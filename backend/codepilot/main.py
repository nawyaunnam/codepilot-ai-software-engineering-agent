from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import answer, plan
from .config import settings
from .indexer import parse_file, safe_files
from .models import CodeChunk, Dependency, Repository, SessionLocal, init_db

app = FastAPI(title="CodePilot", version="0.1.0")


@app.on_event("startup")
def startup():
    init_db()


class RepoIn(BaseModel):
    name: str
    path: str


class Query(BaseModel):
    question: str


class TestRun(BaseModel):
    repository_path: str
    command: list[str]
    timeout_seconds: int = 120


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/repositories", status_code=202)
def index_repository(request: RepoIn):
    root = Path(request.path).resolve()
    workspace = Path("/workspace").resolve()
    if not root.is_relative_to(workspace):
        raise HTTPException(403, "Repository must be mounted under /workspace")
    if not root.is_dir():
        raise HTTPException(400, "repository path does not exist")
    total = sum(p.stat().st_size for p in safe_files(root))
    if total > settings.max_repository_bytes:
        raise HTTPException(413, "repository exceeds configured limit")
    with SessionLocal() as db:
        repo = Repository(name=request.name, root_path=str(root), status="indexing")
        db.add(repo)
        db.commit()
        db.refresh(repo)
        count = 0
        for path in safe_files(root):
            for c in parse_file(root, path):
                db.add(
                    CodeChunk(
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
                )
                for target, line in c.dependencies:
                    db.add(
                        Dependency(
                            repository_id=repo.id, source_path=c.path, target=target, kind="import", line=line
                        )
                    )
                count += 1
        repo.status = "ready"
        db.commit()
        return {"id": repo.id, "status": repo.status, "chunks": count}


@app.post("/api/repositories/{repo_id}/query")
def query(repo_id: int, q: Query):
    with SessionLocal() as db:
        return answer(db, repo_id, q.question)


@app.post("/api/repositories/{repo_id}/plan")
def feature_plan(repo_id: int, q: Query):
    with SessionLocal() as db:
        return plan(db, repo_id, q.question)


@app.get("/api/repositories/{repo_id}/graph")
def graph(repo_id: int):
    with SessionLocal() as db:
        edges = db.query(Dependency).filter_by(repository_id=repo_id).limit(2000).all()
        return {
            "edges": [
                {"source": e.source_path, "target": e.target, "kind": e.kind, "line": e.line} for e in edges
            ]
        }


@app.post("/api/test-runs")
def test_run(run: TestRun):
    try:
        return httpx.post(
            f"{settings.sandbox_url}/v1/runs", json=run.model_dump(), timeout=run.timeout_seconds + 5
        ).json()
    except httpx.HTTPError as e:
        raise HTTPException(503, "sandbox unavailable") from e


@app.get("/api/repositories")
def repositories():
    with SessionLocal() as db:
        return [{"id": r.id, "name": r.name, "status": r.status} for r in db.query(Repository).all()]


@app.post("/api/repositories/{repo_id}/propose")
def proposal(repo_id: int, q: Query):
    from .agent import propose

    with SessionLocal() as db:
        if not db.get(Repository, repo_id):
            raise HTTPException(404, "Repository not found")
        try:
            return propose(db, repo_id, q.question)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc
