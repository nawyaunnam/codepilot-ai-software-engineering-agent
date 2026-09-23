import base64
import io
import zipfile

import pytest
from codepilot import retrieval
from codepilot.models import Base, CodeChunk, CodeEmbedding
from codepilot.patch_testing import snapshot
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_semantic_retrieval_without_lexical_match(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(retrieval, "embed", lambda texts: [[1, 0]])
    with Session(engine) as db:
        chunk = CodeChunk(
            repository_id=1,
            path="auth.py",
            language="python",
            symbol="verify",
            kind="function",
            start_line=1,
            end_line=1,
            content="verify()",
            search_text="verify credentials",
        )
        db.add(chunk)
        db.flush()
        db.add(CodeEmbedding(chunk_id=chunk.id, model=retrieval.model_id(), vector=[1, 0]))
        db.commit()
        assert retrieval.retrieve(db, 1, "login")[0].symbol == "verify"
        assert retrieval.retrieve(db, 2, "login") == []


def test_patch_snapshot_preserves_original(tmp_path):
    source = tmp_path / "auth.py"
    source.write_text("before")
    encoded = snapshot(
        tmp_path,
        [{"path": "auth.py", "content": "after"}, {"path": "tests/test_auth.py", "content": "assert True"}],
    )
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as z:
        assert z.read("auth.py") == b"after"
        assert z.read("tests/test_auth.py") == b"assert True"
    assert source.read_text() == "before"


def test_patch_escape_rejected(tmp_path):
    with pytest.raises(ValueError):
        snapshot(tmp_path, [{"path": "../escape", "content": "x"}])
