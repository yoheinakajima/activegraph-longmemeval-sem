"""memory_evaluation is created for each memory_answer."""
from __future__ import annotations


def test_evaluation_emitted(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei prefers lowercase.", "source": "chat",
    })
    runtime.run_until_idle()
    graph.add_object("memory_query", {"question": "How should I write for Yohei?", "mode": "standard"})
    runtime.run_until_idle()
    assert runtime.errors == []
    evals = [o for o in graph.all_objects() if o.type == "memory_evaluation"]
    assert evals
    ev = evals[-1].data
    assert ev["outcome"] in ("helpful", "unhelpful", "incorrect",
                              "unsupported", "partially_helpful", "unknown")
    rels = [r for r in graph.all_relations() if r.type in ("validated_by", "invalidated_by")]
    assert rels
