# Architecture

Indexing walks supported source files, rejects symlinks, ignores generated and vendor directories, and caps file and repository size. Python uses the language AST. Tree-sitter handles TypeScript, TSX, JavaScript, Go, and Java. Each symbol stores its exact source span and imports become dependency edges.

Retrieval ranks chunks by query-token overlap, symbol-name matches, and graph degree. A production variant adds dense code embeddings, reciprocal-rank fusion, a cross-encoder reranker, and dependency expansion within a strict context budget. Answers and plans consume retrieved evidence and return citations.

Feature planning returns an ordered set of relevant files before generation. A write-enabled agent should create a temporary branch, apply patches with optimistic blob-SHA checks, run targeted tests in isolation, present a unified diff, and require approval before opening a pull request.
