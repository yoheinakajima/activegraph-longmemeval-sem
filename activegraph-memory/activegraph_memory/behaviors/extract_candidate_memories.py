"""Behavior 1 — extract_candidate_memories.

Trigger: ``object.created`` where ``object.type == "memory_observation"``.

For each new observation, decide whether it contains a durable memory.
Create one memory object (procedural, episodic, or semantic) and wire
provenance edges: ``memory -[derived_from]-> observation`` and
``observation -[supports]-> memory``.

Deterministic heuristic in v0.1; a future ``@llm_behavior`` swap can use
``prompts/extract_candidate_memories.md`` with the same I/O shape.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.behaviors._helpers import classify_observation
from activegraph_memory.constants import STATUS_ACTIVE
from activegraph_memory.settings import MemorySettings
from activegraph_memory.types import EpisodicMemory, MemoryClaim, ProceduralMemory


@behavior(
    name="extract_candidate_memories",
    on=["object.created"],
    where={"object.type": "memory_observation"},
    creates=["memory_claim", "episodic_memory", "procedural_memory"],
)
def extract_candidate_memories(event, graph, ctx, *, settings: MemorySettings):
    obs = event.payload.get("object", {})
    obs_id = obs.get("id")
    data = obs.get("data") or {}
    content = (data.get("content") or "").strip()
    if not content or obs_id is None:
        return

    kind = classify_observation(content)
    confidence = 0.85
    if confidence < settings.extraction_confidence_threshold:
        return

    created_id = None

    if kind == "procedural" and settings.enable_procedural_memory:
        created = graph.add_object(
            "procedural_memory",
            ProceduralMemory(
                content=content,
                applies_to=list(data.get("metadata", {}).get("applies_to", [])),
                priority=int(data.get("metadata", {}).get("priority", 0)),
                confidence=confidence,
                status=STATUS_ACTIVE,
                metadata={"source_observation_id": obs_id},
            ).model_dump(),
            
        )
        created_id = created.id

    elif kind == "episodic" and settings.enable_episodic_memory:
        created = graph.add_object(
            "episodic_memory",
            EpisodicMemory(
                content=content,
                occurred_at=data.get("occurred_at"),
                actors=([data["actor"]] if data.get("actor") else []),
                entities=[],
                source=data.get("source"),
                confidence=confidence,
                status=STATUS_ACTIVE,
                metadata={"source_observation_id": obs_id},
            ).model_dump(),
            
        )
        created_id = created.id

    elif settings.enable_semantic_memory:
        created = graph.add_object(
            "memory_claim",
            MemoryClaim(
                content=content,
                confidence=confidence,
                status=STATUS_ACTIVE,
                metadata={"source_observation_id": obs_id},
            ).model_dump(),
            
        )
        created_id = created.id

    if created_id is None:
        return

    # Provenance edges: memory -[derived_from]-> observation,
    # and observation -[supports]-> memory.
    graph.add_relation(created_id, obs_id, "derived_from")
    graph.add_relation(obs_id, created_id, "supports")
