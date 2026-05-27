"""Two graph instances with different MemorySettings produce different memory volumes."""
from __future__ import annotations

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


OBSERVATIONS = [
    "Yohei prefers lowercase X posts and dislikes em dashes.",
    "I think maybe the fund has around $250 million in reserves.",
    "She might have said the meeting is on Tuesday.",
    "Apparently Alice prefers shorter emails.",
]


def _run(threshold: float) -> dict:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings(extraction_confidence_threshold=threshold))
    for c in OBSERVATIONS:
        g.add_object("memory_observation", {"actor": "user", "content": c, "source": "chat"})
        rt.run_until_idle()
    assert rt.errors == []
    return {
        "claims": sum(1 for o in g.all_objects() if o.type == "memory_claim"),
        "episodic": sum(1 for o in g.all_objects() if o.type == "episodic_memory"),
        "procedural": sum(1 for o in g.all_objects() if o.type == "procedural_memory"),
    }


def test_aggressive_extracts_at_least_as_many_as_conservative():
    conservative = _run(threshold=0.85)
    aggressive = _run(threshold=0.4)
    total_c = sum(conservative.values())
    total_a = sum(aggressive.values())
    assert total_a >= total_c
