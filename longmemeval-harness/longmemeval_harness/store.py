"""Resumable per-run SQLite store.

Records each question's status and every analyzable field (ingest stats,
retrieved + mapped turn ids, assembled context, token counts, per-stage
timings, hypothesis, scores, judge verdict). The orchestrator reads
completed ids on startup and skips them, so a run resumes cleanly after
an interruption (Replit restart, timeout, crash).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

_JSON_COLS = (
    "pack_errors",
    "retrieved_object_ids",
    "used_memory_ids",
    "evidence_ids",
    "context_turn_ids",
    "context_session_ids",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY,
    question_type TEXT,
    is_abstention INTEGER,
    status TEXT,                       -- pending | done | error
    error TEXT,

    question TEXT,
    question_date TEXT,
    gold_answer TEXT,

    ingest_n_obs INTEGER,
    ingest_n_claims INTEGER,
    extractor_resolved_model TEXT,
    pack_errors TEXT,
    retrieved_object_ids TEXT,
    used_memory_ids TEXT,
    evidence_ids TEXT,
    context_turn_ids TEXT,
    context_session_ids TEXT,
    retrieval_summary TEXT,
    assembled_context TEXT,

    hypothesis TEXT,
    reader_requested_model TEXT,
    reader_resolved_model TEXT,
    reader_prompt_tokens INTEGER,
    reader_completion_tokens INTEGER,
    reader_total_tokens INTEGER,
    context_tokens INTEGER,
    truncated INTEGER,

    turn_recall REAL,
    turn_hit INTEGER,
    session_recall REAL,
    session_hit INTEGER,
    n_gold_turns INTEGER,
    n_gold_sessions INTEGER,

    judge_requested_model TEXT,
    judge_resolved_model TEXT,
    judge_correct INTEGER,
    judge_raw TEXT,
    judge_total_tokens INTEGER,

    t_ingest REAL,
    t_read REAL,
    t_judge REAL,
    t_total REAL,

    created_at REAL,
    updated_at REAL
);
"""

_BOOL_COLS = ("is_abstention", "truncated", "turn_hit", "session_hit", "judge_correct")

# Columns added after the original schema shipped; applied to pre-existing DBs by
# RunStore._migrate so older run stores keep resuming. (column_name, sql_decl)
_ADDED_COLUMNS = (
    ("extractor_resolved_model", "TEXT"),
)


class RunStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Additively add columns missing from pre-existing DBs so older run
        stores keep resuming after the schema gains a field (e.g.
        ``extractor_resolved_model``). New stores already have every column from
        ``_SCHEMA``; this only touches stores created before the column existed."""
        have = {row[1] for row in self._conn.execute("PRAGMA table_info(questions)")}
        for col, decl in _ADDED_COLUMNS:
            if col not in have:
                self._conn.execute(f"ALTER TABLE questions ADD COLUMN {col} {decl}")

    def close(self) -> None:
        self._conn.close()

    def completed_ids(self) -> set[str]:
        cur = self._conn.execute(
            "SELECT question_id FROM questions WHERE status = 'done'"
        )
        return {row[0] for row in cur.fetchall()}

    def status_counts(self) -> dict[str, int]:
        cur = self._conn.execute(
            "SELECT status, COUNT(*) FROM questions GROUP BY status"
        )
        return {row[0]: row[1] for row in cur.fetchall()}

    def upsert(self, record: dict[str, Any]) -> None:
        rec = dict(record)
        now = time.time()
        rec.setdefault("created_at", now)
        rec["updated_at"] = now
        for col in _JSON_COLS:
            if col in rec and not isinstance(rec[col], (str, type(None))):
                rec[col] = json.dumps(rec[col])
        for col in _BOOL_COLS:
            if col in rec and isinstance(rec[col], bool):
                rec[col] = int(rec[col])

        cols = list(rec.keys())
        placeholders = ", ".join(":" + c for c in cols)
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "question_id")
        sql = (
            f"INSERT INTO questions ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(question_id) DO UPDATE SET {updates}"
        )
        self._conn.execute(sql, rec)
        self._conn.commit()

    def get(self, question_id: str) -> Optional[dict]:
        cur = self._conn.execute(
            "SELECT * FROM questions WHERE question_id = ?", (question_id,)
        )
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def all_records(self) -> list[dict]:
        cur = self._conn.execute("SELECT * FROM questions")
        return [self._row_to_dict(r) for r in cur.fetchall()]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        for col in _JSON_COLS:
            if d.get(col) is not None:
                try:
                    d[col] = json.loads(d[col])
                except (TypeError, ValueError):
                    pass
        for col in _BOOL_COLS:
            if d.get(col) is not None:
                d[col] = bool(d[col])
        return d
