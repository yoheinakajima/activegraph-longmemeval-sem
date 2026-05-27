"""Phase 2 — each object type accepts representative data."""
from __future__ import annotations

import pytest


CASES = [
    ("memory_observation", {"actor": "user", "content": "hi", "source": "chat"}),
    ("memory_claim", {"content": "Yohei prefers lowercase.", "confidence": 0.9, "status": "active"}),
    ("episodic_memory", {"content": "Met Alice on Monday.", "confidence": 0.7, "status": "active"}),
    ("procedural_memory", {"content": "Avoid em dashes.", "confidence": 0.95, "status": "active", "priority": 1}),
    ("memory_query", {"question": "Where does Yohei live?", "mode": "standard"}),
    ("retrieval_plan", {"query_id": "q1", "keywords": ["yohei", "live"], "mode": "standard"}),
    ("memory_retrieval_result", {"query_id": "q1", "plan_id": "p1", "retrieved_object_ids": ["m1"],
                                  "summary": "1 hit", "confidence": 0.8}),
    ("memory_answer", {"query_id": "q1", "retrieval_result_id": "r1", "answer": "ok",
                       "used_memory_ids": ["m1"], "confidence": 0.8}),
    ("quantity_claim", {"raw_value": "$250 million", "value": 250000000.0, "unit": "USD",
                         "exactness": "exact", "confidence": 0.9}),
    ("temporal_ref", {"text": "yesterday", "resolution_method": "relative_to_observation", "confidence": 0.7}),
    ("memory_consolidation", {"source_memory_ids": ["a", "b"], "consolidated_memory_id": "c",
                               "reason": "duplicate", "confidence": 0.9}),
    ("memory_evaluation", {"answer_id": "a1", "query_id": "q1", "used_memory_ids": ["m1"],
                            "outcome": "helpful", "score": 1.0}),
    ("memory_policy", {"name": "conservative"}),
    ("memory_archive_request", {"memory_id": "m1", "reason": "stale"}),
    ("memory_forget_request", {"memory_id": "m1", "reason": "pii"}),
]


@pytest.mark.parametrize("type_name,data", CASES)
def test_can_create(graph, runtime, type_name, data):
    obj = graph.add_object(type_name, data)
    assert obj.id
    assert obj.type == type_name
    for k, v in data.items():
        assert obj.data[k] == v
