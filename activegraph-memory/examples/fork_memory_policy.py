"""Two graph instances with different extraction thresholds form a memory
policy comparison: the aggressive policy retains more candidate memories
from the same observation stream than the conservative policy.

If/when ActiveGraph exposes a first-class fork/diff API, this example
can be rewritten to fork a single graph instead of running two copies.
"""
from __future__ import annotations

from collections import Counter

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


OBSERVATIONS = [
    "Yohei prefers lowercase X posts and dislikes em dashes.",
    "I think the fund might have around $250 million in reserves.",
    "She might have said the meeting is on Tuesday.",
    "Apparently Alice prefers shorter emails.",
]


def run(label: str, threshold: float) -> dict:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings(extraction_confidence_threshold=threshold))
    for c in OBSERVATIONS:
        g.add_object("memory_observation", {"actor": "user", "content": c, "source": "chat"})
        rt.run_until_idle()
    types = Counter(o.type for o in g.all_objects())
    print(f"\n[{label}] threshold={threshold}")
    print(f"  memory_claim:       {types['memory_claim']}")
    print(f"  episodic_memory:    {types['episodic_memory']}")
    print(f"  procedural_memory:  {types['procedural_memory']}")
    print(f"  total memories:     {types['memory_claim'] + types['episodic_memory'] + types['procedural_memory']}")
    return dict(types)


def main() -> None:
    conservative = run("conservative", threshold=0.85)
    aggressive = run("aggressive", threshold=0.4)
    keys = ("memory_claim", "episodic_memory", "procedural_memory")
    delta_total = (
        sum(aggressive.get(k, 0) for k in keys)
        - sum(conservative.get(k, 0) for k in keys)
    )
    print(f"\naggressive extracted {delta_total} more memories than conservative")


if __name__ == "__main__":
    main()
