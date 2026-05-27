"""Smoke test: full pipeline runs without any network access or API keys."""
from __future__ import annotations

import os
import socket

import pytest


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _no_socket(*args, **kwargs):
        raise RuntimeError("network calls are not allowed in tests")
    monkeypatch.setattr(socket, "socket", _no_socket)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_full_pipeline_offline(graph, runtime):
    graph.add_object("memory_observation", {
        "actor": "user", "content": "Yohei prefers lowercase.", "source": "chat",
    })
    runtime.run_until_idle()
    graph.add_object("memory_query", {"question": "How should I write for Yohei?", "mode": "standard"})
    runtime.run_until_idle()
    assert runtime.errors == []
    assert any(o.type == "memory_answer" for o in graph.all_objects())
