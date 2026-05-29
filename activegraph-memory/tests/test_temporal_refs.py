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


def test_duration_start_resolution():
    """Ongoing-duration phrases resolve to the activity's START date
    (anchor - N units) so 'how long had I been doing X' becomes subtraction."""
    from datetime import datetime
    from activegraph_memory.behaviors._helpers import (
        find_temporal_refs, resolve_temporal,
    )

    anchor = datetime(2023, 5, 25)
    refs = [m for m in find_temporal_refs(
        "I've been taking weekly guitar lessons for six weeks now"
    ) if m["kind"] == "duration"]
    assert refs, "duration phrase should be detected"
    res = resolve_temporal(refs[0], anchor)
    assert res["resolution_method"] == "duration_start"
    assert res["resolved_at"] == datetime(2023, 4, 13)  # 6 weeks before anchor

    res2 = resolve_temporal(
        [m for m in find_temporal_refs("getting into bird watching for about three months")
         if m["kind"] == "duration"][0],
        datetime(2023, 5, 21),
    )
    assert res2["resolution_method"] == "duration_start"
    assert res2["resolved_at"] == datetime(2023, 2, 21)  # 3 months before anchor
