"""Temporal references in observations become temporal_ref objects."""
from __future__ import annotations

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


def main() -> None:
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings())

    for content in [
        "I had a meeting yesterday with Alice.",
        "We launched on May 26 2026.",
        "Q1 2026 was strong.",
    ]:
        g.add_object("memory_observation", {"actor": "user", "content": content, "source": "chat"})
        rt.run_until_idle()

    print("temporal refs:")
    for o in g.all_objects():
        if o.type == "temporal_ref":
            print(f"  text={o.data['text']!r} "
                  f"resolved_at={o.data.get('resolved_at')} "
                  f"method={o.data.get('resolution_method')}")


if __name__ == "__main__":
    main()
