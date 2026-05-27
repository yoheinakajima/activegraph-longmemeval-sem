"""Shared fixtures for activegraph-memory tests."""
from __future__ import annotations

import pytest

from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings


@pytest.fixture
def graph():
    return Graph()


@pytest.fixture
def runtime(graph):
    rt = Runtime(graph)
    rt.load_pack(pack, settings=MemorySettings())
    return rt


@pytest.fixture
def memory_pack():
    return pack
