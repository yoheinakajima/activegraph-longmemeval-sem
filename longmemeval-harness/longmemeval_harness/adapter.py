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

from .config import CACHE_DIR
from .dataset import Instance
from .embedding_cache import CachedEmbeddingProvider

_MEMORY_TYPES = ("memory_claim", "episodic_memory", "procedural_memory")

# Same embedding model the original activegraph-longmemeval substrate test used.
EMBEDDING_MODEL = "text-embedding-3-small"

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
    instance: Instance, settings: Optional[MemorySettings] = None
) -> EvidenceBundle:
    settings = settings or MemorySettings()
    _install_embedding_provider()
    g = Graph()
    rt = Runtime(g)
    rt.load_pack(pack, settings=settings)

    n_obs = 0
    for session in _sorted_sessions(instance):
        for turn in session.turns:
            if not turn.content:
                continue
            g.add_object(
                "memory_observation",
                {
                    "actor": turn.role,
                    "content": turn.content,
                    "source": "longmemeval",
                    "source_id": f"{turn.session_id}::{turn.turn_index}",
                    "metadata": {
                        "session_id": turn.session_id,
                        "turn_index": turn.turn_index,
                        "role": turn.role,
                        "session_date": session.date,
                    },
                },
            )
            n_obs += 1
    rt.run_until_idle()

    g.add_object(
        "memory_query",
        {"question": instance.question, "mode": "standard"},
    )
    rt.run_until_idle()

    objects = {o.id: o for o in g.all_objects()}
    derived: dict[str, set[str]] = {}
    for rel in g.all_relations():
        if rel.type == "derived_from":
            src, tgt = _rel_ends(rel)
            if src and tgt:
                derived.setdefault(src, set()).add(tgt)

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
    fact_lines: list[str] = []
    for mid in dict.fromkeys(used_ids + retrieved_ids):
        obj = objects.get(mid)
        if obj and obj.type in _MEMORY_TYPES:
            content = (obj.data.get("content") or "").strip()
            if content:
                fact_lines.append(f"- {content}")

    msg_lines: list[str] = []
    for oid in sorted(obs_ids, key=_id_num):
        obj = objects.get(oid)
        if obj is None:
            continue
        md = obj.data.get("metadata", {}) or {}
        date = md.get("session_date") or ""
        actor = obj.data.get("actor") or md.get("role") or ""
        content = (obj.data.get("content") or "").strip()
        msg_lines.append(f"[{date}] {actor}: {content}")

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
