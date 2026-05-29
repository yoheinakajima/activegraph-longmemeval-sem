"""LLM-backed retrieval reranker with a persistent, process-safe cache.

``CachedLLMReranker`` implements the pack's ``RerankProvider`` protocol: given
a question and the flat path's ranked candidate facts, it asks an LLM which
facts are actually useful for answering — ordered, distractors dropped — and
returns the kept ids. This is the "genuinely strong reranker" the precision
experiment flagged as untried: it replaces the weak deterministic relevance
score as the final gate on what reaches the reader.

Caching mirrors the extraction / embedding caches and gives the same two
properties:

* **Speed / bounded cost** — exactly one rerank call per question (not per
  memory), keyed by ``(model, prompt_version, question, candidate_contents)``,
  so re-runs over the same slice are free.
* **Reproducibility** — temp-0 + on-disk cache means a given (question,
  candidate-set) always yields the same ordering.

A transient failure returns the path's original top-``limit`` order and is NOT
cached, so a rate-limit / network blip never becomes a permanent bad entry.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

# Bump when the prompt or output contract changes so stale entries are never
# reused under a new rerank definition.
PROMPT_VERSION = "1.0.0"

_SYSTEM = (
    "You are a precise retrieval reranker. You are given a user QUESTION and a "
    "numbered list of candidate FACTS remembered from the user's past "
    "conversations. Decide which facts are actually useful for answering the "
    "question, ordered most useful first.\n\n"
    "Keep every fact that could plausibly help answer — including questions "
    "that need several facts combined (aggregation, multi-step, timelines, "
    "comparisons), where all the contributing facts must be kept. Drop only "
    "clear distractors: facts about a different entity, person, item, topic, or "
    "time that do not bear on the question. When in doubt, keep the fact.\n\n"
    "Return ONLY a JSON object of the form {\"relevant\": [i, j, k, ...]} where "
    "each value is the 1-based index of a kept fact, most relevant first. "
    "Return an empty list only if no fact is relevant."
)


def _key(model: str, question: str, contents: list[str]) -> str:
    h = hashlib.blake2b(digest_size=20)
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(PROMPT_VERSION.encode("utf-8"))
    h.update(b"\x00")
    h.update(question.encode("utf-8"))
    for c in contents:
        h.update(b"\x00")
        h.update(c.encode("utf-8"))
    return h.hexdigest()


class CachedLLMReranker:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        cache_path: str | os.PathLike,
        max_tokens: int = 256,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> None:
        from openai import OpenAI

        if not api_key:
            raise RuntimeError("CachedLLMReranker requires an explicit api_key.")
        self._client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self._max_retries = max(1, max_retries)
        self._backoff_base = backoff_base
        self._path = str(cache_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    # -- connection (one per thread) ----------------------------------------
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._path, timeout=60.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=60000")
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reranks ("
            "key TEXT PRIMARY KEY, ordering TEXT NOT NULL)"
        )
        conn.commit()

    # -- cache read/write ---------------------------------------------------
    def _read(self, question: str, contents: list[str]) -> Optional[list[int]]:
        row = self._conn().execute(
            "SELECT ordering FROM reranks WHERE key=?",
            (_key(self.model, question, contents),),
        ).fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row[0])
            return [int(i) for i in data]
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def _write(self, question: str, contents: list[str], order: list[int]) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR IGNORE INTO reranks(key, ordering) VALUES (?, ?)",
            (_key(self.model, question, contents), json.dumps(order)),
        )
        conn.commit()

    # -- LLM call -----------------------------------------------------------
    def _call_llm(self, question: str, contents: list[str]) -> Optional[list[int]]:
        """Return 1-based kept indices, or ``None`` on a transient failure.

        ``None`` (transient) is distinct from ``[]`` (the model judged nothing
        relevant): callers must NOT cache ``None``.
        """
        numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(contents, 1))
        user = f"QUESTION:\n{question}\n\nCANDIDATE FACTS:\n{numbered}"
        raw: Optional[str] = None
        for attempt in range(self._max_retries):
            try:
                r = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.0,
                    max_completion_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )
                raw = r.choices[0].message.content or "{}"
                break
            except Exception:
                if attempt + 1 >= self._max_retries:
                    return None
                time.sleep(self._backoff_base * (2 ** attempt))
        if raw is None:
            return None
        # Parse defensively. A well-formed-but-unexpected shape is treated as a
        # genuine empty result (keep nothing), not a transient failure.
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(parsed, dict):
            return []
        items = parsed.get("relevant")
        if not isinstance(items, list):
            return []
        out: list[int] = []
        n = len(contents)
        seen: set[int] = set()
        for v in items:
            try:
                idx = int(v)
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= n and idx not in seen:
                seen.add(idx)
                out.append(idx)
        return out

    # -- public API (RerankProvider) ----------------------------------------
    def rerank(
        self, question: str, candidates: list[tuple[str, str]], limit: int
    ) -> list[str]:
        question = (question or "").strip()
        ids = [cid for cid, _ in candidates]
        contents = [str(c or "") for _, c in candidates]
        if not ids or not question:
            return ids[: max(1, limit)]

        order = self._read(question, contents)
        if order is None:
            order = self._call_llm(question, contents)
            if order is None:  # transient failure: do not poison the cache
                return ids[: max(1, limit)]
            self._write(question, contents, order)

        kept = [ids[i - 1] for i in order if 1 <= i <= len(ids)]
        # Empty result is a valid "nothing relevant" verdict; fall back to the
        # original top-`limit` rather than starving the reader of all context.
        if not kept:
            return ids[: max(1, limit)]
        return kept[: max(1, limit)]

    def stats(self) -> dict[str, int]:
        (n,) = self._conn().execute("SELECT COUNT(*) FROM reranks").fetchone()
        return {"cached_reranks": int(n)}
