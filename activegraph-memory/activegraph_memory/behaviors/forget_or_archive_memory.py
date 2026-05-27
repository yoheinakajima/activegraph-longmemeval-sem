"""Behavior 10 — forget_or_archive_memory.

Two triggers, each its own behavior:
  - ``memory_forget_request.created``  -> patch target's status to ``deleted``
  - ``memory_archive_request.created`` -> patch target's status to ``archived``

We never erase event history — the patch is the auditable record. Retrieval
filters honor the new statuses via ``EXCLUDED_FROM_STANDARD_RETRIEVAL``.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.constants import STATUS_ARCHIVED, STATUS_DELETED


@behavior(
    name="forget_memory",
    on=["object.created"],
    where={"object.type": "memory_forget_request"},
)
def forget_memory(event, graph, ctx):
    req = event.payload.get("object", {})
    data = req.get("data") or {}
    target_id = data.get("memory_id")
    if not target_id:
        return
    target = graph.get_object(target_id)
    if target is None:
        return
    graph.patch_object(target_id, {"status": STATUS_DELETED})


@behavior(
    name="archive_memory",
    on=["object.created"],
    where={"object.type": "memory_archive_request"},
)
def archive_memory(event, graph, ctx):
    req = event.payload.get("object", {})
    data = req.get("data") or {}
    target_id = data.get("memory_id")
    if not target_id:
        return
    target = graph.get_object(target_id)
    if target is None:
        return
    graph.patch_object(target_id, {"status": STATUS_ARCHIVED})
