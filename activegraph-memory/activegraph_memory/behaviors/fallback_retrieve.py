"""Behavior 5 — fallback_retrieve.

Trigger: ``object.created`` where ``object.type == "memory_retrieval_result"``.

When the first result carries non-empty ``missing_data`` (and is not itself a
fallback), build a targeted retrieval plan for each missing item, search, and
emit a second ``memory_retrieval_result`` flagged ``is_fallback=True``. The
new result preserves the original ``query_id``.

The behavior tags fallback results so it does not re-fire on its own output.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.constants import EXCLUDED_FROM_STANDARD_RETRIEVAL
from activegraph_memory.settings import MemorySettings
from activegraph_memory.tools.keyword_search import keyword_search_fn
from activegraph_memory.types import MemoryRetrievalResult


@behavior(
    name="fallback_retrieve",
    on=["object.created"],
    where={"object.type": "memory_retrieval_result"},
    creates=["memory_retrieval_result"],
)
def fallback_retrieve(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_fallback_retrieval:
        return
    res = event.payload.get("object", {})
    data = res.get("data") or {}
    if data.get("metadata", {}).get("is_fallback"):
        return  # do not recurse
    missing = list(data.get("missing_data") or [])
    if not missing:
        return
    query_id = data.get("query_id")
    if not query_id:
        return
    query = graph.get_object(query_id)
    question = ((query.data if query else {}) or {}).get("question", "")

    # Targeted re-search: bias to wider memory_types and broader keyword set
    objects = ctx.view.objects()
    extra_terms = []
    for need in missing:
        if need == "numeric_value":
            extra_terms += ["amount", "number", "target", "size", "reserves"]
        elif need == "temporal_value":
            extra_terms += ["date", "when", "year"]
        else:
            extra_terms.append(need)
    expanded_query = " ".join([question] + extra_terms)

    hits = keyword_search_fn(
        objects, expanded_query,
        memory_types=None,
        exclude_statuses=list(EXCLUDED_FROM_STANDARD_RETRIEVAL),
        limit=settings.fallback_retrieval_limit,
    )
    previous_ids = set(data.get("retrieved_object_ids") or [])
    new_ids = [h.object_id for h in hits if h.object_id not in previous_ids]
    combined_ids = list(previous_ids) + new_ids

    # Recompute satisfaction
    relations = ctx.view.relations()
    still_missing: list[str] = []
    for need in missing:
        ok = False
        if need == "numeric_value":
            ok = any(r.type == "has_quantity" and r.source in combined_ids
                     for r in relations)
        elif need == "temporal_value":
            ok = any(r.type == "has_temporal_ref" and r.source in combined_ids
                     for r in relations)
        else:
            ok = bool(combined_ids)
        if not ok:
            still_missing.append(need)

    fb = MemoryRetrievalResult(
        query_id=query_id,
        plan_id=data.get("plan_id"),
        retrieved_object_ids=combined_ids,
        summary=f"Fallback retrieval added {len(new_ids)} memories.",
        missing_data=still_missing,
        confidence=0.7 if combined_ids and not still_missing else 0.4,
        metadata={"policy": settings.default_policy_name,
                  "is_fallback": True,
                  "previous_result_id": res.get("id")},
    )
    fb_obj = graph.add_object(
        "memory_retrieval_result", fb.model_dump(),
    )
    for oid in combined_ids:
        graph.add_relation(oid, fb_obj.id, "retrieved_for")
