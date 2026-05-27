"""Deterministic text utilities: tokenization, lowercasing, keyword extraction.

No network, no randomness. Suitable for use inside deterministic behaviors.
"""

from __future__ import annotations

import re

_PUNCT_RE = re.compile(r"[^\w\s]+")
_WS_RE = re.compile(r"\s+")

# A very small stop list — intentionally short. The memory pack is more
# useful when content words like "prefers" or "called" survive.
_STOPWORDS = frozenset(
    """
    a an the and or but if then so to of in on at by for from with as is are was were
    be been being do does did have has had this that these those it its i you he she
    we they them me my your his her our their about over under up down out into
    """.split()
)


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    out = text.lower()
    out = _PUNCT_RE.sub(" ", out)
    out = _WS_RE.sub(" ", out).strip()
    return out


def tokenize(text: str) -> list[str]:
    """Normalize and split into tokens."""
    n = normalize(text)
    return [t for t in n.split(" ") if t]


def extract_keywords(text: str, *, drop_stopwords: bool = True,
                     min_len: int = 2, max_keywords: int = 20) -> list[str]:
    """Return distinct content words from text, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for tok in tokenize(text):
        if drop_stopwords and tok in _STOPWORDS:
            continue
        if len(tok) < min_len:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= max_keywords:
            break
    return out
