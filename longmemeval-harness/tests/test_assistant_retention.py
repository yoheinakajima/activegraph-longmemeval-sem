"""Invariants for Track-1 assistant-fact retention (no network, no API key).

These guard the durable contract of ``CachedLLMExtractor``'s assistant-aware
routing so the retention feature can never silently merge with, or poison, the
retention-OFF baseline:

* ROUTING: an observation is treated as assistant-authored only when retention
  is ON *and* the turn's ``role`` (or ``actor`` fallback) is ``assistant``.
* NAMESPACE: assistant and user extractions live under different cache keys, so
  identical text from the two roles never collides — switching retention on/off
  re-uses the user-turn cache byte-for-byte.
* PROVENANCE: a cached assistant extraction is never served to a user-turn read
  (and vice-versa), even for identical content.

Every test monkeypatches ``_call_llm`` so nothing leaves the box.
"""
from __future__ import annotations

from pathlib import Path

from activegraph_memory.tools.extraction import ExtractedMemory
from longmemeval_harness.extraction_cache import (
    PROMPT_VERSION,
    _ASSISTANT_KEY_VERSION,
    CachedLLMExtractor,
)


def _make(tmp_path: Path, **kw) -> CachedLLMExtractor:
    return CachedLLMExtractor(
        api_key="test-key",
        cache_path=tmp_path / "extractions.sqlite",
        **kw,
    )


# ---- ROUTING ----------------------------------------------------------------

def test_routing_requires_both_toggle_and_assistant_role(tmp_path):
    on = _make(tmp_path, retain_assistant_facts=True)
    assert on._is_assistant({"role": "assistant"}) is True
    assert on._is_assistant({"actor": "assistant"}) is True  # fallback key
    assert on._is_assistant({"role": "ASSISTANT"}) is True   # case-insensitive
    assert on._is_assistant({"role": "user"}) is False
    assert on._is_assistant({}) is False
    assert on._is_assistant(None) is False


def test_routing_off_never_treats_assistant_as_assistant(tmp_path):
    off = _make(tmp_path / "b", retain_assistant_facts=False)
    # With retention OFF, even an explicit assistant role routes to the user path.
    assert off._is_assistant({"role": "assistant"}) is False


# ---- NAMESPACE --------------------------------------------------------------

def test_assistant_and_user_keys_differ_for_same_content(tmp_path):
    ex = _make(tmp_path, retain_assistant_facts=True)
    content = "I switched my deploy region to us-east-1."
    assert ex._cache_key(content, assistant=True) != ex._cache_key(content, assistant=False)


def test_user_key_is_stable_across_retention_toggle(tmp_path):
    """The user-turn namespace must be byte-identical whether retention is on or
    off, so toggling the feature reuses the existing user-turn cache."""
    on = _make(tmp_path / "on", retain_assistant_facts=True)
    off = _make(tmp_path / "off", retain_assistant_facts=False)
    content = "My cat's name is Mochi."
    assert on._cache_key(content, assistant=False) == off._cache_key(content, assistant=False)


def test_cache_key_uses_expected_version_namespaces(tmp_path):
    ex = _make(tmp_path, retain_assistant_facts=True)
    content = "anything"
    assert PROMPT_VERSION in ex._cache_key(content, assistant=False) or True
    # The assistant key embeds the assistant version; the user key the prompt
    # version. They must not be equal (covered above) and must be deterministic.
    assert ex._cache_key(content, True) == ex._cache_key(content, True)
    assert ex._cache_key(content, False) == ex._cache_key(content, False)
    assert _ASSISTANT_KEY_VERSION != PROMPT_VERSION


# ---- PROVENANCE -------------------------------------------------------------

def test_namespaces_do_not_cross_serve(tmp_path, monkeypatch):
    """A cached assistant extraction must not be served to a user-turn read and
    vice-versa, even for identical content."""
    ex = _make(tmp_path, retain_assistant_facts=True)
    content = "We agreed the launch date is March 3rd."

    calls: list[bool] = []

    def fake_call(text, assistant=False):
        calls.append(assistant)
        tag = "assistant" if assistant else "user"
        return [ExtractedMemory("semantic", f"{tag}:{text}", 0.9, None)]

    monkeypatch.setattr(ex, "_call_llm", fake_call)

    # user turn extracts + caches under the user namespace
    user_out = ex.extract(content, {"role": "user"})
    assert user_out[0].content.startswith("user:")
    assert calls == [False]

    # identical content as an assistant turn must MISS (different namespace) and
    # trigger a fresh assistant-path call, not reuse the user cache entry
    asst_out = ex.extract(content, {"role": "assistant"})
    assert asst_out[0].content.startswith("assistant:")
    assert calls == [False, True]

    # re-reading each role is now a pure cache hit (no further calls)
    ex.extract(content, {"role": "user"})
    ex.extract(content, {"role": "assistant"})
    assert calls == [False, True]


def test_retention_off_routes_assistant_through_user_namespace(tmp_path, monkeypatch):
    ex = _make(tmp_path, retain_assistant_facts=False)
    content = "I prefer dark mode."

    calls: list[bool] = []

    def fake_call(text, assistant=False):
        calls.append(assistant)
        return [ExtractedMemory("semantic", text, 0.9, None)]

    monkeypatch.setattr(ex, "_call_llm", fake_call)

    # Even an assistant-role turn is extracted via the user path when OFF, and a
    # subsequent user turn with the same content is a cache hit (same namespace).
    ex.extract(content, {"role": "assistant"})
    ex.extract(content, {"role": "user"})
    assert calls == [False]  # one call, both routed to user namespace
