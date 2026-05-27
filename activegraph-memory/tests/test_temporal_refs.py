"""Temporal references are extracted into temporal_ref objects with has_temporal_ref edges."""
from __future__ import annotations


def test_temporal_extraction(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "I had a meeting yesterday with Alice.", "source": "chat",
    })
    runtime.run_until_idle()
    assert runtime.errors == []
    refs = [o for o in graph.all_objects() if o.type == "temporal_ref"]
    assert refs, "temporal_ref should be extracted"
    rels = [r for r in graph.all_relations() if r.type == "has_temporal_ref"]
    assert rels, "has_temporal_ref edge should exist"


def test_temporal_resolution_method(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "We met on May 26 2026.", "source": "chat",
    })
    runtime.run_until_idle()
    refs = [o for o in graph.all_objects() if o.type == "temporal_ref"]
    assert refs
    methods = {(r.data or {}).get("resolution_method") for r in refs}
    assert methods & {"absolute", "relative", "unresolved"}
