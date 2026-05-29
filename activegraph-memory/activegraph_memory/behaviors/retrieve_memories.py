"""Behavior 4 — retrieve_memories.

Trigger: ``object.created`` where ``object.type == "retrieval_plan"``.

Search memory objects using keyword (always) and optional vector search,
filter by status, merge results, and emit a ``memory_retrieval_result``
with ``retrieved_for`` edges from each hit back to the query.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.constants import (
    EXCLUDED_FROM_STANDARD_RETRIEVAL,
    MEMORY_TYPES,
    STATUS_SUPERSEDED,
)
from activegraph_memory.settings import MemorySettings
from activegraph_memory.tools.keyword_search import keyword_search_fn
from activegraph_memory.tools.retrieval import (
    DefaultAgenticController,
    RetrievalTools,
    get_active_retrieval_controller,
)
from activegraph_memory.tools.text_normalize import extract_keywords
from activegraph_memory.tools.vector_search import vector_search_fn
from activegraph_memory.types import MemoryRetrievalResult


def _type_map(t: str) -> str:
    return {"memory_claim": "semantic", "episodic_memory": "episodic",
            "procedural_memory": "procedural"}.get(t, t)


def _expand_types(short_names: list[str]) -> list[str]:
    reverse = {"semantic": "memory_claim", "episodic": "episodic_memory",
               "procedural": "procedural_memory"}
    if not short_names:
        return list(MEMORY_TYPES)
    return [reverse[n] for n in short_names if n in reverse]


def _compute_missing(ctx, required, retrieved_ids) -> list[str]:
    """Required-data gaps: which requested signals no retrieved memory carries."""
    retrieved = set(retrieved_ids)
    missing: list[str] = []
    for need in required or []:
        if need == "numeric_value":
            satisfied = any(
                r.source in retrieved for r in ctx.view.relations(type="has_quantity")
            )
        elif need == "temporal_value":
            satisfied = any(
                r.source in retrieved for r in ctx.view.relations(type="has_temporal_ref")
            )
        else:
            satisfied = bool(retrieved_ids)
        if not satisfied:
            missing.append(need)
    return missing


def _exclude_statuses(settings, plan_data) -> set:
    exclude = set(EXCLUDED_FROM_STANDARD_RETRIEVAL)
    if not settings.include_superseded_in_standard_retrieval and plan_data.get("mode") != "deep":
        exclude.add(STATUS_SUPERSEDED)
    return exclude


def _agentic_retrieve(graph, ctx, settings, plan_id, query_id, plan_data, question):
    """Delegate retrieval to a pluggable controller (concept -> facts loop)."""
    exclude = _exclude_statuses(settings, plan_data)
    tools = RetrievalTools(
        ctx.view.objects(), ctx.view.relations(), exclude_statuses=list(exclude),
    )
    controller = get_active_retrieval_controller() or DefaultAgenticController()
    decision = controller.retrieve(question, tools, settings)

    # The controller boundary is untrusted (a buggy/LLM controller may return
    # concept ids, excluded ids, or non-existent ids). Keep only valid,
    # retrievable memory ids, de-duplicated, preserving the controller's order.
    retrieved_ids: list[str] = []
    seen: set[str] = set()
    for fid in decision.fact_ids:
        if fid in seen or not tools.is_fact(fid):
            continue
        seen.add(fid)
        retrieved_ids.append(fid)

    missing = _compute_missing(ctx, plan_data.get("required_data", []), retrieved_ids)
    confidence = max(0.0, min(1.0, decision.confidence)) if retrieved_ids else 0.2
    if missing:
        confidence = min(confidence, 0.5)

    result = MemoryRetrievalResult(
        query_id=query_id,
        plan_id=plan_id,
        retrieved_object_ids=retrieved_ids,
        summary=f"Agentic retrieval ({decision.reasoning}).",
        missing_data=missing,
        confidence=confidence,
        metadata={
            "policy": settings.default_policy_name,
            "is_fallback": False,
            "strategy": "agentic",
            "iterations": decision.iterations,
        },
    )
    result_obj = graph.add_object("memory_retrieval_result", result.model_dump())
    for oid in retrieved_ids:
        graph.add_relation(oid, result_obj.id, "retrieved_for")
        graph.add_relation(oid, query_id, "retrieved_for")


@behavior(
    name="retrieve_memories",
    on=["object.created"],
    where={"object.type": "retrieval_plan"},
    creates=["memory_retrieval_result"],
)
def retrieve_memories(event, graph, ctx, *, settings: MemorySettings):
    plan = event.payload.get("object", {})
    plan_id = plan.get("id")
    plan_data = plan.get("data") or {}
    query_id = plan_data.get("query_id")
    if not (plan_id and query_id):
        return

    query_obj = graph.get_object(query_id)
    question = ((query_obj.data if query_obj else {}) or {}).get("question", "")

    # Agentic path: delegate to a pluggable controller (concept -> facts loop).
    # Default flat path (keyword + vector blend) is unchanged.
    if settings.retrieval_strategy == "agentic":
        _agentic_retrieve(graph, ctx, settings, plan_id, query_id, plan_data, question)
        return

    keywords = plan_data.get("keywords") or extract_keywords(question)
    types = _expand_types(plan_data.get("memory_types") or [])
    exclude = _exclude_statuses(settings, plan_data)

    objects = ctx.view.objects()
    hits_by_id: dict[str, float] = {}
    if settings.enable_keyword_retrieval:
        for h in keyword_search_fn(
            objects, " ".join(keywords) if keywords else question,
            memory_types=types, exclude_statuses=list(exclude),
            limit=settings.retrieval_limit,
        ):
            hits_by_id[h.object_id] = max(hits_by_id.get(h.object_id, 0.0), h.score)
    if settings.enable_vector_retrieval and plan_data.get("vector_queries"):
        for vq in plan_data["vector_queries"]:
            for h in vector_search_fn(
                objects, vq, memory_types=types,
                exclude_statuses=list(exclude), limit=settings.retrieval_limit,
            ):
                # Blend: vector score weighted lower than exact keyword
                hits_by_id[h.object_id] = max(
                    hits_by_id.get(h.object_id, 0.0), 0.6 * h.score
                )

    # Order: score desc, then id asc for determinism
    ranked = sorted(hits_by_id.items(), key=lambda kv: (-kv[1], kv[0]))
    retrieved_ids = [oid for oid, _ in ranked[: settings.retrieval_limit]]

    # Detect missing data: if plan flagged required_data, check whether any
    # hit carries that signal.
    missing = _compute_missing(ctx, plan_data.get("required_data", []), retrieved_ids)

    result = MemoryRetrievalResult(
        query_id=query_id,
        plan_id=plan_id,
        retrieved_object_ids=retrieved_ids,
        summary=f"Retrieved {len(retrieved_ids)} memories for keywords {keywords}.",
        missing_data=missing,
        confidence=0.9 if retrieved_ids and not missing else 0.5,
        metadata={"policy": settings.default_policy_name, "is_fallback": False},
    )
    result_obj = graph.add_object(
        "memory_retrieval_result", result.model_dump(),
    )

    for oid in retrieved_ids:
        graph.add_relation(oid, result_obj.id, "retrieved_for")
        graph.add_relation(oid, query_id, "retrieved_for")
