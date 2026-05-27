"""memory_answer is grounded in retrieved memories (no hallucination of ids)."""
from __future__ import annotations


def test_answer_uses_retrieved_ids(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat",
    })
    runtime.run_until_idle()
    graph.add_object("memory_query", {"question": "Where does Yohei live?", "mode": "standard"})
    runtime.run_until_idle()
    assert runtime.errors == []
    answers = [o for o in graph.all_objects() if o.type == "memory_answer"]
    results = [o for o in graph.all_objects() if o.type == "memory_retrieval_result"]
    assert answers and results
    used = set(answers[-1].data["used_memory_ids"])
    retrieved = set(results[-1].data["retrieved_object_ids"])
    assert used.issubset(retrieved)


def test_answer_missing_evidence(graph, runtime):
    graph.add_object("memory_query", {"question": "Who is the CEO of OpenAI?", "mode": "standard"})
    runtime.run_until_idle()
    assert runtime.errors == []
    answers = [o for o in graph.all_objects() if o.type == "memory_answer"]
    assert answers
    assert answers[-1].data["confidence"] <= 0.6
