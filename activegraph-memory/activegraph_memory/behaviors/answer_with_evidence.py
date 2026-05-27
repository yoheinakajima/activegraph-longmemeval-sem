"""Behavior 6 — answer_with_evidence.

Trigger: ``object.created`` where ``object.type == "memory_retrieval_result"``.

Compose an answer from the retrieved memories. Procedural memories become
style/constraint prefixes; semantic/episodic memories become the body.
If no memories were retrieved or required data is missing, the answer
explicitly says so and populates ``missing_data``.

To avoid double-answering when the fallback retriever fires, this behavior
skips the original retrieval result when its ``missing_data`` is non-empty
(the fallback will produce its own result and that one gets the answer).
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.settings import MemorySettings
from activegraph_memory.types import MemoryAnswer


@behavior(
    name="answer_with_evidence",
    on=["object.created"],
    where={"object.type": "memory_retrieval_result"},
    creates=["memory_answer"],
)
def answer_with_evidence(event, graph, ctx, *, settings: MemorySettings):
    if not settings.enable_answer_generation:
        return
    res = event.payload.get("object", {})
    res_id = res.get("id")
    data = res.get("data") or {}
    query_id = data.get("query_id")
    if not (res_id and query_id):
        return

    missing = list(data.get("missing_data") or [])
    is_fallback = bool(data.get("metadata", {}).get("is_fallback"))
    # If the first pass has missing data, defer to the fallback retriever.
    if missing and not is_fallback and settings.enable_fallback_retrieval:
        return

    retrieved_ids = list(data.get("retrieved_object_ids") or [])
    proc_parts: list[str] = []
    body_parts: list[str] = []
    used: list[str] = []
    evidence: list[str] = []

    for oid in retrieved_ids:
        obj = graph.get_object(oid)
        if obj is None:
            continue
        content = (obj.data or {}).get("content", "")
        if obj.type == "procedural_memory":
            proc_parts.append(content)
        elif obj.type in ("memory_claim", "episodic_memory"):
            body_parts.append(content)
        used.append(oid)
        # Collect evidence ids: source observations supporting this memory
        for r in ctx.view.relations(type="derived_from"):
            if r.source == oid:
                evidence.append(r.target)

    if not retrieved_ids:
        answer_text = (
            "I don't have any stored memory that answers this question."
            if not settings.allow_general_knowledge_in_answers
            else "I don't have stored memory for this; the answer would rely on general knowledge."
        )
    else:
        pieces: list[str] = []
        if proc_parts:
            pieces.append("Style preferences: " + " ".join(proc_parts))
        if body_parts:
            pieces.append(" ".join(body_parts))
        if missing:
            pieces.append("(Missing: " + ", ".join(missing) + ".)")
        answer_text = " ".join(pieces) or "Retrieved memories had no usable content."

    answer = MemoryAnswer(
        query_id=query_id,
        retrieval_result_id=res_id,
        answer=answer_text,
        used_memory_ids=used,
        evidence_ids=list(dict.fromkeys(evidence)),
        missing_data=missing,
        confidence=0.85 if used and not missing else 0.4,
        metadata={"policy": settings.default_policy_name,
                  "from_fallback": is_fallback},
    )
    answer_obj = graph.add_object(
        "memory_answer", answer.model_dump(),
    )
    for mid in used:
        graph.add_relation(mid, answer_obj.id, "used_in_answer")
