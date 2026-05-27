"""Phase 1 — verify the pack is discoverable and registers cleanly."""
from __future__ import annotations

from activegraph_memory import pack, MemorySettings


def test_pack_metadata():
    assert pack.name == "memory"
    assert pack.version
    assert pack.object_types
    assert pack.relation_types
    assert pack.behaviors


def test_pack_loads_into_runtime(runtime):
    # If `runtime` fixture builds without raising, the pack registered.
    assert runtime is not None


def test_settings_defaults():
    s = MemorySettings()
    assert 0.0 <= s.extraction_confidence_threshold <= 1.0
    assert s.retrieval_limit > 0


def test_pack_has_expected_object_types(memory_pack):
    type_names = {o.name for o in memory_pack.object_types}
    expected = {
        "memory_observation", "memory_claim", "episodic_memory",
        "procedural_memory", "memory_query", "retrieval_plan",
        "memory_retrieval_result", "memory_answer", "quantity_claim",
        "temporal_ref", "memory_consolidation", "memory_evaluation",
        "memory_policy", "memory_archive_request", "memory_forget_request",
    }
    missing = expected - type_names
    assert not missing, f"missing object types: {missing}"


def test_pack_has_expected_relation_types(memory_pack):
    rel_names = {r.name for r in memory_pack.relation_types}
    expected = {
        "derived_from", "supports", "contradicts", "supersedes",
        "retrieved_for", "used_in_answer", "has_quantity",
        "has_temporal_ref", "validated_by", "invalidated_by",
        "consolidated_into", "governed_by_policy",
    }
    missing = expected - rel_names
    assert not missing, f"missing relation types: {missing}"
