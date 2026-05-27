"""Contradiction detection + supersession patches old memory status."""
from __future__ import annotations


def test_explicit_supersession(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat",
    })
    runtime.run_until_idle()
    graph.add_object("memory_observation", {
        "actor": "user",
        "content": "Update: Yohei now lives in San Francisco, not Tokyo.",
        "source": "chat",
    })
    runtime.run_until_idle()
    assert runtime.errors == []

    claims = [o for o in graph.all_objects() if o.type == "memory_claim"]
    statuses = [c.data.get("status") for c in claims]
    # At least one superseded or needs_review
    assert any(s in ("superseded", "needs_review") for s in statuses)
    rel_types = {r.type for r in graph.all_relations()}
    assert "supersedes" in rel_types or "contradicts" in rel_types

    # No memory was deleted
    assert len(claims) >= 2
