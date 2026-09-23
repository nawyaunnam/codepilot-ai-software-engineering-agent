import re
from collections import defaultdict

from .models import CodeChunk, Dependency


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text.lower()))


def retrieve(session, repo_id: int, query: str, limit: int = 8):
    q = tokens(query)
    chunks = session.query(CodeChunk).filter_by(repository_id=repo_id).all()
    deps = session.query(Dependency).filter_by(repository_id=repo_id).all()
    degree = defaultdict(int)
    for d in deps:
        degree[d.source_path] += 1
    ranked = []
    for c in chunks:
        lexical = len(q & tokens(c.search_text)) / max(len(q), 1)
        symbol = 0.5 if any(t in c.symbol.lower() for t in q) else 0
        if not lexical and not symbol:
            continue
        graph = min(degree[c.path] / 10, 0.2)
        ranked.append((lexical + symbol + graph, c))
    return [c for score, c in sorted(ranked, key=lambda x: x[0], reverse=True)[:limit] if score > 0]
