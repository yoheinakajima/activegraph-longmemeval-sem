"""Guards for ``analysis.cleanup_tables.fmt_model`` — the manifest model-block
renderer used in the reproduction-metadata table.

The contract is subtle because the alias lives in different fields per block:
- reader / judge: alias in ``requested``
- extraction / rerank: ``requested`` is the MODE (llm/deterministic), alias in
  ``model``

and three schema generations must all render correctly:
- legacy (only ``resolved``)
- new, snapshot resolved (``resolved_model`` set)
- new, snapshot unavailable (``resolved_model_unavailable=True``)
"""
from __future__ import annotations

from analysis.cleanup_tables import fmt_model


# ---- reader / judge (alias in `requested`) ---------------------------------

def test_reader_legacy_resolved():
    block = {"requested": "claude-sonnet-4-5", "resolved": "claude-sonnet-4-5-20250929"}
    assert fmt_model(block) == "claude-sonnet-4-5-20250929"


def test_reader_legacy_resolved_missing_falls_back_to_requested():
    assert fmt_model({"requested": "claude-sonnet-4-5"}) == "claude-sonnet-4-5"


def test_reader_new_schema_resolved():
    block = {"requested": "gpt-4o", "resolved_model": "gpt-4o-2024-08-06",
             "resolved_model_unavailable": False}
    assert fmt_model(block) == "gpt-4o-2024-08-06"


def test_reader_new_schema_unavailable_uses_requested_alias():
    block = {"requested": "claude-sonnet-4-5", "resolved_model": None,
             "resolved_model_unavailable": True}
    assert fmt_model(block) == "claude-sonnet-4-5 (alias; unavailable)"


# ---- extraction (MODE in `requested`, alias in `model`) ---------------------

def test_extraction_unavailable_uses_model_alias_not_mode():
    # The bug this guards: must show the extractor alias, NOT the mode "llm".
    block = {"requested": "llm", "resolved": "llm", "model": "gpt-4o-mini",
             "resolved_model": None, "resolved_model_unavailable": True}
    assert fmt_model(block) == "gpt-4o-mini (alias; unavailable)"


def test_extraction_resolved_snapshot_wins_over_mode():
    block = {"requested": "llm", "resolved": "llm", "model": "gpt-4o-mini",
             "resolved_model": "gpt-4o-mini-2024-07-18",
             "resolved_model_unavailable": False}
    assert fmt_model(block) == "gpt-4o-mini-2024-07-18"


def test_extraction_legacy_renders_mode():
    # Old manifests (pre-resolution schema) only have requested+resolved=mode.
    assert fmt_model({"requested": "llm", "resolved": "llm"}) == "llm"


def test_extraction_deterministic_has_no_model_alias():
    # Deterministic extraction: `model` is None -> fall back to the mode.
    block = {"requested": "deterministic", "resolved": "deterministic",
             "model": None, "resolved_model": None,
             "resolved_model_unavailable": True}
    assert fmt_model(block) == "deterministic (alias; unavailable)"


def test_empty_block_is_safe():
    assert fmt_model({}) == "?"
