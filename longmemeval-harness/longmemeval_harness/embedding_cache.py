"""Persistent, process-safe embedding cache.

``CachedEmbeddingProvider`` wraps any base embedding provider (e.g. the pack's
``OpenAIEmbeddingProvider``) with an on-disk SQLite cache keyed by
``(model, text)``. This gives two properties the original
activegraph-longmemeval test relied on:

* **Speed** — LongMemEval-S reuses the same distractor sessions across many
  questions' haystacks, so the same turn text recurs constantly. Each unique
  ``(model, text)`` is embedded exactly once, ever; subsequent occurrences
  (same run, later questions, or entirely new runs) are disk hits.
* **Reproducibility** — a given text always resolves to the same stored vector,
  so re-runs are bit-for-bit identical and require no new API calls.

The cache is safe for the harness's ``ProcessPoolExecutor`` workers: SQLite is
opened in WAL mode with a busy timeout, and writes use ``INSERT OR IGNORE`` so
concurrent workers embedding overlapping text never conflict.
"""

from __future__ import annotations

import array
import hashlib
import os
import sqlite3
import threading
from pathlib import Path
from typing import Iterable, Optional, Protocol


class _BaseProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]: ...


def _key(model: str, text: str) -> str:
    h = hashlib.blake2b(digest_size=20)
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


class CachedEmbeddingProvider:
    """Disk-cached wrapper around a base embedding provider."""

    def __init__(
        self,
        base: _BaseProvider,
        *,
        model: str,
        cache_path: str | os.PathLike,
    ) -> None:
        self._base = base
        self._model = model
        self._path = str(cache_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    # -- connection (one per thread/process) --------------------------------
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
            "CREATE TABLE IF NOT EXISTS embeddings ("
            "key TEXT PRIMARY KEY, dim INTEGER NOT NULL, vec BLOB NOT NULL)"
        )
        conn.commit()

    # -- (de)serialization ---------------------------------------------------
    @staticmethod
    def _to_blob(vec: list[float]) -> bytes:
        # float64 ('d') so a cached read is bit-identical to the value the API
        # first returned -> re-runs are exactly reproducible.
        return array.array("d", vec).tobytes()

    @staticmethod
    def _from_blob(blob: bytes) -> list[float]:
        a = array.array("d")
        a.frombytes(blob)
        return a.tolist()

    # -- public API ----------------------------------------------------------
    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []

        # Unique, non-empty texts -> their cache keys.
        uniq: list[str] = []
        seen: set[str] = set()
        for t in items:
            if t and t.strip() and t not in seen:
                seen.add(t)
                uniq.append(t)
        keys = {t: _key(self._model, t) for t in uniq}

        # Bulk read from cache.
        found: dict[str, list[float]] = {}
        conn = self._conn()
        key_list = list(keys.values())
        rev = {v: k for k, v in keys.items()}
        CHUNK = 900  # stay under SQLite's variable limit
        for i in range(0, len(key_list), CHUNK):
            sub = key_list[i : i + CHUNK]
            q = "SELECT key, vec FROM embeddings WHERE key IN (%s)" % (
                ",".join("?" * len(sub))
            )
            for k, blob in conn.execute(q, sub):
                found[rev[k]] = self._from_blob(blob)

        # Embed misses with the base provider, then persist them.
        misses = [t for t in uniq if t not in found]
        if misses:
            vecs = self._base.embed_many(misses)
            rows = []
            for t, v in zip(misses, vecs):
                found[t] = v
                rows.append((keys[t], len(v), self._to_blob(v)))
            conn.executemany(
                "INSERT OR IGNORE INTO embeddings(key, dim, vec) VALUES (?, ?, ?)",
                rows,
            )
            conn.commit()

        # Map back to the original (possibly duplicated) input order.
        zero: Optional[list[float]] = None
        out: list[list[float]] = []
        for t in items:
            if t in found:
                out.append(found[t])
            else:
                if zero is None:
                    dim = len(next(iter(found.values()))) if found else 1536
                    zero = [0.0] * dim
                out.append(zero)
        return out

    def stats(self) -> dict[str, int]:
        conn = self._conn()
        (n,) = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()
        return {"cached_vectors": int(n)}
