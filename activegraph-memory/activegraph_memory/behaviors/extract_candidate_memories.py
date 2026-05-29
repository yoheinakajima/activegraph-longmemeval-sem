"""Behavior 1 — extract_candidate_memories.

Trigger: ``object.created`` where ``object.type == "memory_observation"``.

For each new observation, decide whether it contains durable memories. Create
one memory object per durable fact and wire provenance edges:
``memory -[derived_from]-> observation`` and ``observation -[supports]-> memory``.

Two extraction paths share the same node-creation + provenance logic:

* **Deterministic heuristic (default, offline):** :func:`classify_observation`
  proposes exactly one memory per observation. Used whenever no extractor is
  installed, so the pack runs offline and tests stay deterministic.
* **Injected provider (e.g. LLM):** when a caller installs an extractor via
  ``set_active_extractor``, it may propose zero or many memories per observation
  using ``prompts/extract_candidate_memories.md``. The caller (the harness) owns
  the model + any caching; the pack stays key-agnostic.

When ``enable_concept_graph`` is set, each created memory is additionally linked
to one or more canonical ``memory_concept`` nodes via ``about_entity``. Concept
names come from the extractor (``mem.concepts``) when provided, else a
deterministic derivation from the memory's text. Concepts are deduped by
normalized name within the graph, so repeated mentions share one node. The
concept layer is inert (no nodes, no edges) when the flag is off — the default —
so flat retrieval and the reader are unaffected.
"""

from __future__ import annotations

from activegraph.packs import behavior

from activegraph_memory.behaviors._helpers import classify_observation
from activegraph_memory.constants import CONCEPT_TYPE, STATUS_ACTIVE
from activegraph_memory.settings import MemorySettings
from activegraph_memory.tools.concepts import concepts_for_memory, normalize_concept
from activegraph_memory.tools.extraction import ExtractedMemory, get_active_extractor
from activegraph_memory.types import (
    EpisodicMemory,
    MemoryClaim,
    MemoryConcept,
    ProceduralMemory,
)


def _create_memory(graph, settings, obs_id, mem: ExtractedMemory, data):
    """Create the node for one extracted memory and return its id (or None)."""
    md = data.get("metadata", {}) or {}

    if mem.memory_type == "procedural" and settings.enable_procedural_memory:
        created = graph.add_object(
            "procedural_memory",
            ProceduralMemory(
                content=mem.content,
                applies_to=list(md.get("applies_to", [])),
                priority=int(md.get("priority", 0)),
                confidence=mem.confidence,
                status=STATUS_ACTIVE,
                metadata={"source_observation_id": obs_id},
            ).model_dump(),
        )
        return created.id

    if mem.memory_type == "episodic" and settings.enable_episodic_memory:
        created = graph.add_object(
            "episodic_memory",
            EpisodicMemory(
                content=mem.content,
                occurred_at=data.get("occurred_at"),
                actors=([data["actor"]] if data.get("actor") else []),
                entities=[],
                source=data.get("source"),
                confidence=mem.confidence,
                status=STATUS_ACTIVE,
                metadata={"source_observation_id": obs_id},
            ).model_dump(),
        )
        return created.id

    if mem.memory_type not in ("procedural", "episodic") and settings.enable_semantic_memory:
        created = graph.add_object(
            "memory_claim",
            MemoryClaim(
                content=mem.content,
                confidence=mem.confidence,
                status=STATUS_ACTIVE,
                metadata={"source_observation_id": obs_id},
            ).model_dump(),
        )
        return created.id

    return None


def _build_concept_index(ctx) -> dict[str, str]:
    """normalized concept name -> concept object id, for concepts already in the
    graph. Updated in place as new concepts are created this call so repeated
    mentions within one observation share a single node."""
    index: dict[str, str] = {}
    for c in ctx.view.objects(type=CONCEPT_TYPE):
        cdata = c.data or {}
        norm = cdata.get("normalized") or normalize_concept(cdata.get("name", ""))
        if norm and norm not in index:
            index[norm] = c.id
    return index


def _link_concepts(graph, settings, index, mem_id, mem: ExtractedMemory):
    """Create/reuse concept nodes for a memory and link via ``about_entity``."""
    names = list(mem.concepts) if getattr(mem, "concepts", None) else \
        concepts_for_memory(
            mem.content, mem.memory_type,
            max_concepts=settings.max_concepts_per_memory,
        )
    kind = "topic" if mem.memory_type == "procedural" else "entity"
    for name in names[: settings.max_concepts_per_memory]:
        norm = normalize_concept(name)
        if not norm:
            continue
        cid = index.get(norm)
        if cid is None:
            created = graph.add_object(
                CONCEPT_TYPE,
                MemoryConcept(name=name, kind=kind, normalized=norm).model_dump(),
            )
            cid = created.id
            index[norm] = cid
        graph.add_relation(mem_id, cid, "about_entity")


@behavior(
    name="extract_candidate_memories",
    on=["object.created"],
    where={"object.type": "memory_observation"},
    creates=["memory_claim", "episodic_memory", "procedural_memory", "memory_concept"],
)
def extract_candidate_memories(event, graph, ctx, *, settings: MemorySettings):
    obs = event.payload.get("object", {})
    obs_id = obs.get("id")
    data = obs.get("data") or {}
    content = (data.get("content") or "").strip()
    if not content or obs_id is None:
        return

    extractor = get_active_extractor()
    if extractor is None:
        # Deterministic heuristic: exactly one memory per observation.
        candidates = [ExtractedMemory(classify_observation(content), content, 0.85)]
    else:
        candidates = extractor.extract(content, dict(data.get("metadata", {}) or {})) or []

    concept_index = _build_concept_index(ctx) if settings.enable_concept_graph else None

    for mem in candidates:
        if not (mem.content or "").strip():
            continue
        if mem.confidence < settings.extraction_confidence_threshold:
            continue
        created_id = _create_memory(graph, settings, obs_id, mem, data)
        if created_id is None:
            continue
        # Provenance edges: memory -[derived_from]-> observation,
        # and observation -[supports]-> memory.
        graph.add_relation(created_id, obs_id, "derived_from")
        graph.add_relation(obs_id, created_id, "supports")
        if concept_index is not None:
            _link_concepts(graph, settings, concept_index, created_id, mem)
