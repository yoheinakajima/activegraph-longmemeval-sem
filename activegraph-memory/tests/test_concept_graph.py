"""Concept graph (entity/topic layer) — extraction, linking, dedup.

All offline and deterministic: no extractor installed, so the deterministic
concept derivation runs. The layer is gated by ``enable_concept_graph``.
"""
from __future__ import annotations

import pytest

from activegraph import Graph, Runtime
from activegraph_memory import MemorySettings, pack
from activegraph_memory.constants import CONCEPT_TYPE
from activegraph_memory.tools.concepts import (
    deterministic_concepts,
    normalize_concept,
)


def _runtime(**settings_kwargs):
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings(**settings_kwargs))
    return g, rt


def test_deterministic_concepts_extracts_entities():
    names = deterministic_concepts("Yohei lives in Tokyo and works at OpenAI.")
    norms = {normalize_concept(n) for n in names}
    assert "yohei" in norms
    assert "tokyo" in norms
    assert "openai" in norms


def test_concepts_disabled_by_default():
    g, rt = _runtime()  # enable_concept_graph defaults False
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()
    assert rt.errors == []
    assert not [o for o in g.all_objects() if o.type == CONCEPT_TYPE]
    assert not [r for r in g.all_relations() if r.type == "about_entity"]


def test_concept_nodes_and_links_created_when_enabled():
    g, rt = _runtime(enable_concept_graph=True)
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()
    assert rt.errors == []

    concepts = [o for o in g.all_objects() if o.type == CONCEPT_TYPE]
    norms = {(o.data or {}).get("normalized") for o in concepts}
    assert "tokyo" in norms
    assert "yohei" in norms

    # Each concept is linked from the memory via about_entity.
    about = [r for r in g.all_relations() if r.type == "about_entity"]
    assert about
    concept_ids = {o.id for o in concepts}
    assert all(r.target in concept_ids for r in about)


def test_concepts_deduped_across_observations():
    g, rt = _runtime(enable_concept_graph=True)
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei visited Tokyo again.", "source": "chat"})
    rt.run_until_idle()
    assert rt.errors == []

    tokyo = [o for o in g.all_objects()
             if o.type == CONCEPT_TYPE and (o.data or {}).get("normalized") == "tokyo"]
    assert len(tokyo) == 1, "the same entity must canonicalize to one concept node"


def test_max_concepts_per_memory_respected():
    g, rt = _runtime(enable_concept_graph=True, max_concepts_per_memory=2)
    g.add_object("memory_observation", {
        "actor": "user",
        "content": "Alice Bob Carol Dave Eve all met in London during March.",
        "source": "chat",
    })
    rt.run_until_idle()
    assert rt.errors == []
    about = [r for r in g.all_relations() if r.type == "about_entity"]
    assert 0 < len(about) <= 2
