"""Quantities in observations become scoped quantity_claim objects."""
from __future__ import annotations

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


def main() -> None:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings())

    for content in [
        "The fund has $250 million in reserves as of Q1 2026.",
        "Acme grew revenue 35% year-over-year.",
        "The dataset contains 12,000 examples.",
    ]:
        g.add_object("memory_observation", {"actor": "user", "content": content, "source": "chat"})
        rt.run_until_idle()

    for o in g.all_objects():
        if o.type == "quantity_claim":
            d = o.data
            print(f"raw={d['raw_value']!r} value={d.get('value')} "
                  f"unit={d.get('unit')!r} exactness={d.get('exactness')}")


if __name__ == "__main__":
    main()
