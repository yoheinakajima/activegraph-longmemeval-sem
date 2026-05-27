"""Numeric extraction creates quantity_claim with has_quantity edges."""
from __future__ import annotations


def test_numeric_extraction(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user",
        "content": "The fund has $250 million in reserves as of Q1 2026.",
        "source": "chat",
    })
    runtime.run_until_idle()
    assert runtime.errors == []
    qcs = [o for o in graph.all_objects() if o.type == "quantity_claim"]
    assert qcs
    q = qcs[0].data
    assert q.get("raw_value")
    assert q.get("value") is not None
    rels = [r for r in graph.all_relations() if r.type == "has_quantity"]
    assert rels


def test_no_quantity_for_text_without_numbers(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "I enjoyed the trip.", "source": "chat",
    })
    runtime.run_until_idle()
    qcs = [o for o in graph.all_objects() if o.type == "quantity_claim"]
    assert not qcs
