"""activegraph-memory — an ActiveGraph pack for event-sourced memory lifecycle.

Memory is not a passive store. It is graph state that evolves through
observation -> extraction -> evidence -> retrieval -> answer -> evaluation.
Every transition is an event in the ActiveGraph log; every memory carries
provenance to its source observation.

Public surface:
    from activegraph_memory import pack, MemorySettings

The pack is also discoverable via ActiveGraph's entry-point registry:
    from activegraph.packs import load_by_name
    load_by_name("memory")
"""

from __future__ import annotations

from pathlib import Path

from activegraph.packs import Pack, load_prompts_from_dir

from activegraph_memory.behaviors import BEHAVIORS
from activegraph_memory.relations import RELATION_TYPES
from activegraph_memory.settings import MemorySettings
from activegraph_memory.tools import TOOLS
from activegraph_memory.types import OBJECT_TYPES

_PROMPTS_DIR = Path(__file__).parent / "prompts"

pack = Pack(
    name="memory",
    version="0.1.0",
    description=(
        "Event-sourced memory lifecycle: observation -> extraction "
        "-> evidence -> retrieval -> answer -> evaluation. Memories "
        "are graph objects with provenance; behaviors evolve memory "
        "state in response to events."
    ),
    object_types=tuple(OBJECT_TYPES),
    relation_types=tuple(RELATION_TYPES),
    behaviors=tuple(BEHAVIORS),
    tools=tuple(TOOLS),
    prompts=load_prompts_from_dir(_PROMPTS_DIR),
    settings_schema=MemorySettings,
)

__all__ = ["pack", "MemorySettings"]
