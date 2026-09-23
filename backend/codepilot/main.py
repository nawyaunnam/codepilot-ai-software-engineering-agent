import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .agent import answer, plan, propose
from .auth import login, require_user
from .config import settings
from .embeddings import embed, model_id
from .indexer import parse_file, safe_files
from .ingestion import github_archive, unpack
from .models import CodeChunk, CodeEmbedding, Dependency, Repository, SessionLocal, init_db
from .patch_testing import run_tests


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="CodePilot", version="0.2.0", lifespan=lifespan)
api = APIRouter(prefix="/api", dependencies=[Depends(require_user)])


class Credentials(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=1024)


class RepoIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    path: str


class GitHubIn(BaseModel):
    url: str
    ref: str = "main"


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=12000)


class ProposalIn(Query):
    command: list[str] = Field(default_factory=lambda: ["python3", "-m", "pytest", "-q"], max_length=20)
    timeout_seconds: int = Field(default=120, ge=1, le=300)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login")
def sign_in(credentials: Credentials, request: Request, response: Response):
    token = login(credentials.username, credentials.password, request.client.host)
    response.set_cookie(
        "codepilot_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=3600,
        path="/",
    )
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


@app.post("/auth/logout")
def sign_out(response: Response):
    response.delete_cookie("codepilot_session", path="/")
    return {"status": "signed-out"}


def get_repo(db, repo_id):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo


def index_root(name, root):
    root = root.resolve()
    if not root.is_relative_to(Path(settings.workspace_root).resolve()) or not root.is_dir():
        raise HTTPException(400, "Repository must exist inside the configured workspace")
    paths = list(safe_files(root))
    if sum(p.stat().st_size for p in paths) > settings.max_repository_bytes:
        raise HTTPException(413, "Repository exceeds size limit")
    with SessionLocal() as db:
        repo = Repository(name=name, root_path=str(root), status="indexing")
        db.add(repo)
        db.flush()
        chunks, warnings, edges = [], [], set()
        for path in paths:
            try:
                parsed = parse_file(root, path)
            except (SyntaxError, ValueError) as exc:
                warnings.append(f"{path.relative_to(root)}: {type(exc).__name__}")
                continue
            for c in parsed:
                chunk = CodeChunk(
                    repository_id=repo.id,
                    path=c.path,
                    language=c.language,
                    symbol=c.symbol,
                    kind=c.kind,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    content=c.content,
                    search_text=f"{c.path} {c.symbol} {c.content}",
                )
                db.add(chunk)
                chunks.append(chunk)
                edges.update((c.path, target, line) for target, line in c.dependencies)
        for source, target, line in edges:
            db.add(
                Dependency(repository_id=repo.id, source_path=source, target=target, line=line, kind="import")
            )
        db.flush()
        for start in range(0, len(chunks), 32):
            batch = chunks[start : start + 32]
            vectors = embed([c.search_text[:12000] for c in batch])
            for c, vector in zip(batch, vectors, strict=bool(vectors)):
                db.add(CodeEmbedding(chunk_id=c.id, model=model_id(), vector=vector))
        repo.status = "ready"
        db.commit()
        return {
            "id": repo.id,
            "status": repo.status,
            "chunks": len(chunks),
            "warnings": warnings,
            "embedding_model": model_id(),
        }


@api.post("/repositories", status_code=201)
def index_repository(request: RepoIn):
    return index_root(request.name, Path(request.path))


@api.post("/repositories/upload", status_code=201)
async def upload(request: Request):
    # Raw ZIP streaming enforces the bound before writing or parsing multipart data.
    data = bytearray()
    async for part in request.stream():
        data.extend(part)
        if len(data) > settings.max_repository_bytes:
            raise HTTPException(413, "ZIP exceeds upload limit")
    try:
        root = unpack(bytes(data))
    except (ValueError, zipfile.BadZipFile) as exc:
        raise HTTPException(400, str(exc)) from exc
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(index_root, "uploaded-repository", root)


@api.post("/repositories/github", status_code=201)
def github(request: GitHubIn):
    try:
        root = unpack(github_archive(request.url, request.ref))
        return index_root(request.url.rstrip("/").split("/")[-1], root)
    except (ValueError, httpx.HTTPError, zipfile.BadZipFile) as exc:
        raise HTTPException(400, "GitHub import failed: check public URL, ref, and size limits") from exc


@api.get("/repositories")
def repositories():
    with SessionLocal() as db:
        return [{"id": r.id, "name": r.name, "status": r.status} for r in db.query(Repository).all()]


@api.get("/settings/status")
def provider_status():
    return {
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model,
        "embedding_model": model_id(),
        "sandbox_configured": bool(settings.sandbox_token),
    }


@api.post("/repositories/{repo_id}/query")
def query(repo_id: int, q: Query):
    with SessionLocal() as db:
        get_repo(db, repo_id)
        return answer(db, repo_id, q.question)


@api.post("/repositories/{repo_id}/plan")
def feature_plan(repo_id: int, q: Query):
    with SessionLocal() as db:
        get_repo(db, repo_id)
        return plan(db, repo_id, q.question)


@api.get("/repositories/{repo_id}/graph")
def graph(repo_id: int):
    with SessionLocal() as db:
        get_repo(db, repo_id)
        edges = db.query(Dependency).filter_by(repository_id=repo_id).limit(2000).all()
        return {
            "edges": [
                {"source": e.source_path, "target": e.target, "kind": e.kind, "line": e.line} for e in edges
            ]
        }


@api.post("/repositories/{repo_id}/propose")
def proposal(repo_id: int, q: ProposalIn):
    with SessionLocal() as db:
        repo = get_repo(db, repo_id)
        try:
            result = propose(db, repo_id, q.question)
            changes = result.pop("changes")
            # Test both snapshots so existing failures are distinguishable from regressions.
            result["baseline_tests"] = run_tests(repo.root_path, [], q.command, q.timeout_seconds)
            result["tests"] = run_tests(repo.root_path, changes, q.command, q.timeout_seconds)
            return result
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Sandbox unavailable; no patch applied or tests claimed") from exc


app.include_router(api)
