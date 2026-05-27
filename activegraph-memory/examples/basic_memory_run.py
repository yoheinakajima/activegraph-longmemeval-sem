"""End-to-end run of the memory pack: observation → claim → query → answer."""
from __future__ import annotations

from collections import Counter

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


def main() -> None:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings())

    g.add_object("memory_observation", {
        "actor": "user",
        "content": "Yohei prefers lowercase X posts and dislikes em dashes.",
        "source": "chat",
    })
    rt.run_until_idle()

    g.add_object("memory_query", {
        "question": "How should I write Yohei's X posts?",
        "mode": "standard",
    })
    rt.run_until_idle()

    assert rt.errors == [], rt.errors
    print("object types:", dict(Counter(o.type for o in g.all_objects())))
    print("relation types:", dict(Counter(r.type for r in g.all_relations())))
    answer = next(o for o in g.all_objects() if o.type == "memory_answer")
    print("\nanswer:", answer.data.get("answer"))
    print("used memory ids:", answer.data.get("used_memory_ids"))


if __name__ == "__main__":
    main()
