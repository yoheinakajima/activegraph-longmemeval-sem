"""Concept (entity/topic) extraction + canonicalization helpers.

A *concept* is a canonical entity or topic that memories are about. The concept
layer is an optional semantic index over memories: when ``enable_concept_graph``
is set, each extracted memory is linked to one or more ``memory_concept`` nodes
via ``about_entity``. Concepts can then be vector-searched to find relevant
memories indirectly (the agentic retrieval path), which surfaces facts that
share an entity even when their wording is far from the query.

Two ways concept names are produced, mirroring the extractor/embeddings pattern:

* **Deterministic (default, offline):** :func:`deterministic_concepts` derives
  concept names from a memory's content (capitalized noun phrases + salient
  keywords). No network, no key — so tests stay deterministic and validation
  runs cost nothing extra.
* **Injected provider:** a caller may install a smarter concept extractor via
  :func:`set_active_concept_extractor` (e.g. an LLM). The pack stays
  key-agnostic; the provider returns concept names for a memory's content.
"""

from __future__ import annotations

import re
from typing import Optional, Protocol

from activegraph_memory.tools.text_normalize import extract_keywords, normalize

# Capitalized (possibly multi-word) phrases — a cheap proper-noun / named-entity
# detector. Allows internal &, ., - so "AT&T", "U.S.", "text-davinci" survive.
_CAP_PHRASE = re.compile(r"\b([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,3})\b")

# Words capitalized only by sentence position, not because they name an entity.
_SENTENCE_LEAD = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "it", "his", "her", "their", "our", "my", "your",
    "if", "when", "while", "but", "and", "or", "so", "then", "also",
})


class ConceptExtractor(Protocol):
    def concepts(self, content: str, memory_type: str) -> list[str]: ...


_ACTIVE: Optional[ConceptExtractor] = None


def set_active_concept_extractor(provider: Optional[ConceptExtractor]) -> None:
    """Install the process-wide concept extractor (None resets to heuristic)."""
    global _ACTIVE
    _ACTIVE = provider


def get_active_concept_extractor() -> Optional[ConceptExtractor]:
    return _ACTIVE


def normalize_concept(name: str) -> str:
    """Canonical key for deduping surface forms of the same concept."""
    return normalize(name)


def deterministic_concepts(content: str, *, max_concepts: int = 6) -> list[str]:
    """Derive concept names from a memory's text, deterministically.

    Capitalized multi-word phrases (proper nouns / named entities) come first,
    then salient single keywords as topic anchors. First-seen order is
    preserved; results are deduped by normalized form.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        name = name.strip().strip(".,;:!?()[]\"'").strip()
        if len(name) < 2:
            return
        key = normalize_concept(name)
        if not key or key in seen:
            return
        seen.add(key)
        out.append(name)

    for m in _CAP_PHRASE.finditer(content or ""):
        toks = m.group(1).split()
        # Drop a leading sentence-position-only capital ("The", "When", ...).
        while toks and toks[0].lower() in _SENTENCE_LEAD:
            toks = toks[1:]
        if toks:
            _add(" ".join(toks))
        if len(out) >= max_concepts:
            return out[:max_concepts]

    for kw in extract_keywords(content or ""):
        _add(kw)
        if len(out) >= max_concepts:
            break
    return out[:max_concepts]


def concepts_for_memory(
    content: str, memory_type: str, *, max_concepts: int = 6
) -> list[str]:
    """Concept names for a memory: injected provider if present, else the
    deterministic derivation. Deduped by normalized form and capped."""
    provider = get_active_concept_extractor()
    if provider is not None:
        names = provider.concepts(content, memory_type) or []
    else:
        names = deterministic_concepts(content, max_concepts=max_concepts)

    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        n = (n or "").strip()
        key = normalize_concept(n)
        if n and key and key not in seen:
            seen.add(key)
            out.append(n)
        if len(out) >= max_concepts:
            break
    return out
