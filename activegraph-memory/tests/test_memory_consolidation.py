"""Duplicate memories get consolidated into a memory_consolidation object."""
from __future__ import annotations


def test_duplicate_memories_consolidate(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei dislikes em dashes.", "source": "chat",
    })
    runtime.run_until_idle()
    graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei dislikes em dashes.", "source": "chat",
    })
    runtime.run_until_idle()
    assert runtime.errors == []
    cons = [o for o in graph.all_objects() if o.type == "memory_consolidation"]
    assert cons, "consolidation should fire on duplicate content"
    rels = [r for r in graph.all_relations() if r.type == "consolidated_into"]
    assert rels
