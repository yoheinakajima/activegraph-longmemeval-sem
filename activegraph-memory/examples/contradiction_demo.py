"""Demonstrate contradiction detection and supersession of older memories."""
from __future__ import annotations

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


def main() -> None:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings())

    g.add_object("memory_observation", {
        "actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat",
    })
    rt.run_until_idle()
    g.add_object("memory_observation", {
        "actor": "user",
        "content": "Update: Yohei now lives in San Francisco, not Tokyo.",
        "source": "chat",
    })
    rt.run_until_idle()

    assert rt.errors == [], rt.errors
    for o in g.all_objects():
        if o.type == "memory_claim":
            print(f"{o.id} [{o.data['status']}] {o.data['content']}")
    print("\nedges:")
    for r in g.all_relations():
        if r.type in ("supersedes", "contradicts"):
            print(f"  {r.source} -[{r.type}]-> {r.target}")


if __name__ == "__main__":
    main()
