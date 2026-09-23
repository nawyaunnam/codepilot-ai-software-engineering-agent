# Architecture

FastAPI authenticates a single operator before accepting imported archives or repository questions. Imports are bounded and synchronous. Python AST / Tree-sitter produce code chunks, exact line ranges, and import edges. Chunk vectors are stored in a separate model-tagged PostgreSQL table, so existing repositories can still use lexical search without a schema migration. Reimport old repositories to add embeddings.

Retrieval combines lexical and symbol relevance, import-degree weighting, and cosine similarity, then applies reciprocal rank fusion. Local embeddings use FastEmbed ONNX; OpenAI embeddings are optional. Model identifiers prevent accidental comparison across vector spaces. The LangChain chat adapter consumes retrieved evidence for answers, plans, and complete-file change proposals.

The proposal endpoint constructs a unified diff without writing source. It then snapshots both original and modified trees and sends each to the Go broker over an authenticated internal API. The broker creates a fresh restricted Docker container, copies the validated snapshot, runs the supplied argument array, reads exit status, and destroys the container. Responses distinguish baseline failures, patched failures, infrastructure failures, and timeouts. No successful test status is fabricated when the runner is unavailable.

See the [official embedding guide](https://developers.openai.com/api/docs/guides/embeddings) for the remote vector API. For larger installations, move indexing to a queue and replace in-process vector scoring with pgvector ANN; neither is needed for the bounded reference deployment.
