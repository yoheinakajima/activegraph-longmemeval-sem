"""Strong pluggable reranker — flag-gated, opt-in, offline.

The flat retrieval path is unchanged unless ``enable_rerank`` is on AND a
rerank provider is installed. These tests drive the flat path end-to-end
through the runtime with a deterministic stub provider (no LLM, no key) and
assert: (1) default/off is byte-for-byte the prior flat behavior, (2) the
provider can reorder + trim, (3) a buggy provider cannot inject ids or break
retrieval.
"""
from __future__ import annotations

import pytest

from activegraph import Graph, Runtime
from activegraph_memory import MemorySettings, pack
from activegraph_memory.constants import MEMORY_TYPES
from activegraph_memory.tools.reranker import (
    get_active_reranker,
    set_active_reranker,
)


@pytest.fixture(autouse=True)
def _reset_reranker():
    """Process-global injectable must not leak across tests."""
    set_active_reranker(None)
    yield
    set_active_reranker(None)


def _runtime(**settings_kwargs):
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=MemorySettings(**settings_kwargs))
    return g, rt


def _latest_retrieval(g):
    rs = [o for o in g.all_objects() if o.type == "memory_retrieval_result"]
    return max(rs, key=lambda o: int(o.id.rsplit("#", 1)[1])) if rs else None


_FACTS = [
    "Acme released 500 copies of the debut album worldwide.",
    "Acme signed poster from the debut album hangs on the wall.",
    "Acme debut album was recorded in Berlin.",
    "Acme debut album cover is blue.",
    "Acme debut album tour started in May.",
]
_Q = "How many copies of the debut album were released worldwide?"


def _ingest(g, rt):
    for c in _FACTS:
        g.add_object("memory_observation",
                     {"actor": "user", "content": c, "source": "chat"})
    rt.run_until_idle()


def _retrieve(g, rt):
    g.add_object("memory_query", {"question": _Q, "mode": "standard"})
    rt.run_until_idle()
    return _latest_retrieval(g)


def test_default_off_does_not_call_provider():
    calls: list[str] = []

    class _Spy:
        def rerank(self, question, candidates, limit):
            calls.append(question)
            return [cid for cid, _ in candidates]

    set_active_reranker(_Spy())
    g, rt = _runtime()  # enable_rerank defaults False
    _ingest(g, rt)
    retrieval = _retrieve(g, rt)
    assert rt.errors == []
    assert calls == [], "provider must not be consulted when enable_rerank is off"
    assert retrieval.data.get("retrieved_object_ids")


def test_flag_on_without_provider_is_inert():
    # enable_rerank on but no provider installed -> flat path unchanged.
    g_off, rt_off = _runtime()
    _ingest(g_off, rt_off)
    base_ids = _retrieve(g_off, rt_off).data.get("retrieved_object_ids")

    set_active_reranker(None)
    g_on, rt_on = _runtime(enable_rerank=True)
    _ingest(g_on, rt_on)
    on_ids = _retrieve(g_on, rt_on).data.get("retrieved_object_ids")
    assert on_ids == base_ids


def test_provider_reorders_and_trims():
    class _PutAnswerFirst:
        def rerank(self, question, candidates, limit):
            # Move the "500 copies" fact to the front, drop the rest, honor limit.
            ordered = sorted(
                candidates,
                key=lambda c: (0 if "500 copies" in c[1] else 1),
            )
            return [cid for cid, _ in ordered][:limit]

    set_active_reranker(_PutAnswerFirst())
    g, rt = _runtime(enable_rerank=True, rerank_keep=2)
    _ingest(g, rt)
    retrieval = _retrieve(g, rt)
    assert rt.errors == []
    retrieved = retrieval.data.get("retrieved_object_ids") or []
    assert 0 < len(retrieved) <= 2
    by_id = {o.id: o for o in g.all_objects()}
    assert "500 copies" in (by_id[retrieved[0]].data or {}).get("content", "")
    assert all(by_id[r].type in MEMORY_TYPES for r in retrieved)


def test_buggy_provider_cannot_inject_ids():
    class _Bad:
        def rerank(self, question, candidates, limit):
            return ["memory_claim#999999", "not_a_real_id"]

    set_active_reranker(_Bad())
    g, rt = _runtime(enable_rerank=True)
    _ingest(g, rt)
    retrieval = _retrieve(g, rt)
    assert rt.errors == []
    retrieved = retrieval.data.get("retrieved_object_ids") or []
    # Bogus ids filtered; empty kept-set falls back to the original top-N.
    assert "memory_claim#999999" not in retrieved
    assert "not_a_real_id" not in retrieved
    assert retrieved, "fallback must keep original candidates when nothing valid"
    by_id = {o.id: o for o in g.all_objects()}
    assert all(by_id[r].type in MEMORY_TYPES for r in retrieved)


def test_provider_exception_falls_back_to_top_n():
    class _Raises:
        def rerank(self, question, candidates, limit):
            raise RuntimeError("boom")

    set_active_reranker(_Raises())
    g, rt = _runtime(enable_rerank=True, rerank_keep=3)
    _ingest(g, rt)
    retrieval = _retrieve(g, rt)
    assert rt.errors == []
    retrieved = retrieval.data.get("retrieved_object_ids") or []
    assert 0 < len(retrieved) <= 3


@pytest.mark.parametrize("bad_return", [None, 42, object()])
def test_non_iterable_provider_return_falls_back(bad_return):
    # A malformed provider returns something that isn't a list of ids. The
    # behavior must not crash (no schema violation) — it falls back to top-N.
    class _Malformed:
        def rerank(self, question, candidates, limit):
            return bad_return

    set_active_reranker(_Malformed())
    g, rt = _runtime(enable_rerank=True, rerank_keep=3)
    _ingest(g, rt)
    retrieval = _retrieve(g, rt)
    assert rt.errors == []
    retrieved = retrieval.data.get("retrieved_object_ids") or []
    assert 0 < len(retrieved) <= 3
    by_id = {o.id: o for o in g.all_objects()}
    assert all(by_id[r].type in MEMORY_TYPES for r in retrieved)


def test_reranker_injectable_resets():
    assert get_active_reranker() is None
    sentinel = object()
    set_active_reranker(sentinel)
    assert get_active_reranker() is sentinel
    set_active_reranker(None)
    assert get_active_reranker() is None
