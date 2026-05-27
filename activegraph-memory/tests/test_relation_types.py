"""Phase 2 — all declared relations register in the pack."""
from __future__ import annotations

import pytest

from activegraph_memory import pack

RELS = [
    "derived_from", "supports", "contradicts", "supersedes",
    "retrieved_for", "used_in_answer", "has_quantity",
    "has_temporal_ref", "validated_by", "invalidated_by",
    "consolidated_into", "governed_by_policy",
]


@pytest.mark.parametrize("rel", RELS)
def test_relation_registers(rel):
    names = {r.name for r in pack.relation_types}
    assert rel in names


def test_can_add_derived_from(graph, runtime):
    obs = graph.add_object("memory_observation", {"actor": "u", "content": "x", "source": "chat"})
    claim = graph.add_object("memory_claim", {"content": "x", "status": "active", "confidence": 0.9})
    r = graph.add_relation(claim.id, obs.id, "derived_from")
    assert r.type == "derived_from"
