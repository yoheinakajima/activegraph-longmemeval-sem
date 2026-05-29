"""vector_search — deterministic hash-embedding vector search.

Uses the ``DeterministicEmbeddingProvider`` from ``embeddings.py`` so tests
work offline without numpy. Production users can pass a real provider.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from activegraph.packs import tool

from activegraph_memory.constants import EXCLUDED_FROM_STANDARD_RETRIEVAL, MEMORY_TYPES
from activegraph_memory.tools.embeddings import (
    EmbeddingProvider,
    get_active_provider,
)
from activegraph_memory.tools.keyword_search import SearchHit
from activegraph_memory.tools.scoring import cosine_similarity


class VectorSearchInput(BaseModel):
    query: str
    memory_types: list[str] = Field(default_factory=list)
    exclude_statuses: list[str] = Field(default_factory=list)
    limit: int = 10


class VectorSearchOutput(BaseModel):
    hits: list[SearchHit] = Field(default_factory=list)


def vector_search_fn(
    objects,
    query: str,
    *,
    memory_types: Optional[list[str]] = None,
    exclude_statuses: Optional[list[str]] = None,
    limit: int = 10,
    provider: Optional[EmbeddingProvider] = None,
) -> list[SearchHit]:
    types = tuple(memory_types) if memory_types else MEMORY_TYPES
    excluded = set(exclude_statuses or EXCLUDED_FROM_STANDARD_RETRIEVAL)
    p = provider or get_active_provider()

    # Gather candidate (object, content) pairs first, then embed all contents
    # in a single batched call so a real provider can cache/batch instead of
    # making one network request per object.
    candidates: list[tuple] = []
    for obj in objects:
        if obj.type not in types:
            continue
        data = obj.data or {}
        if data.get("status") in excluded:
            continue
        content = str(data.get("content", ""))
        if not content:
            continue
        candidates.append((obj, content))

    if not candidates:
        return []

    qvec = p.embed(query)
    cvecs = p.embed_many([c for _, c in candidates])

    hits: list[SearchHit] = []
    for (obj, content), cvec in zip(candidates, cvecs):
        score = cosine_similarity(qvec, cvec)
        if score <= 0.0:
            continue
        hits.append(SearchHit(
            object_id=obj.id,
            score=score,
            type=obj.type,
            content=content,
        ))
    hits.sort(key=lambda h: (-h.score, h.object_id))
    return hits[:limit]


@tool(
    name="vector_search",
    description=(
        "Vector similarity search over memory objects using a deterministic "
        "hash-based embedding (no network, no API key)."
    ),
    input_schema=VectorSearchInput,
    output_schema=VectorSearchOutput,
    cost_per_call=Decimal("0.0"),
    timeout_seconds=5.0,
    deterministic=True,
)
def vector_search(args: VectorSearchInput, ctx) -> VectorSearchOutput:
    hits = vector_search_fn(
        ctx.graph.all_objects(),
        args.query,
        memory_types=args.memory_types or None,
        exclude_statuses=args.exclude_statuses or None,
        limit=args.limit,
    )
    return VectorSearchOutput(hits=hits)
