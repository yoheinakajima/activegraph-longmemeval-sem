"""Behavior 11 — evaluate_memory_usage.

Trigger: ``object.created`` where ``object.type == "memory_answer"``.

Create a baseline ``memory_evaluation`` linked to the answer. The outcome
is conservative:
  - ``unsupported``       — answer had no used memories
  - ``partially_helpful`` — answer used memories but missing_data is non-empty
  - ``unknown``           — used memories with no missing data; needs human/benchmark label

The brief is explicit that this should not aggressively mutate source
memory in the first pass — we only create the evaluation and link it.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.settings import MemorySettings
from activegraph_memory.types import MemoryEvaluation


@behavior(
    name="evaluate_memory_usage",
    on=["object.created"],
    where={"object.type": "memory_answer"},
    creates=["memory_evaluation"],
)
def evaluate_memory_usage(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_memory_evaluation:
        return
    a = event.payload.get("object", {})
    a_id = a.get("id")
    data = a.get("data") or {}
    if not a_id:
        return

    used = list(data.get("used_memory_ids") or [])
    missing = list(data.get("missing_data") or [])
    if not used:
        outcome = "unsupported"
    elif missing:
        outcome = "partially_helpful"
    else:
        outcome = "unknown"

    eval_obj = graph.add_object(
        "memory_evaluation",
        MemoryEvaluation(
            answer_id=a_id,
            query_id=data.get("query_id"),
            used_memory_ids=used,
            outcome=outcome,
            score=None,
            notes="Auto-generated baseline evaluation. Replace via benchmark or user feedback.",
            metadata={"auto": True},
        ).model_dump(),
        
    )
    relation = "validated_by" if outcome in ("unknown",) else "invalidated_by"
    graph.add_relation(a_id, eval_obj.id, relation)
