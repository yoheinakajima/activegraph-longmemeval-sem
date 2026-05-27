"""Procedural memories ("always do X") are extracted and applied to answers."""
from __future__ import annotations

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


def main() -> None:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings())

    g.add_object("memory_observation", {
        "actor": "user",
        "content": "When writing X posts for Yohei, always use lowercase and avoid em dashes.",
        "source": "chat",
    })
    rt.run_until_idle()

    g.add_object("memory_query", {
        "question": "Draft an X post for Yohei about a product launch.",
        "mode": "standard",
    })
    rt.run_until_idle()

    answer = next(o for o in g.all_objects() if o.type == "memory_answer")
    procs = [o for o in g.all_objects() if o.type == "procedural_memory"]
    print("procedural memories extracted:")
    for p in procs:
        print("  -", p.data["content"])
    print("\nanswer used memory ids:", answer.data["used_memory_ids"])


if __name__ == "__main__":
    main()
