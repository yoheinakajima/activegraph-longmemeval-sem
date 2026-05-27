"""Deterministic scoring helpers used by retrieval."""

from __future__ import annotations

import math

from activegraph_memory.tools.text_normalize import tokenize


def keyword_score(query_keywords: list[str], text: str) -> float:
    """Fraction of query keywords present in text. In [0, 1]."""
    if not query_keywords:
        return 0.0
    text_tokens = set(tokenize(text))
    hits = sum(1 for k in query_keywords if k in text_tokens)
    return hits / len(query_keywords)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Returns 0.0 for zero-norm vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
