"""Agentic retrieval controller — pluggable, flag-gated, offline.

The default flat path is unchanged; the agentic path is exercised end-to-end
through the runtime and the controller is unit-tested directly. All offline
(deterministic embeddings, no extractor).
"""
from __future__ import annotations

import pytest

from activegraph import Graph, Runtime
from activegraph_memory import MemorySettings, pack
from activegraph_memory.constants import CONCEPT_TYPE, MEMORY_TYPES
from activegraph_memory.tools.retrieval import (
    DefaultAgenticController,
    RetrievalDecision,
    RetrievalTools,
    get_active_retrieval_controller,
    set_active_retrieval_controller,
)


@pytest.fixture(autouse=True)
def _reset_controller():
    """Process-global injectable must not leak across tests."""
    set_active_retrieval_controller(None)
    yield
    set_active_retrieval_controller(None)


def _runtime(**settings_kwargs):
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings(**settings_kwargs))
    return g, rt


def _latest_retrieval(g):
    rs = [o for o in g.all_objects() if o.type == "memory_retrieval_result"]
    return max(rs, key=lambda o: int(o.id.rsplit("#", 1)[1])) if rs else None


def test_agentic_path_retrieves_via_concepts():
    g, rt = _runtime(enable_concept_graph=True, retrieval_strategy="agentic")
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()
    g.add_object("memory_query",
                 {"question": "Where does Yohei live?", "mode": "standard"})
    rt.run_until_idle()
    assert rt.errors == []

    retrieval = _latest_retrieval(g)
    assert retrieval is not None
    assert (retrieval.data.get("metadata") or {}).get("strategy") == "agentic"

    retrieved = retrieval.data.get("retrieved_object_ids") or []
    assert retrieved, "agentic retrieval should surface the linked fact"
    by_id = {o.id: o for o in g.all_objects()}
    # Only real memories are retrieved — concept nodes never leak into results.
    assert all(by_id[r].type in MEMORY_TYPES for r in retrieved)


def test_agentic_degrades_to_fact_search_without_concepts():
    # Concept graph OFF, but strategy agentic: loop must fall back to direct
    # fact search and still return results.
    g, rt = _runtime(enable_concept_graph=False, retrieval_strategy="agentic")
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()
    assert not [o for o in g.all_objects() if o.type == CONCEPT_TYPE]
    g.add_object("memory_query",
                 {"question": "Where does Yohei live?", "mode": "standard"})
    rt.run_until_idle()
    assert rt.errors == []

    retrieval = _latest_retrieval(g)
    assert retrieval is not None
    assert retrieval.data.get("retrieved_object_ids")


def test_flat_path_has_no_agentic_metadata():
    g, rt = _runtime()  # defaults: flat
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()
    g.add_object("memory_query",
                 {"question": "Where does Yohei live?", "mode": "standard"})
    rt.run_until_idle()
    retrieval = _latest_retrieval(g)
    assert retrieval is not None
    assert (retrieval.data.get("metadata") or {}).get("strategy") != "agentic"


def test_controller_is_pluggable():
    class _Stub:
        def retrieve(self, question, tools, settings):
            return RetrievalDecision(fact_ids=[], confidence=1.0, reasoning="stub")

    assert get_active_retrieval_controller() is None
    set_active_retrieval_controller(_Stub())
    try:
        g, rt = _runtime(enable_concept_graph=True, retrieval_strategy="agentic")
        g.add_object("memory_observation",
                     {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
        rt.run_until_idle()
        g.add_object("memory_query",
                     {"question": "Where does Yohei live?", "mode": "standard"})
        rt.run_until_idle()
        assert rt.errors == []
        retrieval = _latest_retrieval(g)
        assert "stub" in (retrieval.data.get("summary") or "")
    finally:
        set_active_retrieval_controller(None)
    assert get_active_retrieval_controller() is None


def test_controller_returning_bad_ids_is_filtered():
    # A buggy/malicious controller returns a concept id and a non-existent id.
    # The behavior must drop both: no schema violation, no concept leakage.
    concept_ids: list[str] = []

    class _Bad:
        def retrieve(self, question, tools, settings):
            return RetrievalDecision(
                fact_ids=[*concept_ids, "memory_claim#999999"],
                confidence=0.9,
                reasoning="bad",
            )

    g, rt = _runtime(enable_concept_graph=True, retrieval_strategy="agentic")
    g.add_object("memory_observation",
                 {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()
    concept_ids.extend(o.id for o in g.all_objects() if o.type == CONCEPT_TYPE)
    assert concept_ids

    set_active_retrieval_controller(_Bad())
    g.add_object("memory_query",
                 {"question": "Where does Yohei live?", "mode": "standard"})
    rt.run_until_idle()
    assert rt.errors == []

    retrieval = _latest_retrieval(g)
    retrieved = retrieval.data.get("retrieved_object_ids") or []
    # The concept id and the bogus id are both filtered out.
    assert all(r not in concept_ids for r in retrieved)
    assert "memory_claim#999999" not in retrieved
    # No about_entity/concept leaked into retrieved_for edges either.
    by_id = {o.id: o for o in g.all_objects()}
    rel_sources = {r.source for r in g.all_relations() if r.type == "retrieved_for"}
    assert all(by_id[s].type in MEMORY_TYPES for s in rel_sources if s in by_id)


def test_default_controller_unit_concept_then_fallback():
    # Build a tiny graph by hand and drive the controller directly.
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings(enable_concept_graph=True))
    obs = g.add_object("memory_observation",
                       {"actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat"})
    rt.run_until_idle()

    tools = RetrievalTools(g.all_objects(), g.all_relations(), exclude_statuses=[])
    assert tools.n_facts >= 1
    assert tools.n_concepts >= 1

    decision = DefaultAgenticController().retrieve(
        "Where does Yohei live?", tools, MemorySettings()
    )
    assert decision.fact_ids
    assert decision.iterations >= 1
    assert 0.0 <= decision.confidence <= 1.0
