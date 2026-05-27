"""Phase 5 — full end-to-end lifecycle from observation to evaluation."""
from __future__ import annotations


def test_observation_to_evaluation_flow(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user",
        "content": "Yohei prefers lowercase X posts and dislikes em dashes.",
        "source": "chat",
    })
    runtime.run_until_idle()
    graph.add_object("memory_query", {
        "question": "How should I write Yohei's X posts?",
        "mode": "standard",
    })
    runtime.run_until_idle()

    assert runtime.errors == []
    types = {o.type for o in graph.all_objects()}
    assert {
        "memory_observation", "memory_query", "retrieval_plan",
        "memory_retrieval_result", "memory_answer", "memory_evaluation",
    }.issubset(types)

    rel_types = {r.type for r in graph.all_relations()}
    assert {"derived_from", "supports", "retrieved_for", "used_in_answer"}.issubset(rel_types)

    answers = [o for o in graph.all_objects() if o.type == "memory_answer"]
    assert answers and answers[0].data.get("used_memory_ids")
