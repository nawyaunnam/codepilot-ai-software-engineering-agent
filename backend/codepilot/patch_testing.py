import base64
import io
import zipfile
from pathlib import Path, PurePosixPath

import httpx

from .config import settings
from .indexer import IGNORED


def snapshot(root, changes):
    root = Path(root).resolve()
    files = {}
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink() or any(part in IGNORED for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.resolve().is_relative_to(root):
            total += path.stat().st_size
            if total > settings.max_repository_bytes:
                raise ValueError("Test snapshot exceeds size limit")
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    for change in changes:
        name, content = change["path"], change["content"]
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or ":" in name
            or any(p in IGNORED for p in path.parts)
            or not path.parts
        ):
            raise ValueError("Unsafe patch path")
        if len(content.encode()) > 2_000_000:
            raise ValueError("Proposed file exceeds size limit")
        files[name] = content.encode()
    if sum(map(len, files.values())) > settings.max_repository_bytes:
        raise ValueError("Patched snapshot exceeds size limit")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return base64.b64encode(output.getvalue()).decode()


def run_tests(root, changes, command, timeout=120):
    if not settings.sandbox_token:
        raise ValueError("Configure SANDBOX_TOKEN")
    archive = snapshot(root, changes)
    with httpx.Client(timeout=timeout + 45) as client:
        response = client.post(
            f"{settings.sandbox_url}/v1/runs",
            headers={"Authorization": f"Bearer {settings.sandbox_token}"},
            json={"archive": archive, "command": command, "timeout_seconds": timeout},
        )
        response.raise_for_status()
        return response.json()
