# Security

Treat repositories and their instructions as untrusted data. Never execute code while indexing. Remove secrets from prompts, isolate tenants at storage and retrieval, validate Git URLs against SSRF, pin revisions, verify archive paths, and audit access.

Execute tests in single-use sandboxes with no host socket, no credentials, deny-by-default networking, read-only source, writable size-limited scratch space, CPU/memory/PID/time limits, syscall filtering, and bounded logs. The included runner is a development baseline and must not run hostile public code on a shared Docker daemon.
