"""Behavior 9 — consolidate_memories.

Trigger: ``object.created`` for memory_claim / episodic_memory / procedural_memory.

When the new memory's normalized content matches another active memory of
the same type (exact normalized-content match in v0.1), emit a
``memory_consolidation`` and link both originals into it via
``consolidated_into``. Older sources patch to ``archived``; the newer one
remains active and is treated as the canonical memory.

To avoid loops, consolidation does NOT itself create new memories — it
links existing ones into a consolidation object.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.behaviors._helpers import content_signature
from activegraph_memory.constants import STATUS_ACTIVE, STATUS_ARCHIVED
from activegraph_memory.settings import MemorySettings
from activegraph_memory.types import MemoryConsolidation


def _run(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_consolidation:
        return
    new_obj = event.payload.get("object", {})
    new_id = new_obj.get("id")
    new_type = new_obj.get("type")
    new_data = new_obj.get("data") or {}
    new_content = new_data.get("content") or ""
    if not (new_id and new_content):
        return
    new_sig = content_signature(new_content)

    duplicates: list[str] = []
    for other in ctx.view.objects(type=new_type):
        if other.id == new_id:
            continue
        other_data = other.data or {}
        if other_data.get("status") != STATUS_ACTIVE:
            continue
        if content_signature(other_data.get("content") or "") == new_sig:
            duplicates.append(other.id)

    if not duplicates:
        return

    confidence = 0.9
    if confidence < settings.consolidation_confidence_threshold:
        return

    source_ids = duplicates + [new_id]
    consolidation = MemoryConsolidation(
        source_memory_ids=source_ids,
        consolidated_memory_id=new_id,
        reason="Exact normalized-content duplicate.",
        confidence=confidence,
        metadata={},
    )
    cons_obj = graph.add_object(
        "memory_consolidation", consolidation.model_dump(),
    )
    for sid in source_ids:
        graph.add_relation(sid, cons_obj.id, "consolidated_into")
    for did in duplicates:
        graph.patch_object(did, {"status": STATUS_ARCHIVED})


@behavior(name="consolidate_memories_claim", on=["object.created"],
          where={"object.type": "memory_claim"})
def _claim(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


@behavior(name="consolidate_memories_episodic", on=["object.created"],
          where={"object.type": "episodic_memory"})
def _epi(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


@behavior(name="consolidate_memories_procedural", on=["object.created"],
          where={"object.type": "procedural_memory"})
def _proc(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


consolidate_memories = [_claim, _epi, _proc]
