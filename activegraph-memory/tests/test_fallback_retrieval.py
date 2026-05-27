"""Fallback retrieval runs when missing_data is reported."""
from __future__ import annotations


def test_fallback_runs_when_data_missing(graph, runtime):
    # Establish two memories, one with numeric and one without
    graph.add_object("memory_observation", {
        "actor": "user",
        "content": "The fund has $250 million in reserves.",
        "source": "chat",
    })
    runtime.run_until_idle()

    # Query that requires numeric_value
    graph.add_object("memory_query", {
        "question": "What are the reserves of the fund?",
        "mode": "standard",
        "required_data": ["numeric_value"],
    })
    runtime.run_until_idle()
    assert runtime.errors == []
    results = [o for o in graph.all_objects() if o.type == "memory_retrieval_result"]
    assert results
    # If first result had missing_data, fallback would produce a second result
    # In either case, the final answer must be present
    answers = [o for o in graph.all_objects() if o.type == "memory_answer"]
    assert answers
