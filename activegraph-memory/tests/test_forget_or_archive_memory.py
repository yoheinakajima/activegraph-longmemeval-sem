"""Forget and archive requests transition memory status without deleting the object."""
from __future__ import annotations


def _one_claim(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat",
    })
    runtime.run_until_idle()
    return next(o for o in graph.all_objects() if o.type == "memory_claim")


def test_archive_request(graph, runtime):
    claim = _one_claim(graph, runtime)
    graph.add_object("memory_archive_request", {"memory_id": claim.id, "reason": "stale"})
    runtime.run_until_idle()
    assert runtime.errors == []
    updated = graph.get_object(claim.id)
    assert updated.data["status"] == "archived"


def test_forget_request(graph, runtime):
    claim = _one_claim(graph, runtime)
    graph.add_object("memory_forget_request", {"memory_id": claim.id, "reason": "pii"})
    runtime.run_until_idle()
    assert runtime.errors == []
    updated = graph.get_object(claim.id)
    assert updated.data["status"] == "deleted"
    # The memory object still exists for audit (only status changed)
    assert updated is not None
