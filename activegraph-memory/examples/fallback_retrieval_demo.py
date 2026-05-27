"""When a query requires numeric data and the standard hits don't carry it,
the fallback behavior runs a focused re-search."""
from __future__ import annotations

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


def main() -> None:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings())

    g.add_object("memory_observation", {
        "actor": "user",
        "content": "The fund has $250 million in reserves.",
        "source": "chat",
    })
    rt.run_until_idle()

    g.add_object("memory_query", {
        "question": "What are the fund reserves?",
        "mode": "standard",
        "required_data": ["numeric_value"],
    })
    rt.run_until_idle()

    results = [o for o in g.all_objects() if o.type == "memory_retrieval_result"]
    for r in results:
        d = r.data
        print(f"result confidence={d['confidence']} "
              f"missing={d.get('missing_data')} "
              f"fallback={d.get('metadata', {}).get('is_fallback')}")


if __name__ == "__main__":
    main()
