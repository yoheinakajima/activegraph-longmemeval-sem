"""Behavior 7 — resolve_temporal_refs.

Trigger: ``object.created`` for memory_claim / episodic_memory / memory_observation.

Extract temporal references from the content, attempt to resolve relative
references against the observation's anchor (``occurred_at`` or
``observed_at``), and emit ``temporal_ref`` objects linked via
``has_temporal_ref``.
"""

from __future__ import annotations

from datetime import datetime

from activegraph.packs import behavior

from activegraph_memory.behaviors._helpers import find_temporal_refs, resolve_temporal
from activegraph_memory.settings import MemorySettings
from activegraph_memory.types import TemporalRef


def _coerce_dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _run(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_temporal_resolution:
        return
    obj = event.payload.get("object", {})
    obj_id = obj.get("id")
    data = obj.get("data") or {}
    content = data.get("content") or ""
    if not (obj_id and content):
        return

    anchor = _coerce_dt(data.get("occurred_at") or data.get("observed_at"))
    for mention in find_temporal_refs(content):
        resolved = resolve_temporal(mention, anchor)
        ref = TemporalRef(
            text=mention["text"],
            resolved_at=resolved["resolved_at"],
            anchor=resolved["anchor"],
            resolution_method=resolved["resolution_method"],
            confidence=resolved["confidence"],
            metadata={},
        )
        ref_obj = graph.add_object(
            "temporal_ref", ref.model_dump(mode="json"),
        )
        graph.add_relation(obj_id, ref_obj.id, "has_temporal_ref",
                           )


@behavior(name="resolve_temporal_refs_claim", on=["object.created"],
          where={"object.type": "memory_claim"}, creates=["temporal_ref"])
def _claim(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


@behavior(name="resolve_temporal_refs_episodic", on=["object.created"],
          where={"object.type": "episodic_memory"}, creates=["temporal_ref"])
def _epi(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


@behavior(name="resolve_temporal_refs_observation", on=["object.created"],
          where={"object.type": "memory_observation"}, creates=["temporal_ref"])
def _obs(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


resolve_temporal_refs = [_claim, _epi, _obs]
