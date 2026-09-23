# CodePilot

A repository-aware engineering assistant with AST indexing, hybrid code search, cited explanations, feature planning, and automatically tested change proposals.

## Start locally

```bash
python3 scripts/setup.py
# Optional: add LLM_API_KEY to .env for live answers, plans, and patch generation.
docker compose build
docker compose up -d
```

Open http://localhost:3000 and sign in with `admin` and the password chosen during setup. Docker Engine must be available to the sandbox broker. Build creates a dedicated Python/pytest test runtime; source repositories never receive the Docker socket.

The default local embedding model (`BAAI/bge-small-en-v1.5`) downloads on first import, then remains in a persistent cache. It does not need an API key. For cloud embeddings, set `EMBEDDING_PROVIDER=openai`, `EMBEDDING_MODEL=text-embedding-3-small`, and `LLM_API_KEY`. Reimport repositories after changing embedding models. Source sent to a remote embedding or chat provider leaves your machine.

## User workflow

1. **Connect:** paste a public GitHub repository URL and branch/tag/SHA, upload a ZIP, or index a directory mounted under `/workspace`.
2. **Index:** Python AST and Tree-sitter extract symbols, line ranges, and import edges; vectors are stored alongside chunks in PostgreSQL.
3. **Ask:** hybrid retrieval fuses lexical/symbol/graph ranking with cosine similarity over model-tagged embeddings. Answers include repository-relative citations.
4. **Plan:** retrieve candidate files and produce a cited change plan.
5. **Generate & test:** request a change and a test command. CodePilot generates complete candidate files, creates a unified diff, and runs both the baseline and patched snapshots in fresh containers. The response includes separate test statuses, exit codes, bounded output, and timeouts. Original files stay unchanged.

The built-in test image supports `python3 -m pytest -q`. Dependencies must be installed in a custom `TEST_IMAGE` before testing: execution has no network. The UI accepts whitespace-separated command arguments; JSON callers can provide an exact argument array. A failing baseline is reported rather than concealed as a patch regression.

## Authentication

This release is a **single-operator workspace**. Every `/api` route requires a signed one-hour JWT. Browser login uses an HttpOnly, SameSite=Strict cookie; API clients may use a bearer token. Login has a process-local rate limit and mutation requests using cookies validate Origin. Configure `COOKIE_SECURE=true` and `ALLOWED_ORIGINS` behind HTTPS. No account registration, default password, multi-tenant claim, or secret-display endpoint is provided.

```bash
curl -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"YOUR_LOCAL_PASSWORD"}'
# Use the returned access_token in Authorization: Bearer ...
```

## API

| Route | Behavior |
|---|---|
| `POST /auth/login`, `/auth/logout` | Sign in / clear browser session |
| `GET /api/settings/status` | Non-secret provider readiness |
| `POST /api/repositories` | Index mounted path |
| `POST /api/repositories/github` | Import public GitHub `{url, ref}` |
| `POST /api/repositories/upload` | Stream raw `application/zip` bytes |
| `GET /api/repositories` | List imported repositories |
| `POST /api/repositories/{id}/query` | `{question}` → cited answer |
| `POST /api/repositories/{id}/plan` | `{question}` → change plan |
| `POST /api/repositories/{id}/propose` | `{question, command, timeout_seconds}` → diff and baseline/patched tests |
| `GET /api/repositories/{id}/graph` | Import dependency edges |

No key is necessary for imports, local embeddings, retrieval, graphs, or viewing source evidence. Live generation requires the operator's own provider key and account access. `LLM_MODEL` is configurable. Keyless mode explicitly returns evidence rather than pretending to have generated an explanation.

## Safety and execution

ZIP validation rejects traversal, absolute paths, backslashes, symlinks, duplicate entries, oversized expansion, and suspicious compression ratios. GitHub imports use a fixed HTTPS codeload host without following redirects. Imported source is never executed during indexing.

The Go broker authenticates requests with a separate secret, limits concurrency, extracts validated snapshots, then creates a new container per test run. Test containers have no network, credentials, host mounts, or Docker socket; they run as UID 65534 with a read-only root, writable bounded temporary storage, dropped capabilities, PID/memory/CPU limits, timeout cleanup, and one-megabyte logs. The broker itself controls Docker and must remain private on a dedicated worker host. Containers share the host kernel; use gVisor or microVM workers for hostile public workloads.

## Validation

`pytest -q`, `ruff check backend`, `npm run build`, and `go test ./...` verify authentication, archive validation, retrieval, source citations, proposal non-mutation, output limits, and path controls. CI also builds all images and runs a real Python test inside the isolated runner, including a network-denial check. Live provider smoke checks are separate because they require credentials and may incur cost.

## Scope

GitHub imports currently support public repositories (private sources can be uploaded as ZIP). Dependency graphs describe imports, not fully resolved dynamic calls. Indexing is synchronous and bounded to 50 MB/10,000 archive entries. Vectors are persisted in PostgreSQL JSON and scored in-process; migrate to pgvector ANN for large indexes. Redis and AWS/Kubernetes resources are deployment scaffolding, not required for correctness. Generated changes are tested and returned for review; this service does not push branches or create pull requests.
