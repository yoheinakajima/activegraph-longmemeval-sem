"""keyword_search — deterministic text search over memory objects.

Exposes both a plain Python helper (``keyword_search_fn``, called from
behaviors) and an ActiveGraph ``@tool``-decorated wrapper
(``keyword_search``, registered with the pack).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from activegraph.packs import tool

from activegraph_memory.constants import EXCLUDED_FROM_STANDARD_RETRIEVAL, MEMORY_TYPES
from activegraph_memory.tools.scoring import keyword_score
from activegraph_memory.tools.text_normalize import extract_keywords


# ---------------------------------------------------------------- schemas


class SearchHit(BaseModel):
    object_id: str
    score: float
    type: str
    content: str


class KeywordSearchInput(BaseModel):
    query: str
    memory_types: list[str] = Field(default_factory=list)
    exclude_statuses: list[str] = Field(default_factory=list)
    limit: int = 10


class KeywordSearchOutput(BaseModel):
    hits: list[SearchHit] = Field(default_factory=list)


# ---------------------------------------------------------------- helper


def keyword_search_fn(
    objects,
    query: str,
    *,
    memory_types: Optional[list[str]] = None,
    exclude_statuses: Optional[list[str]] = None,
    limit: int = 10,
) -> list[SearchHit]:
    """Plain Python search. ``objects`` is an iterable of ActiveGraph Objects."""
    types = tuple(memory_types) if memory_types else MEMORY_TYPES
    excluded = set(exclude_statuses or EXCLUDED_FROM_STANDARD_RETRIEVAL)
    keywords = extract_keywords(query)

    hits: list[SearchHit] = []
    for obj in objects:
        if obj.type not in types:
            continue
        data = obj.data or {}
        if data.get("status") in excluded:
            continue
        content = str(data.get("content", ""))
        score = keyword_score(keywords, content)
        if score <= 0.0:
            continue
        hits.append(SearchHit(
            object_id=obj.id,
            score=score,
            type=obj.type,
            content=content,
        ))
    # Stable sort: score desc, then object_id asc for determinism
    hits.sort(key=lambda h: (-h.score, h.object_id))
    return hits[:limit]


# ---------------------------------------------------------------- @tool wrapper


@tool(
    name="keyword_search",
    description=(
        "Deterministic keyword search over memory objects in the current graph. "
        "Returns the top-N hits ordered by keyword-overlap score."
    ),
    input_schema=KeywordSearchInput,
    output_schema=KeywordSearchOutput,
    cost_per_call=Decimal("0.0"),
    timeout_seconds=5.0,
    deterministic=True,
)
def keyword_search(args: KeywordSearchInput, ctx) -> KeywordSearchOutput:
    """ctx.graph gives access to all objects; we filter them ourselves."""
    objects = ctx.graph.all_objects()
    hits = keyword_search_fn(
        objects,
        args.query,
        memory_types=args.memory_types or None,
        exclude_statuses=args.exclude_statuses or None,
        limit=args.limit,
    )
    return KeywordSearchOutput(hits=hits)
