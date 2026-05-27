"""Retrieved memories must be linked to their query and to source observations."""
from __future__ import annotations


def test_retrieval_links_back_to_query_and_observation(graph, runtime):
    obs = graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei lives in Tokyo.", "source": "chat",
    })
    runtime.run_until_idle()
    q = graph.add_object("memory_query", {"question": "Where does Yohei live?", "mode": "standard"})
    runtime.run_until_idle()
    assert runtime.errors == []

    rels = graph.all_relations()
    # retrieved_for from claim to query
    assert any(r.type == "retrieved_for" and r.target == q.id for r in rels)
    # derived_from from claim to observation
    assert any(r.type == "derived_from" and r.target == obs.id for r in rels)
