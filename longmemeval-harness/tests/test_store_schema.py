"""Schema / migration guards for ``RunStore`` (no network).

These guard against record/schema drift — the class of bug where the
orchestrator writes a field the table has no column for, crashing every run on
first ``upsert``:

* a record carrying every resolved-model field (incl. ``extractor_resolved_model``)
  round-trips through ``upsert`` -> ``get``;
* a store created BEFORE a column existed is migrated additively on open, so old
  run dirs keep resuming.
"""
from __future__ import annotations

import sqlite3

from longmemeval_harness.store import _ADDED_COLUMNS, RunStore


def _columns(db_path) -> set[str]:
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(questions)")}
    con.close()
    return cols


def test_fresh_store_has_all_added_columns(tmp_path):
    store = RunStore(tmp_path / "store.sqlite")
    store.close()
    cols = _columns(tmp_path / "store.sqlite")
    for name, _decl in _ADDED_COLUMNS:
        assert name in cols


def test_record_with_resolved_models_roundtrips(tmp_path):
    store = RunStore(tmp_path / "store.sqlite")
    rec = {
        "question_id": "q1",
        "question_type": "single-session-user",
        "status": "done",
        "ingest_n_claims": 5,
        "extractor_resolved_model": "gpt-4o-mini-2024-07-18",
        "reader_resolved_model": "claude-sonnet-4-5-20250929",
        "judge_resolved_model": "gpt-4o-2024-08-06",
        "turn_hit": True,
    }
    store.upsert(rec)
    got = store.get("q1")
    store.close()
    assert got is not None
    assert got["extractor_resolved_model"] == "gpt-4o-mini-2024-07-18"
    assert got["reader_resolved_model"] == "claude-sonnet-4-5-20250929"
    assert got["turn_hit"] is True


def test_legacy_store_is_migrated_on_open(tmp_path):
    """Simulate a pre-migration DB missing the newest column, then confirm
    opening it via RunStore adds the column and a write succeeds."""
    path = tmp_path / "store.sqlite"
    con = sqlite3.connect(str(path))
    # Old-style table with the original columns but WITHOUT the newest one.
    con.execute(
        "CREATE TABLE questions (question_id TEXT PRIMARY KEY, status TEXT, "
        "ingest_n_claims INTEGER, created_at REAL, updated_at REAL)"
    )
    con.commit()
    con.close()
    assert "extractor_resolved_model" not in _columns(path)

    store = RunStore(path)  # __init__ runs _migrate()
    assert "extractor_resolved_model" in _columns(path)
    store.upsert({"question_id": "q1", "status": "done",
                  "extractor_resolved_model": "gpt-4o-mini-2024-07-18"})
    got = store.get("q1")
    store.close()
    assert got["extractor_resolved_model"] == "gpt-4o-mini-2024-07-18"
