# Security boundaries

All API operations require the configured operator's JWT. Deploy HTTPS and enable secure cookies outside localhost. The workspace is single-operator; isolate instances for separate organizations. Protect `.env`, model credentials, database storage, and the broker socket. Apply an ingress login rate limit for multiple API replicas.

GitHub downloads use only codeload.github.com with redirects disabled. ZIP extraction checks member paths, symlinks, duplicates, entry count, compressed and expanded sizes. Uploaded sources are data during indexing. LLM prompts classify repository contents as untrusted evidence, but prompts cannot guarantee injection resistance; proposed code always runs without production credentials.

Only the private broker receives the Docker socket. Every test gets a disposable non-root container with network disabled, no inherited host mounts, read-only root, bounded /tmp, dropped capabilities, default Docker seccomp, CPU/memory/PID limits, and timeout cleanup. Containers are a shared-kernel boundary, not a VM. Run the broker on a dedicated execution host; use gVisor or microVMs for mutually untrusted users. The configured test image is trusted and preinstalled dependencies must be reviewed. Test output is capped while collecting, not after unbounded buffering.
