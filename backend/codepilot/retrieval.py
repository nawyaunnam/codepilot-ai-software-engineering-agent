import re
from collections import defaultdict

import numpy as np

from .embeddings import embed, model_id
from .models import CodeChunk, CodeEmbedding, Dependency


def tokens(text):
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text.lower()))


def retrieve(session, repo_id, query, limit=8):
    chunks = session.query(CodeChunk).filter_by(repository_id=repo_id).all()
    if not chunks:
        return []
    q = tokens(query)
    degree = defaultdict(int)
    for d in session.query(Dependency).filter_by(repository_id=repo_id).all():
        degree[d.source_path] += 1
    lexical = []
    for c in chunks:
        score = len(q & tokens(c.search_text)) / max(len(q), 1)
        score += 0.5 if any(t in c.symbol.lower() for t in q) else 0
        if score:
            lexical.append((score + min(degree[c.path] / 10, 0.2), c))
    vectors = (
        session.query(CodeEmbedding)
        .join(CodeChunk)
        .filter(CodeChunk.repository_id == repo_id, CodeEmbedding.model == model_id())
        .all()
    )
    semantic = []
    by_id = {c.id: c for c in chunks}
    if vectors:
        query_vector = np.array(embed([query])[0])
        for row in vectors:
            v = np.array(row.vector)
            similarity = float(
                np.dot(v, query_vector) / max(np.linalg.norm(v) * np.linalg.norm(query_vector), 1e-9)
            )
            if similarity >= 0.35:
                semantic.append((similarity, by_id[row.chunk_id]))
    # Reciprocal rank fusion prevents one scoring scale dominating the other.
    scores = defaultdict(float)
    for ranked in (lexical, semantic):
        for rank, (_, c) in enumerate(sorted(ranked, key=lambda x: x[0], reverse=True)):
            scores[c.id] += 1 / (60 + rank + 1)
    return [by_id[key] for key in sorted(scores, key=scores.get, reverse=True)[:limit]]
