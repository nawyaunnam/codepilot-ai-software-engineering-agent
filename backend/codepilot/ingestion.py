import io
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from uuid import uuid4

import httpx

from .config import settings


def unpack(data: bytes) -> Path:
    if len(data) > settings.max_repository_bytes:
        raise ValueError("Archive exceeds size limit")
    root = Path(settings.workspace_root) / uuid4().hex
    root.mkdir(parents=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 10000:
                raise ValueError("Too many archive entries")
            total = 0
            seen = set()
            for entry in entries:
                path = PurePosixPath(entry.filename)
                mode = entry.external_attr >> 16
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in entry.filename
                    or ":" in entry.filename
                    or stat.S_ISLNK(mode)
                ):
                    raise ValueError("Unsafe archive path or symlink")
                if entry.filename in seen:
                    raise ValueError("Duplicate archive entry")
                seen.add(entry.filename)
                total += entry.file_size
                if total > settings.max_repository_bytes or entry.file_size > 2_000_000:
                    raise ValueError("Expanded archive exceeds size limit")
                if entry.file_size / max(entry.compress_size, 1) > 200:
                    raise ValueError("Suspicious compression ratio")
                if ".git" in path.parts or entry.is_dir():
                    continue
                target = root.joinpath(*path.parts)
                if not target.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Archive escapes workspace")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, 65536)
        children = list(root.iterdir())
        return children[0] if len(children) == 1 and children[0].is_dir() else root
    except Exception:
        shutil.rmtree(root)
        raise


def github_archive(url: str, ref: str) -> bytes:
    # Fixed codeload host: never fetch arbitrary URLs or follow redirects.
    match = re.fullmatch(r"https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?", url)
    if not match or not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", ref) or ".." in ref:
        raise ValueError("Use a public https://github.com/owner/repo URL and a branch, tag, or SHA")
    owner, repo = match.groups()
    with httpx.stream(
        "GET", f"https://codeload.github.com/{owner}/{repo}/zip/{ref}", timeout=30, follow_redirects=False
    ) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("GitHub archive unavailable")
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > settings.max_repository_bytes:
                raise ValueError("GitHub archive exceeds size limit")
        return bytes(data)
