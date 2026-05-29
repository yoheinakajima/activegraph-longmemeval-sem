"""Pluggable retrieval reranker — flag-gated, opt-in.

The flat retrieval path ranks candidate facts by a blended keyword+vector
score. That score is a weak relevance proxy: same-entity distractors and
stale siblings often outrank the answer-bearing fact, and they reach the
reader because the path keeps a large pool. A *reranker* re-scores the
candidate facts against the question with a stronger model and trims to the
most answer-relevant set, suppressing distractors before they reach the
reader — the precision bottleneck identified in the prior experiment.

The reranker is pluggable, mirroring the embeddings / extraction providers: a
caller (the harness) installs an LLM-backed implementation via
:func:`set_active_reranker`; the pack itself never reads an API key. When no
provider is installed the flat path is unchanged, so default behavior and the
offline tests stay deterministic and key-free.
"""

from __future__ import annotations

from typing import Optional, Protocol


class RerankProvider(Protocol):
    def rerank(
        self, question: str, candidates: list[tuple[str, str]], limit: int
    ) -> list[str]:
        """Return an ordered subset of candidate ids (most relevant first).

        ``candidates`` is ``[(object_id, content), ...]`` in the path's current
        rank order. Implementations may reorder and trim; callers validate that
        every returned id was a candidate before using it.
        """
        ...


# Process-wide active reranker. ``None`` => the flat path does not rerank, which
# is the default so the pack runs offline unchanged.
_ACTIVE: Optional[RerankProvider] = None


def set_active_reranker(provider: Optional[RerankProvider]) -> None:
    """Install the process-wide rerank provider (None resets to no-rerank)."""
    global _ACTIVE
    _ACTIVE = provider


def get_active_reranker() -> Optional[RerankProvider]:
    return _ACTIVE
