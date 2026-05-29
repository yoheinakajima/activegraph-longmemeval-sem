"""Regression tests for ``CachedLLMExtractor`` cache correctness.

These guard the durable contract of the LLM extraction cache without any
network access or API key:

* A transient failure (``None`` from the LLM call) is never cached and is
  retried with backoff.
* A genuine empty result (``[]``) and non-empty results are cached and re-read
  byte-for-byte identically.
* A cache hit never re-invokes the LLM.
* Confidence is clamped to ``[0, 1]`` and malformed / unexpected JSON shapes
  degrade to an empty extraction (treated as "nothing durable", not failure).

The OpenAI client is constructed with a dummy key (its construction is lazy and
makes no network call); every test either monkeypatches ``_call_llm`` directly
or the underlying ``chat.completions.create`` so nothing ever leaves the box.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from activegraph_memory.tools.extraction import ExtractedMemory
from longmemeval_harness import extraction_cache
from longmemeval_harness.extraction_cache import CachedLLMExtractor


def _make_extractor(tmp_path, **kwargs) -> CachedLLMExtractor:
    return CachedLLMExtractor(
        api_key="test-key",
        cache_path=tmp_path / "extractions.sqlite",
        **kwargs,
    )


def _fake_response(raw: str) -> SimpleNamespace:
    """Mimic the shape the extractor reads: ``r.choices[0].message.content``."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw))]
    )


# -- transient failure handling --------------------------------------------
def test_call_llm_retries_then_returns_none(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path, max_retries=3, backoff_base=0.0)
    monkeypatch.setattr(extraction_cache.time, "sleep", lambda *_: None)

    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        raise RuntimeError("transient network blip")

    monkeypatch.setattr(ex._client.chat.completions, "create", boom)

    assert ex._call_llm("anything") is None
    assert calls["n"] == 3  # retried exactly max_retries times


def test_failure_is_not_cached_and_returns_empty(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    monkeypatch.setattr(ex, "_call_llm", lambda content: None)

    assert ex.extract("some durable fact", {}) == []
    # Nothing was written: the next read still misses, and stats stay at zero.
    assert ex._read("some durable fact") is None
    assert ex.stats() == {"cached_extractions": 0}


def test_failure_then_success_caches_only_success(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)

    state = {"fail": True}

    def flaky(content):
        if state["fail"]:
            return None
        return [ExtractedMemory("semantic", "the sky is blue", 0.9, "stated")]

    monkeypatch.setattr(ex, "_call_llm", flaky)

    assert ex.extract("the sky is blue", {}) == []  # failure: not cached
    assert ex.stats() == {"cached_extractions": 0}

    state["fail"] = False
    got = ex.extract("the sky is blue", {})  # success: cached now
    assert len(got) == 1
    assert ex.stats() == {"cached_extractions": 1}


# -- empty + non-empty results are cached and round-trip --------------------
def test_empty_result_is_cached_and_reread(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    monkeypatch.setattr(ex, "_call_llm", lambda content: [])

    assert ex.extract("just saying hi", {}) == []
    assert ex.stats() == {"cached_extractions": 1}
    # A cached empty list reads back as a (non-None) empty list.
    assert ex._read("just saying hi") == []


def test_non_empty_result_round_trips_identically(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    original = [
        ExtractedMemory("procedural", "always use metric units", 0.95, "rule"),
        ExtractedMemory("episodic", "we shipped on 2026-05-01", 0.7, None),
    ]
    monkeypatch.setattr(ex, "_call_llm", lambda content: list(original))

    first = ex.extract("payload", {})
    assert ex.stats() == {"cached_extractions": 1}

    reread = ex._read("payload")
    assert reread is not None
    for produced, expected in zip(reread, original):
        assert produced.memory_type == expected.memory_type
        assert produced.content == expected.content
        assert produced.confidence == expected.confidence
        assert produced.reason == expected.reason
    # The freshly extracted list and the re-read list agree field-for-field.
    assert [(m.memory_type, m.content, m.confidence, m.reason) for m in first] == [
        (m.memory_type, m.content, m.confidence, m.reason) for m in reread
    ]


# -- cache hits avoid re-calling the LLM -----------------------------------
def test_cache_hit_does_not_invoke_llm(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    calls = {"n": 0}

    def counting(content):
        calls["n"] += 1
        return [ExtractedMemory("semantic", "fact", 0.8, None)]

    monkeypatch.setattr(ex, "_call_llm", counting)

    ex.extract("repeatable content", {})
    ex.extract("repeatable content", {})
    ex.extract("repeatable content", {})

    assert calls["n"] == 1  # only the first miss called the LLM


def test_empty_cache_hit_does_not_invoke_llm(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    calls = {"n": 0}

    def counting(content):
        calls["n"] += 1
        return []

    monkeypatch.setattr(ex, "_call_llm", counting)

    assert ex.extract("nothing durable here", {}) == []
    assert ex.extract("nothing durable here", {}) == []
    assert calls["n"] == 1  # cached empty result short-circuits the second call


# -- parsing: confidence clamping + malformed shapes -----------------------
def _call_with_raw(ex, raw, monkeypatch):
    monkeypatch.setattr(
        ex._client.chat.completions,
        "create",
        lambda *a, **k: _fake_response(raw),
    )
    return ex._call_llm("content")


def test_confidence_is_clamped_to_unit_interval(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    raw = json.dumps(
        {
            "memories": [
                {"memory_type": "semantic", "content": "too high", "confidence": 5.0},
                {"memory_type": "semantic", "content": "too low", "confidence": -3.0},
                {"memory_type": "semantic", "content": "in range", "confidence": 0.4},
            ]
        }
    )
    mems = _call_with_raw(ex, raw, monkeypatch)
    by_content = {m.content: m.confidence for m in mems}
    assert by_content["too high"] == 1.0
    assert by_content["too low"] == 0.0
    assert by_content["in range"] == 0.4


def test_invalid_confidence_falls_back_to_default(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    raw = json.dumps(
        {"memories": [{"content": "no conf", "confidence": "not-a-number"}]}
    )
    mems = _call_with_raw(ex, raw, monkeypatch)
    assert len(mems) == 1
    assert mems[0].confidence == 0.85


def test_unknown_memory_type_degrades_to_semantic(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    raw = json.dumps({"memories": [{"memory_type": "WISHFUL", "content": "x"}]})
    mems = _call_with_raw(ex, raw, monkeypatch)
    assert mems[0].memory_type == "semantic"


def test_empty_content_items_are_skipped(tmp_path, monkeypatch):
    ex = _make_extractor(tmp_path)
    raw = json.dumps(
        {
            "memories": [
                {"memory_type": "semantic", "content": "   "},
                {"memory_type": "semantic", "content": "kept"},
                {"memory_type": "semantic"},
            ]
        }
    )
    mems = _call_with_raw(ex, raw, monkeypatch)
    assert [m.content for m in mems] == ["kept"]


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",          # invalid JSON
        "[]",                        # valid JSON but not an object
        "\"a string\"",             # valid JSON but not an object
        "42",                        # valid JSON but not an object
        "{}",                        # object without "memories"
        json.dumps({"memories": "nope"}),       # "memories" not a list
        json.dumps({"memories": [1, 2, "x"]}),  # list of non-dicts
    ],
)
def test_malformed_shapes_degrade_to_empty_list(tmp_path, monkeypatch, raw):
    ex = _make_extractor(tmp_path)
    mems = _call_with_raw(ex, raw, monkeypatch)
    assert mems == []


def test_malformed_shape_is_cached_as_empty(tmp_path, monkeypatch):
    """A degraded-to-empty parse is a genuine result and must be cached."""
    ex = _make_extractor(tmp_path)
    monkeypatch.setattr(
        ex._client.chat.completions,
        "create",
        lambda *a, **k: _fake_response("garbage"),
    )
    assert ex.extract("weird message", {}) == []
    assert ex.stats() == {"cached_extractions": 1}
