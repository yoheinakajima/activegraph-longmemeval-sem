"""Tests for the reader: parity prompt constancy + scaffolded-mode parsing.

No network access — these guard the controlled-constant parity reader and the
NON-PARITY scaffolded reader's answer extraction without touching an LLM.
"""

from __future__ import annotations

from longmemeval_harness import reader


# -- parity reader is a frozen constant ------------------------------------
def test_parity_reader_system_is_frozen():
    """The parity reader system prompt is copied verbatim from the paper harness
    and must never drift — it is the controlled constant across runs."""
    assert reader.READER_SYSTEM == (
        "You are a helpful assistant answering a user's question about prior "
        "conversations between the user and an assistant. Use ONLY the provided "
        "conversation history. If the history does not contain enough information "
        "to answer, say you don't know. Be concise."
    )


# -- scaffolded answer parsing ---------------------------------------------
def test_parse_scaffolded_answer_takes_text_after_marker():
    out = reader._parse_scaffolded_answer(
        "1. type: temporal\n2. evidence...\n3. compute 30 days\nANSWER: 30 days"
    )
    assert out == "30 days"


def test_parse_scaffolded_answer_uses_last_marker():
    assert reader._parse_scaffolded_answer("ANSWER: draft\nANSWER: final") == "final"


def test_parse_scaffolded_answer_is_case_insensitive():
    assert reader._parse_scaffolded_answer("reasoning\nanswer: lower") == "lower"


def test_parse_scaffolded_answer_falls_back_to_full_text():
    """If the model omitted the marker, keep the whole (stripped) response rather
    than dropping the answer."""
    assert reader._parse_scaffolded_answer("  no marker here  ") == "no marker here"


def test_parse_scaffolded_answer_empty_after_marker_falls_back():
    raw = "some reasoning\nANSWER:   "
    assert reader._parse_scaffolded_answer(raw) == raw.strip()


def test_scaffolded_systems_keep_parity_constraints():
    """Both scaffolded variants must retain the use-only-history + abstain
    constraints and the delimited-answer contract."""
    for sysmsg in (reader.SCAFFOLDED_SYSTEM, reader.SCAFFOLDED_SELFCHECK_SYSTEM):
        assert "ONLY the provided" in sysmsg
        assert "don't know" in sysmsg
        assert "ANSWER:" in sysmsg
    # the self-check variant adds an explicit verification step
    assert "Self-check" in reader.SCAFFOLDED_SELFCHECK_SYSTEM
    assert "Self-check" not in reader.SCAFFOLDED_SYSTEM
