"""Pack-driving adapter.

Per question: spin up a fresh ActiveGraph runtime with the memory pack,
ingest the conversation history as ``memory_observation`` events tagged
with their (session_id, turn_index) so retrieved memories trace back to
source turns via provenance, issue the question as a ``memory_query``,
run to idle, and extract the retrieved-evidence bundle.

Ingestion is fully deterministic and calls no LLM. This module only
consumes the pack's public surface: ``Graph``, ``Runtime``, ``pack``,
``MemorySettings``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from activegraph import Graph, Runtime
from activegraph_memory import MemorySettings, pack
from activegraph_memory.tools.embeddings import (
    OpenAIEmbeddingProvider,
    set_active_provider,
)
from activegraph_memory.tools.extraction import set_active_extractor
from activegraph_memory.tools.reranker import set_active_reranker

from .config import CACHE_DIR, EXTRACTION_MODEL
from .dataset import Instance
from .embedding_cache import CachedEmbeddingProvider
from .extraction_cache import CachedLLMExtractor
from .rerank_cache import CachedLLMReranker

_MEMORY_TYPES = ("memory_claim", "episodic_memory", "procedural_memory")

# Same embedding model the original activegraph-longmemeval substrate test used.
EMBEDDING_MODEL = "text-embedding-3-small"

# Cheap, fast model for the optional LLM reranker (opt-in via --rerank llm).
# Cached on disk so each (question, candidate-set) is reranked once, ever.
RERANK_MODEL = "gpt-4o-mini"

# Per-process cached provider. ``run_pack`` is called once per question, but each
# ProcessPoolExecutor worker handles many questions; building a fresh provider
# (and SQLite connection) per question would leak file descriptors over a long
# run. Cache it once per worker process and reuse.
_EMBEDDING_PROVIDER: Optional[CachedEmbeddingProvider] = None


def _install_embedding_provider() -> Optional[str]:
    """Install a real OpenAI embeddings provider for semantic vector search.

    Uses the user-provided real OPENAI_API_KEY (the Replit AI proxy does not
    expose an embeddings endpoint). Falls back to the pack's offline
    deterministic provider when no key is present. Returns the model name when a
    real provider was installed, else None. The cached provider is built once per
    process and reused across questions.
    """
    global _EMBEDDING_PROVIDER
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        set_active_provider(None)  # reset to deterministic default
        return None
    if _EMBEDDING_PROVIDER is None:
        base = OpenAIEmbeddingProvider(EMBEDDING_MODEL, api_key=key)
        _EMBEDDING_PROVIDER = CachedEmbeddingProvider(
            base, model=EMBEDDING_MODEL, cache_path=CACHE_DIR / "embeddings.sqlite"
        )
    set_active_provider(_EMBEDDING_PROVIDER)
    return EMBEDDING_MODEL


# Per-process LLM extractor (see _install_embedding_provider for the rationale).
_EXTRACTOR: Optional[CachedLLMExtractor] = None


def resolve_extraction_mode(mode: str) -> tuple[str, Optional[str]]:
    """Return the extraction mode/model that will actually run, accounting for
    the ``OPENAI_API_KEY`` fallback. ``llm`` silently degrades to
    ``deterministic`` when no key is present, so callers (e.g. the manifest)
    can record what truly happened instead of what was merely requested.
    """
    if mode == "llm" and os.environ.get("OPENAI_API_KEY"):
        return "llm", EXTRACTION_MODEL
    return "deterministic", None


def _install_extractor(
    mode: str, retain_assistant_facts: bool = True
) -> Optional[CachedLLMExtractor]:
    """Install the LLM extraction provider when ``mode == 'llm'`` and a real
    OPENAI_API_KEY is present; otherwise reset the pack to its deterministic
    heuristic. Returns the active extractor (for cache pre-warming) or None.

    ``retain_assistant_facts`` (Track 1) toggles assistant-authored fact
    retention on the per-process extractor. A run has a single value, so setting
    it each call is a no-op after the first; it never changes the user-turn path.
    """
    global _EXTRACTOR
    if mode != "llm":
        set_active_extractor(None)
        return None
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        set_active_extractor(None)
        return None
    if _EXTRACTOR is None:
        _EXTRACTOR = CachedLLMExtractor(
            api_key=key,
            model=EXTRACTION_MODEL,
            cache_path=CACHE_DIR / "extractions.sqlite",
            retain_assistant_facts=retain_assistant_facts,
        )
    _EXTRACTOR.retain_assistant_facts = retain_assistant_facts
    set_active_extractor(_EXTRACTOR)
    return _EXTRACTOR


# Per-process LLM reranker (see _install_embedding_provider for the rationale).
_RERANKER: Optional[CachedLLMReranker] = None


def resolve_rerank_mode(mode: str) -> tuple[str, Optional[str]]:
    """What the reranker will actually do, accounting for the key fallback.
    ``llm`` degrades to ``off`` when no OPENAI_API_KEY is present."""
    if mode == "llm" and os.environ.get("OPENAI_API_KEY"):
        return "llm", RERANK_MODEL
    return "off", None


def _install_reranker(mode: str) -> Optional[CachedLLMReranker]:
    """Install the LLM reranker when ``mode == 'llm'`` and a real OPENAI_API_KEY
    is present; otherwise reset the pack to no-rerank. The pack only consults a
    reranker when ``settings.enable_rerank`` is also on, so this and the settings
    flag must agree (the orchestrator sets both from the same ``--rerank`` flag).
    """
    global _RERANKER
    if mode != "llm":
        set_active_reranker(None)
        return None
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        set_active_reranker(None)
        return None
    if _RERANKER is None:
        _RERANKER = CachedLLMReranker(
            api_key=key,
            model=RERANK_MODEL,
            cache_path=CACHE_DIR / "reranks.sqlite",
        )
    set_active_reranker(_RERANKER)
    return _RERANKER


@dataclass
class EvidenceBundle:
    assembled_context: str
    retrieved_object_ids: list[str]
    used_memory_ids: list[str]
    evidence_ids: list[str]
    context_turn_ids: list[list[Any]] = field(default_factory=list)  # [sid, idx]
    context_session_ids: list[str] = field(default_factory=list)
    retrieval_summary: Optional[str] = None
    missing_data: list[str] = field(default_factory=list)
    n_observations: int = 0
    n_claims: int = 0
    answer_text: Optional[str] = None
    pack_errors: list[str] = field(default_factory=list)


def _rel_ends(rel) -> tuple[Optional[str], Optional[str]]:
    src = getattr(rel, "source_id", None) or getattr(rel, "source", None)
    tgt = getattr(rel, "target_id", None) or getattr(rel, "target", None)
    return src, tgt


def _id_num(obj_id: str) -> int:
    # Object ids look like "memory_observation#7"; the numeric suffix is the
    # insertion order (== chronological order of ingestion / creation order).
    try:
        return int(obj_id.rsplit("#", 1)[1])
    except (IndexError, ValueError):
        return 0


def _sorted_sessions(instance: Instance):
    """Chronological order so supersession/recency is meaningful."""
    dated = [(s, s.date_obj) for s in instance.sessions]
    if all(d is not None for _, d in dated):
        return [s for s, _ in sorted(dated, key=lambda p: p[1])]
    return instance.sessions


def run_pack(
    instance: Instance,
    settings: Optional[MemorySettings] = None,
    *,
    extraction: str = "deterministic",
    rerank: str = "off",
    retain_assistant_facts: bool = True,
) -> EvidenceBundle:
    settings = settings or MemorySettings()
    _install_embedding_provider()
    extractor = _install_extractor(extraction, retain_assistant_facts)
    _install_reranker(rerank)
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=settings)

    n_obs = 0
    # (content, role) pairs so the extraction cache can warm assistant turns
    # under the assistant-aware namespace and user turns under the original one.
    warm_items: list[tuple[str, str]] = []
    for session in _sorted_sessions(instance):
        # Anchor every turn to its session timestamp. This lets the pack's
        # resolve_temporal_refs behavior turn relative mentions ("yesterday",
        # "last week") into absolute dates, and propagates occurred_at onto any
        # episodic memories extracted from the turn — both surfaced to the reader
        # below so it does not have to do relative-date arithmetic itself.
        anchor = session.date_obj.isoformat() if session.date_obj else None
        for turn in session.turns:
            if not turn.content:
                continue
            warm_items.append((turn.content, turn.role))
            g.add_object(
                "memory_observation",
                {
                    "actor": turn.role,
                    "content": turn.content,
                    "source": "longmemeval",
                    "source_id": f"{turn.session_id}::{turn.turn_index}",
                    "occurred_at": anchor,
                    "observed_at": anchor,
                    "metadata": {
                        "session_id": turn.session_id,
                        "turn_index": turn.turn_index,
                        "role": turn.role,
                        "session_date": session.date,
                    },
                },
            )
            n_obs += 1

    # Pre-warm the extraction cache concurrently so the per-observation behavior
    # calls (sequential inside run_until_idle) are all cache hits.
    if extractor is not None:
        extractor.warm(warm_items)
    rt.run_until_idle()

    g.add_object(
        "memory_query",
        {"question": instance.question, "mode": "standard"},
    )
    rt.run_until_idle()

    objects = {o.id: o for o in g.all_objects()}
    derived: dict[str, set[str]] = {}
    # source object id -> temporal_ref object ids (relative/explicit dates the
    # pack already resolved against each turn's anchor).
    temporal_by_src: dict[str, list[str]] = {}
    for rel in g.all_relations():
        if rel.type == "derived_from":
            src, tgt = _rel_ends(rel)
            if src and tgt:
                derived.setdefault(src, set()).add(tgt)
        elif rel.type == "has_temporal_ref":
            src, tgt = _rel_ends(rel)
            if src and tgt:
                temporal_by_src.setdefault(src, []).append(tgt)

    adapter_warnings: list[str] = []

    # Bind to the *final* answer/retrieval chain, not the first-by-type. With
    # fallback retrieval enabled the pack emits a second memory_retrieval_result
    # (is_fallback=True, same query_id) and the answer is produced from that one.
    # Picking by type alone would capture the stale pre-fallback retrieval.
    answers = [o for o in objects.values() if o.type == "memory_answer"]
    retrievals = [o for o in objects.values() if o.type == "memory_retrieval_result"]

    # Latest answer (highest insertion id) is the one the pack settled on.
    answer = max(answers, key=lambda o: _id_num(o.id)) if answers else None

    retrieval = None
    if answer is not None:
        rid = answer.data.get("retrieval_result_id")
        if rid:
            retrieval = objects.get(rid)
    if retrieval is None and retrievals:
        # Prefer a fallback result; otherwise the latest by insertion id.
        fallbacks = [
            o for o in retrievals
            if (o.data.get("metadata") or {}).get("is_fallback")
        ]
        pool = fallbacks or retrievals
        retrieval = max(pool, key=lambda o: _id_num(o.id))

    if len(answers) > 1 and answer is not None and not answer.data.get("retrieval_result_id"):
        adapter_warnings.append(
            "ambiguous answer selection: multiple memory_answer objects and "
            "selected answer has no retrieval_result_id"
        )

    retrieved_ids = list((retrieval.data.get("retrieved_object_ids") if retrieval else []) or [])
    used_ids = list((answer.data.get("used_memory_ids") if answer else []) or [])
    evidence_ids = list((answer.data.get("evidence_ids") if answer else []) or [])

    def source_observations(mem_id: str) -> set[str]:
        obj = objects.get(mem_id)
        if obj is None:
            return set()
        if obj.type == "memory_observation":
            return {mem_id}
        return derived.get(mem_id, set())

    interest = list(dict.fromkeys(retrieved_ids + used_ids + evidence_ids))
    obs_ids: set[str] = set()
    for mid in interest:
        obs_ids |= source_observations(mid)

    context_turn_ids: list[list[Any]] = []
    context_session_ids: set[str] = set()
    for oid in obs_ids:
        obj = objects.get(oid)
        if obj is None:
            continue
        md = obj.data.get("metadata", {}) or {}
        sid = md.get("session_id")
        tidx = md.get("turn_index")
        if sid is not None and tidx is not None:
            context_turn_ids.append([sid, tidx])
            context_session_ids.add(sid)

    # ---- assemble the evidence bundle text the reader will consume ----
    def _date_only(v: Any) -> str:
        # Temporal/occurred_at values are ISO datetimes; keep just the date.
        return str(v).split("T", 1)[0] if v else ""

    def _resolved_dates(src_id: str) -> list[str]:
        """Absolute dates the pack resolved for a turn's relative time words,
        formatted like 'yesterday = 2022-03-20', so the reader does not have to
        do the relative-date arithmetic that causes temporal-reasoning misses."""
        out: list[str] = []
        seen: set[str] = set()
        for ref_id in temporal_by_src.get(src_id, []):
            ref = objects.get(ref_id)
            if ref is None:
                continue
            rd = ref.data or {}
            if rd.get("resolution_method") in (None, "unresolved"):
                continue
            day = _date_only(rd.get("resolved_at"))
            text = (rd.get("text") or "").strip()
            if not day or not text or text.lower() == day:
                continue
            if rd.get("resolution_method") == "duration_start":
                label = f"{text} = since {day}"
            else:
                label = f"{text} = {day}"
            if label not in seen:
                seen.add(label)
                out.append(label)
        return out

    fact_lines: list[str] = []
    for mid in dict.fromkeys(used_ids + retrieved_ids):
        obj = objects.get(mid)
        if obj and obj.type in _MEMORY_TYPES:
            content = (obj.data.get("content") or "").strip()
            if content:
                when = _date_only(obj.data.get("occurred_at")) if obj.type == "episodic_memory" else ""
                fact_lines.append(f"- [{when}] {content}" if when else f"- {content}")

    # The provenance walk surfaces only the turns behind retrieved memories, so a
    # session can be "hit" while its answer-bearing turn is missing (turn_hit=0,
    # common on single-session-preference). When evidence concentrates in one or
    # two short sessions, include all of their turns so the reader sees the actual
    # stated preference/fact. Bounded so multi-session contexts are never bloated.
    display_obs: set[str] = set(obs_ids)
    if 0 < len(context_session_ids) <= 2:
        expanded = set(obs_ids)
        for oid, obj in objects.items():
            if obj.type != "memory_observation":
                continue
            md = obj.data.get("metadata", {}) or {}
            if md.get("session_id") in context_session_ids:
                expanded.add(oid)
        if len(expanded) <= 40:  # sessions average ~10 turns; cap protects tokens
            display_obs = expanded

    msg_lines: list[str] = []
    for oid in sorted(display_obs, key=_id_num):
        obj = objects.get(oid)
        if obj is None:
            continue
        md = obj.data.get("metadata", {}) or {}
        date = md.get("session_date") or ""
        actor = obj.data.get("actor") or md.get("role") or ""
        content = (obj.data.get("content") or "").strip()
        resolved = _resolved_dates(oid)
        suffix = f"  (dates: {'; '.join(resolved)})" if resolved else ""
        msg_lines.append(f"[{date}] {actor}: {content}{suffix}")

    parts: list[str] = []
    if fact_lines:
        parts.append("Remembered facts:\n" + "\n".join(fact_lines))
    if msg_lines:
        parts.append("Relevant past messages:\n" + "\n".join(msg_lines))
    assembled = "\n\n".join(parts) if parts else "(no relevant memory retrieved)"

    n_claims = sum(1 for o in objects.values() if o.type in _MEMORY_TYPES)
    errors = [str(e) for e in (rt.errors or [])] + adapter_warnings

    return EvidenceBundle(
        assembled_context=assembled,
        retrieved_object_ids=retrieved_ids,
        used_memory_ids=used_ids,
        evidence_ids=evidence_ids,
        context_turn_ids=context_turn_ids,
        context_session_ids=sorted(context_session_ids),
        retrieval_summary=(retrieval.data.get("summary") if retrieval else None),
        missing_data=list((retrieval.data.get("missing_data") if retrieval else []) or []),
        n_observations=n_obs,
        n_claims=n_claims,
        answer_text=(answer.data.get("answer") if answer else None),
        pack_errors=errors,
    )
