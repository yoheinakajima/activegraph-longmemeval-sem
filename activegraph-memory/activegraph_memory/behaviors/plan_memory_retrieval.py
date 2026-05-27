"""Behavior 3 — plan_memory_retrieval.

Trigger: ``object.created`` where ``object.type == "memory_query"``.

Turn the question into a structured ``retrieval_plan`` (keywords, memory
types, mode, required data). The retriever fires off the plan.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.behaviors._helpers import (
    coerce_question_keywords,
    detect_required_data,
    query_mode,
)
from activegraph_memory.settings import MemorySettings
from activegraph_memory.types import RetrievalPlan


@behavior(
    name="plan_memory_retrieval",
    on=["object.created"],
    where={"object.type": "memory_query"},
    creates=["retrieval_plan"],
)
def plan_memory_retrieval(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_retrieval_planning:
        return
    q = event.payload.get("object", {})
    q_id = q.get("id")
    data = q.get("data") or {}
    question = (data.get("question") or "").strip()
    if not (q_id and question):
        return

    requested_types = data.get("memory_types") or []
    mode = data.get("mode") or query_mode(question)
    required = list(data.get("required_data") or []) + detect_required_data(question)
    # de-dupe while preserving order
    seen = set()
    required = [r for r in required if not (r in seen or seen.add(r))]

    plan = RetrievalPlan(
        query_id=q_id,
        keywords=coerce_question_keywords(question),
        vector_queries=[question] if settings.enable_vector_retrieval else [],
        memory_types=requested_types,
        mode=mode,
        required_data=required,
        filters={},
        metadata={"policy": settings.default_policy_name},
    )
    graph.add_object("retrieval_plan", plan.model_dump())
