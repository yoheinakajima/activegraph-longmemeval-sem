"""Each memory_answer is automatically evaluated."""
from __future__ import annotations

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


def main() -> None:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings())

    g.add_object("memory_observation", {
        "actor": "user", "content": "Yohei prefers lowercase.", "source": "chat",
    })
    rt.run_until_idle()
    g.add_object("memory_query", {"question": "How should I write for Yohei?", "mode": "standard"})
    rt.run_until_idle()

    for o in g.all_objects():
        if o.type == "memory_evaluation":
            d = o.data
            print(f"outcome={d.get('outcome')} score={d.get('score')} notes={d.get('notes')!r}")


if __name__ == "__main__":
    main()
