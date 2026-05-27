"""A memory_query produces a retrieval_plan with sensible keywords."""
from __future__ import annotations


def test_query_creates_plan(graph, runtime):
    graph.add_object("memory_query", {
        "question": "Where does Yohei live now?",
        "mode": "standard",
    })
    runtime.run_until_idle()
    assert runtime.errors == []
    plans = [o for o in graph.all_objects() if o.type == "retrieval_plan"]
    assert len(plans) == 1
    data = plans[0].data
    assert data["mode"] in ("standard", "deep")
    assert any("yohei" in k.lower() for k in data["keywords"])
