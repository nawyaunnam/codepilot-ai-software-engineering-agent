from codepilot.agent import answer
from codepilot.indexer import parse_treesitter
from codepilot.models import Base, CodeChunk, Dependency
from codepilot.retrieval import retrieve
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_unrelated_query_abstains_despite_graph_degree():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            CodeChunk(
                repository_id=1,
                path="auth.py",
                language="python",
                symbol="authenticate",
                kind="function",
                start_line=1,
                end_line=2,
                content="def authenticate(): pass",
                search_text="authenticate",
            )
        )
        db.add(Dependency(repository_id=1, source_path="auth.py", target="os", kind="import", line=1))
        db.commit()
        assert retrieve(db, 1, "unicorns") == []
        assert answer(db, 1, "unicorns")["citations"] == []
        assert retrieve(db, 1, "authenticate")[0].path == "auth.py"


def test_unicode_and_imports_are_preserved():
    text = '// café\nimport { x } from "./other";\nfunction work() { return x; }\n'
    chunks = parse_treesitter("a.ts", text, "typescript")
    chunk = next(c for c in chunks if c.symbol == "work")
    assert chunk.content == "function work() { return x; }"
    assert chunk.start_line == 3
    assert chunk.dependencies


def test_generated_proposal_is_a_diff_without_writing(tmp_path, monkeypatch):
    from codepilot import agent
    from codepilot.models import Repository

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    source = tmp_path / "auth.py"
    source.write_text("def authenticate(): return False\n")
    monkeypatch.setattr(agent.settings, "llm_api_key", "test-only")
    monkeypatch.setattr(
        agent,
        "generate",
        lambda *args: '{"files":[{"path":"auth.py","content":"def authenticate(): return True\\n"}]}',
    )
    with Session(engine) as db:
        db.add(Repository(id=1, name="fixture", root_path=str(tmp_path), status="ready"))
        db.add(
            CodeChunk(
                repository_id=1,
                path="auth.py",
                language="python",
                symbol="authenticate",
                kind="function",
                start_line=1,
                end_line=1,
                content=source.read_text(),
                search_text="authenticate",
            )
        )
        db.commit()
        result = agent.propose(db, 1, "authenticate")
        assert "+def authenticate(): return True" in result["diff"]
        assert source.read_text() == "def authenticate(): return False\n"
        assert result["tests"] == "not-run"
