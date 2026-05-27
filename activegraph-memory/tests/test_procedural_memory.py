"""Procedural memory extraction and application in answers."""
from __future__ import annotations


def test_procedural_extracted_and_applied(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user",
        "content": "When writing X posts for Yohei, always use lowercase and avoid em dashes.",
        "source": "chat",
    })
    runtime.run_until_idle()
    assert runtime.errors == []
    procs = [o for o in graph.all_objects() if o.type == "procedural_memory"]
    assert procs, "procedural memory should be extracted"

    graph.add_object("memory_query", {
        "question": "Help me write an X post for Yohei.",
        "mode": "standard",
    })
    runtime.run_until_idle()
    assert runtime.errors == []
    answers = [o for o in graph.all_objects() if o.type == "memory_answer"]
    assert answers
    assert any(p.id in (answers[-1].data.get("used_memory_ids") or []) for p in procs)
