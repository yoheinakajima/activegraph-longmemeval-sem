"""Behavior 8 — attach_numeric_scope.

Trigger: ``object.created`` for memory_claim / episodic_memory / memory_observation.

Extract numbers/quantities with rough owner/property attribution, emit
``quantity_claim`` objects, and link them via ``has_quantity``.

The heuristic deliberately refuses to attach a number when it cannot guess
an owner — better to leave the field None than to misattribute (the brief is
explicit: "Do not attach numbers to the wrong entity").
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.behaviors._helpers import find_quantities
from activegraph_memory.settings import MemorySettings
from activegraph_memory.types import QuantityClaim


def _run(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_numeric_scope:
        return
    obj = event.payload.get("object", {})
    obj_id = obj.get("id")
    data = obj.get("data") or {}
    content = data.get("content") or ""
    if not (obj_id and content):
        return

    for q in find_quantities(content):
        qc = QuantityClaim(
            raw_value=q["raw_value"],
            value=q.get("value"),
            unit=q.get("unit"),
            owner=q.get("owner"),
            property=q.get("property"),
            item_or_event=q.get("owner"),  # heuristic alias
            exactness=q.get("exactness", "unknown"),
            can_sum_exactly=bool(q.get("can_sum_exactly")),
            confidence=0.8 if q.get("owner") else 0.5,
            metadata={},
        )
        qc_obj = graph.add_object(
            "quantity_claim", qc.model_dump(),
        )
        graph.add_relation(obj_id, qc_obj.id, "has_quantity")


@behavior(name="attach_numeric_scope_claim", on=["object.created"],
          where={"object.type": "memory_claim"}, creates=["quantity_claim"])
def _claim(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


@behavior(name="attach_numeric_scope_episodic", on=["object.created"],
          where={"object.type": "episodic_memory"}, creates=["quantity_claim"])
def _epi(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


@behavior(name="attach_numeric_scope_observation", on=["object.created"],
          where={"object.type": "memory_observation"}, creates=["quantity_claim"])
def _obs(event, graph, ctx, *, settings: MemorySettings):
    _run(event, graph, ctx, settings=settings)


attach_numeric_scope = [_claim, _epi, _obs]
