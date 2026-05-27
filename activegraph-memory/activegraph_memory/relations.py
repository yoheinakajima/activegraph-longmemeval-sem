"""Relation types for the memory pack. 12 relations per docs/brief/relation_types.md.

(``about_entity`` and ``same_entity_as`` are deferred — see brief; ActiveGraph
does not have a generic entity object type, and the pack does not introduce one
in v0.1.)
"""

from __future__ import annotations

from activegraph.packs import RelationType

_MEMORY_TYPES = ("memory_claim", "episodic_memory", "procedural_memory")

RELATION_TYPES = [
    RelationType(
        name="derived_from",
        source_types=_MEMORY_TYPES + ("quantity_claim", "temporal_ref"),
        target_types=("memory_observation",),
        description="A memory was extracted from an observation.",
    ),
    RelationType(
        name="supports",
        source_types=("memory_observation",) + _MEMORY_TYPES,
        target_types=_MEMORY_TYPES + ("memory_answer",),
        description="Evidence supports a claim or answer.",
    ),
    RelationType(
        name="contradicts",
        source_types=_MEMORY_TYPES,
        target_types=_MEMORY_TYPES,
        description="Two memories are in conflict.",
    ),
    RelationType(
        name="supersedes",
        source_types=_MEMORY_TYPES,
        target_types=_MEMORY_TYPES,
        description="A new memory replaces an older one.",
    ),
    RelationType(
        name="retrieved_for",
        source_types=_MEMORY_TYPES,
        target_types=("memory_query", "memory_retrieval_result"),
        description="A memory was retrieved for a query/result.",
    ),
    RelationType(
        name="used_in_answer",
        source_types=_MEMORY_TYPES,
        target_types=("memory_answer",),
        description="A memory was used to produce an answer.",
    ),
    RelationType(
        name="has_quantity",
        source_types=_MEMORY_TYPES + ("memory_observation",),
        target_types=("quantity_claim",),
        description="A memory or observation carries a numeric claim.",
    ),
    RelationType(
        name="has_temporal_ref",
        source_types=_MEMORY_TYPES + ("memory_observation",),
        target_types=("temporal_ref",),
        description="A memory or observation references a time.",
    ),
    RelationType(
        name="validated_by",
        source_types=("memory_answer",) + _MEMORY_TYPES,
        target_types=("memory_evaluation",),
        description="An answer/memory was validated by an evaluation.",
    ),
    RelationType(
        name="invalidated_by",
        source_types=("memory_answer",) + _MEMORY_TYPES,
        target_types=("memory_evaluation",),
        description="An answer/memory was invalidated by an evaluation.",
    ),
    RelationType(
        name="consolidated_into",
        source_types=_MEMORY_TYPES,
        target_types=_MEMORY_TYPES + ("memory_consolidation",),
        description="An older memory was rolled into a consolidated memory.",
    ),
    RelationType(
        name="governed_by_policy",
        target_types=("memory_policy",),
        description="An operation was governed by a memory policy.",
    ),
]
