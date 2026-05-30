"""LLM-backed memory extractor with a persistent, process-safe cache.

``CachedLLMExtractor`` implements the pack's ``ExtractionProvider`` protocol:
given an observation's text, it asks a cheap LLM (default ``gpt-4o-mini`` at
temp 0) which durable memories to create, following the pack's
``prompts/extract_candidate_memories.md`` contract. Results are cached on disk
keyed by ``(model, prompt_version, content)``, giving the same two properties as
the embedding cache:

* **Speed / bounded cost** — LongMemEval-S reuses the same turns across many
  questions' haystacks, so each unique turn is extracted exactly once, ever.
  ``warm()`` pre-extracts a question's turns concurrently before ingest so the
  per-observation behavior calls are all cache hits (no sequential stalls).
* **Reproducibility** — a given turn always yields the same memories, so re-runs
  are identical and free.

The cache stores the structured extraction (a JSON list), not free text, so it
is robust to prompt re-runs and safe for ``ProcessPoolExecutor`` workers (WAL +
busy timeout + ``INSERT OR IGNORE``).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from activegraph_memory.tools.extraction import ExtractedMemory

# Bump when the prompt or output contract changes so stale cache entries are
# never reused under a new extraction definition.
PROMPT_VERSION = "1.1.0"

# Assistant-turn extraction (Track 1: retain assistant-authored facts) is a
# SEPARATE prompt + cache namespace so the user-turn path stays byte-identical
# (same key + same prompt => existing warm cache hits, results identical to the
# retention-OFF baseline). Only assistant turns are (re)extracted under this key,
# and only when ``retain_assistant_facts`` is enabled. Bump independently.
ASSISTANT_PROMPT_VERSION = "1.0.0"
_ASSISTANT_KEY_VERSION = "assist-" + ASSISTANT_PROMPT_VERSION

_VALID_TYPES = {"procedural", "episodic", "semantic"}

_SYSTEM = (
    "You extract durable, reusable memory from a single conversation message "
    "so a future assistant can personalize help for this user. Skip greetings, "
    "pleasantries, acknowledgements, and purely transient context, but do NOT "
    "be stingy about what reveals the user: capture their stable facts, goals, "
    "and — importantly — their preferences and interests.\n\n"
    "Capture REVEALED preferences and interests, not only explicitly stated "
    "ones. When the user asks for a recommendation, help, or advice about a "
    "subject, or expresses curiosity, enthusiasm, or repeated engagement with "
    "it, that reveals a durable interest or preference of the user — record it. "
    "Example: a user asking 'recommend stand-up comedy specials on Netflix with "
    "strong storytelling' reveals that the user is interested in stand-up "
    "comedy specials on Netflix, especially ones with strong storytelling. "
    "Attribute such memories to the user ('The user is interested in ...', "
    "'The user prefers ...'); treat advice the assistant gives as procedural "
    "guidance only when it is a durable rule the user adopted.\n\n"
    "Coverage: every salient named entity, product, place, work, person, or "
    "topic in the message should appear in at least one extracted memory; do "
    "not drop the specific subject the message is about.\n\n"
    "Self-contained + topic-anchored: each memory must stand alone WITHOUT the "
    "original message and must name the high-level topic or domain it concerns, "
    "so it can be retrieved later from a differently-worded query. For example "
    "write 'The user is interested in stand-up comedy specials on Netflix, "
    "especially ones with strong storytelling (entertainment / shows to "
    "watch).' rather than a bare 'likes Mulaney'. Resolve pronouns to concrete "
    "names. One memory per distinct durable fact, not one per sentence.\n\n"
    "Classify each memory as exactly one of:\n"
    "- procedural: the user's preferences, interests, style rules, "
    "instructions, or policies the assistant should honor.\n"
    "- episodic: events with actors and dates ('yesterday', 'last week', "
    "'we decided', 'they signed').\n"
    "- semantic: stable facts about the user, a project, an entity, or a "
    "person.\n\n"
    "Confidence: ~0.9 for explicitly stated facts/preferences, ~0.7 for "
    "interests revealed indirectly through a request or engagement.\n\n"
    "Return ONLY a JSON object of the form "
    '{"memories": [{"memory_type": "...", "content": "...", '
    '"confidence": 0.0-1.0, "reason": "..."}]}. '
    "Return an empty list when nothing is durable."
)

# Track 1: assistant-authored fact retention. The default ``_SYSTEM`` prompt is
# user-centric ("capture the user's stable facts/preferences") and discards the
# assistant's own factual OUTPUTS (answers, lists, counts, names, game moves,
# calculations, recommendations). That is exactly what the user later asks to
# recall in single-session-assistant questions, so we extract assistant turns
# with a dedicated prompt that preserves those outputs verbatim, attributed to
# the assistant — without polluting the user's profile.
_ASSISTANT_SYSTEM = (
    "You extract durable, retrievable memory from a single ASSISTANT message in a "
    "conversation, so a future assistant can answer the user's later questions "
    "about what was previously said, shown, or produced for them. Users frequently "
    "ask to recall the assistant's own prior OUTPUTS: answers, facts, lists, "
    "counts, names, definitions, game moves, calculations, code, plans, or "
    "recommendations the assistant gave.\n\n"
    "Capture each such factual output as a self-contained memory that names the "
    "topic/domain it concerns AND includes enough verbatim detail (exact numbers, "
    "names, moves, ordered-list positions) to answer an exact-recall question "
    "later, WITHOUT the original message. Attribute it to the assistant. Examples: "
    "'The assistant told the user the party will face 3 mummies in the temple "
    "(D&D campaign).' / 'The assistant's chess move after 27. Kg2 Bd5+ was 28. "
    "Kg3.' / 'The assistant recommended the books Dune and Hyperion as classic "
    "sci-fi (book recommendations).'\n\n"
    "Do NOT convert assistant outputs into facts or preferences ABOUT the user; "
    "record only what the assistant stated or produced, attributed to the "
    "assistant. Skip greetings, filler, hedging, clarifying questions, and "
    "conversational acknowledgements that contain no recallable fact. Resolve "
    "pronouns to concrete names. One memory per distinct recallable output.\n\n"
    "Classify each memory as exactly one of:\n"
    "- episodic: a specific action the assistant took with a context "
    "('the assistant calculated ...', 'the assistant made the move ...').\n"
    "- semantic: a stable factual output, list item, name, count, definition, or "
    "recommendation the assistant provided.\n"
    "- procedural: only if the assistant stated a durable rule/instruction the "
    "user explicitly adopted (rare).\n\n"
    "Confidence: ~0.9 for explicit factual outputs, ~0.7 for less certain ones.\n\n"
    "Return ONLY a JSON object of the form "
    '{"memories": [{"memory_type": "...", "content": "...", '
    '"confidence": 0.0-1.0, "reason": "..."}]}. '
    "Return an empty list when the message contains nothing recallable."
)


def _key(model: str, content: str, version: str = PROMPT_VERSION) -> str:
    h = hashlib.blake2b(digest_size=20)
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(version.encode("utf-8"))
    h.update(b"\x00")
    h.update(content.encode("utf-8"))
    return h.hexdigest()


class CachedLLMExtractor:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        cache_path: str | os.PathLike,
        max_tokens: int = 512,
        max_workers: int = 8,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        retain_assistant_facts: bool = True,
    ) -> None:
        from openai import OpenAI

        if not api_key:
            raise RuntimeError("CachedLLMExtractor requires an explicit api_key.")
        self._client = OpenAI(api_key=api_key)
        self.model = model
        # Track 1 toggle: when True, assistant turns are extracted with the
        # assistant-aware prompt under a separate cache namespace. When False the
        # extractor behaves exactly as the retention-OFF baseline (assistant turns
        # use the default user-centric prompt + the original cache key).
        self.retain_assistant_facts = retain_assistant_facts
        self.max_tokens = max_tokens
        self.max_workers = max(1, max_workers)
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
            "CREATE TABLE IF NOT EXISTS extractions ("
            "key TEXT PRIMARY KEY, memories TEXT NOT NULL)"
        )
        conn.commit()

    # -- cache read/write ---------------------------------------------------
    def _cache_key(self, content: str, assistant: bool = False) -> str:
        version = _ASSISTANT_KEY_VERSION if assistant else PROMPT_VERSION
        return _key(self.model, content, version)

    def _read(
        self, content: str, assistant: bool = False
    ) -> Optional[list[ExtractedMemory]]:
        row = self._conn().execute(
            "SELECT memories FROM extractions WHERE key=?",
            (self._cache_key(content, assistant),),
        ).fetchone()
        if row is None:
            return None
        return self._decode(row[0])

    def _write(
        self, content: str, mems: list[ExtractedMemory], assistant: bool = False
    ) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR IGNORE INTO extractions(key, memories) VALUES (?, ?)",
            (self._cache_key(content, assistant), self._encode(mems)),
        )
        conn.commit()

    @staticmethod
    def _encode(mems: list[ExtractedMemory]) -> str:
        return json.dumps(
            [
                {"memory_type": m.memory_type, "content": m.content,
                 "confidence": m.confidence, "reason": m.reason}
                for m in mems
            ]
        )

    @staticmethod
    def _decode(blob: str) -> list[ExtractedMemory]:
        out: list[ExtractedMemory] = []
        for d in json.loads(blob):
            out.append(
                ExtractedMemory(
                    memory_type=d.get("memory_type", "semantic"),
                    content=d.get("content", ""),
                    confidence=float(d.get("confidence", 0.85)),
                    reason=d.get("reason"),
                )
            )
        return out

    # -- LLM call -----------------------------------------------------------
    def _call_llm(
        self, content: str, assistant: bool = False
    ) -> Optional[list[ExtractedMemory]]:
        """Return the extracted memories, or ``None`` on a transient failure.

        ``None`` is distinct from ``[]`` (a valid "nothing durable" result):
        callers must NOT cache ``None`` so a rate-limit / network blip never
        becomes a permanent empty cache entry. Retries with backoff first.

        ``assistant`` selects the assistant-aware prompt (Track 1); the default
        (``False``) preserves the original user-centric extraction exactly.
        """
        system = _ASSISTANT_SYSTEM if assistant else _SYSTEM
        user = (
            f"Assistant message:\n{content}" if assistant else f"Message:\n{content}"
        )
        raw: Optional[str] = None
        for attempt in range(self._max_retries):
            try:
                r = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
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
        # Parse + defensively normalize. A well-formed-but-unexpected shape
        # (e.g. JSON that is not an object, or a non-list "memories") is treated
        # as a genuine empty extraction, not a transient failure.
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(parsed, dict):
            return []
        items = parsed.get("memories")
        if not isinstance(items, list):
            return []
        mems: list[ExtractedMemory] = []
        for d in items:
            if not isinstance(d, dict):
                continue
            mt = str(d.get("memory_type", "semantic")).lower().strip()
            if mt not in _VALID_TYPES:
                mt = "semantic"
            text = (d.get("content") or "").strip()
            if not text:
                continue
            try:
                conf = float(d.get("confidence", 0.85))
            except (TypeError, ValueError):
                conf = 0.85
            conf = min(1.0, max(0.0, conf))  # clamp to [0, 1] for pack schemas
            mems.append(ExtractedMemory(mt, text, conf, d.get("reason")))
        return mems

    # -- public API (ExtractionProvider) ------------------------------------
    def _is_assistant(self, metadata: dict[str, Any]) -> bool:
        """Route to the assistant-aware path only when retention is on AND the
        observation is an assistant turn. ``role`` (falling back to ``actor``) is
        set by the harness adapter from the source turn."""
        if not self.retain_assistant_facts:
            return False
        md = metadata or {}
        role = str(md.get("role") or md.get("actor") or "").strip().lower()
        return role == "assistant"

    def extract(self, content: str, metadata: dict[str, Any]) -> list[ExtractedMemory]:
        content = (content or "").strip()
        if not content:
            return []
        assistant = self._is_assistant(metadata)
        cached = self._read(content, assistant) if assistant else self._read(content)
        if cached is not None:
            return cached
        mems = self._call_llm(content, assistant) if assistant else self._call_llm(content)
        if mems is None:  # transient failure: do not poison the cache
            return []
        if assistant:
            self._write(content, mems, assistant=True)
        else:
            self._write(content, mems)
        return mems

    def warm(self, items: list[Any]) -> None:
        """Pre-extract cache-missing turns concurrently so later per-observation
        ``extract`` calls (sequential inside run_until_idle) are all hits.

        ``items`` are ``(content, role)`` pairs (a bare string is treated as a
        user turn). Each (content, path) pair is warmed under the path's own
        cache namespace, mirroring ``extract``'s routing."""
        uniq: list[tuple[str, bool]] = []
        seen: set[tuple[str, bool]] = set()
        for it in items:
            if isinstance(it, (tuple, list)):
                text, role = it[0], it[1]
            else:
                text, role = it, "user"
            text = (text or "").strip()
            if not text:
                continue
            assistant = self.retain_assistant_facts and (
                str(role or "").strip().lower() == "assistant"
            )
            key = (text, assistant)
            if key in seen:
                continue
            if self._read(text, assistant) is None:
                seen.add(key)
                uniq.append(key)
        if not uniq:
            return

        def _job(pair: tuple[str, bool]):
            text, assistant = pair
            mems = self._call_llm(text, assistant) if assistant else self._call_llm(text)
            return text, assistant, mems

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            for text, assistant, mems in ex.map(_job, uniq):
                if mems is None:  # skip caching transient failures
                    continue
                if assistant:
                    self._write(text, mems, assistant=True)
                else:
                    self._write(text, mems)

    def stats(self) -> dict[str, int]:
        (n,) = self._conn().execute("SELECT COUNT(*) FROM extractions").fetchone()
        return {"cached_extractions": int(n)}
