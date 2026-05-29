"""Agentic retrieval controller — pluggable, flag-gated.

The default ("flat") retrieval path blends keyword + vector search over memory
objects. The *agentic* path instead reasons in a small loop over the concept
graph:

    1. vector-search **concepts** for the question,
    2. gather the **facts linked** to the best concepts (``about_entity``),
    3. **self-assess** whether those facts look sufficient,
    4. if not, **fall back** to direct fact vector/keyword search,
    5. **iterate** (widening the search) until confident or the budget is spent.

This indirection surfaces facts that share an entity with the question even when
their wording is far from it — the failure mode of flat search on
preference/recommendation questions.

The loop is *pluggable*: a caller may install an LLM-driven controller via
:func:`set_active_retrieval_controller`. When none is installed, the pack uses
:class:`DefaultAgenticController`, a deterministic offline implementation, so
tests stay reproducible and the path runs with no API key.

All of this is inert unless ``settings.retrieval_strategy == "agentic"``. With
an empty concept graph the loop degrades gracefully to direct fact search.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from activegraph_memory.constants import CONCEPT_TYPE, MEMORY_TYPES
from activegraph_memory.tools.concepts import deterministic_concepts, normalize_concept
from activegraph_memory.tools.embeddings import EmbeddingProvider, get_active_provider
from activegraph_memory.tools.scoring import cosine_similarity, keyword_score
from activegraph_memory.tools.text_normalize import extract_keywords


def _id_num(obj_id: str) -> int:
    try:
        return int(str(obj_id).rsplit("#", 1)[1])
    except (IndexError, ValueError):
        return 0


def _rel_ends(rel) -> tuple[Optional[str], Optional[str]]:
    src = getattr(rel, "source", None) or getattr(rel, "source_id", None)
    tgt = getattr(rel, "target", None) or getattr(rel, "target_id", None)
    return src, tgt


@dataclass
class ConceptHit:
    concept_id: str
    name: str
    score: float


@dataclass
class FactHit:
    object_id: str
    score: float
    type: str
    content: str


@dataclass
class RetrievalDecision:
    """What a controller decided to retrieve, plus its self-assessment."""

    fact_ids: list[str]
    confidence: float
    iterations: int = 1
    reasoning: Optional[str] = None
    used_concepts: list[str] = field(default_factory=list)


class RetrievalTools:
    """Read-only retrieval capabilities bound to the current graph view.

    Constructed by the ``retrieve_memories`` behavior and handed to a
    controller. Indices are built once; embeddings go through the active
    provider (deterministic offline, real + cached during a harness run).
    """

    def __init__(
        self,
        objects,
        relations,
        *,
        exclude_statuses,
        provider: Optional[EmbeddingProvider] = None,
    ):
        self._provider = provider or get_active_provider()
        excluded = set(exclude_statuses or ())
        self._facts: dict = {}      # memory id -> object
        self._concepts: dict = {}   # concept id -> object
        for o in objects:
            if o.type in MEMORY_TYPES:
                if (o.data or {}).get("status") in excluded:
                    continue
                self._facts[o.id] = o
            elif o.type == CONCEPT_TYPE:
                self._concepts[o.id] = o
        # Concept name index for exact entity matching (normalized name + aliases
        # -> concept ids), and per-concept normalized name for overlap scoring.
        self._concept_norm: dict[str, str] = {}
        self._concept_by_norm: dict[str, list[str]] = {}
        for cid, o in self._concepts.items():
            data = o.data or {}
            primary = normalize_concept(str(data.get("name", "")))
            self._concept_norm[cid] = primary
            forms = {primary} | {
                normalize_concept(str(a)) for a in (data.get("aliases") or [])
            }
            for n in forms:
                if n:
                    self._concept_by_norm.setdefault(n, []).append(cid)
        # about_entity: memory -> concept. Index concept id -> [memory ids] and
        # the reverse memory id -> {concept ids} (used for entity-overlap rerank).
        self._facts_by_concept: dict[str, list[str]] = {}
        self._concepts_of_fact: dict[str, set[str]] = {}
        for r in relations:
            if getattr(r, "type", None) != "about_entity":
                continue
            src, tgt = _rel_ends(r)
            if src in self._facts and tgt in self._concepts:
                self._facts_by_concept.setdefault(tgt, []).append(src)
                self._concepts_of_fact.setdefault(src, set()).add(tgt)
        self._qvec_cache: dict[str, list[float]] = {}

    # -- embeddings ---------------------------------------------------------
    def _embed(self, text: str) -> list[float]:
        v = self._qvec_cache.get(text)
        if v is None:
            v = self._provider.embed(text)
            self._qvec_cache[text] = v
        return v

    @staticmethod
    def _concept_text(obj) -> str:
        data = obj.data or {}
        name = str(data.get("name", ""))
        aliases = [str(a) for a in (data.get("aliases") or [])]
        return " ".join([name, *aliases]).strip() or name

    @staticmethod
    def _fact_content(obj) -> str:
        return str((obj.data or {}).get("content", ""))

    # -- capabilities -------------------------------------------------------
    def search_concepts(self, query: str, limit: int) -> list[ConceptHit]:
        """Vector-search concept nodes by name/aliases for the query."""
        if not self._concepts or limit <= 0:
            return []
        items = list(self._concepts.values())
        qv = self._embed(query)
        cvecs = self._provider.embed_many([self._concept_text(o) for o in items])
        hits: list[ConceptHit] = []
        for o, cv in zip(items, cvecs):
            s = cosine_similarity(qv, cv)
            if s <= 0.0:
                continue
            hits.append(ConceptHit(o.id, str((o.data or {}).get("name", "")), s))
        hits.sort(key=lambda h: (-h.score, h.concept_id))
        return hits[:limit]

    def search_concepts_by_entities(self, question: str) -> list[ConceptHit]:
        """Exact-match concepts to entities/topics extracted from the question.

        Symmetric with ingest: the same deterministic extractor runs on the
        question, and its normalized names are looked up directly in the concept
        index. This is high-precision (the concept genuinely names something the
        question asks about), complementing the fuzzy vector search. Offline and
        cost-free regardless of any injected (LLM) extractor used at ingest.
        """
        if not self._concepts:
            return []
        hits: list[ConceptHit] = []
        seen: set[str] = set()
        for ent in self.question_entities(question):
            for cid in self._concept_by_norm.get(ent, []):
                if cid in seen:
                    continue
                seen.add(cid)
                hits.append(ConceptHit(
                    cid, str((self._concepts[cid].data or {}).get("name", "")), 1.0,
                ))
        hits.sort(key=lambda h: h.concept_id)
        return hits

    @staticmethod
    def question_entities(question: str) -> set[str]:
        """Normalized entity/topic names extracted from the question."""
        return {
            n for n in (
                normalize_concept(e) for e in deterministic_concepts(question or "")
            ) if n
        }

    def fact_concept_norms(self, fact_id: str) -> set[str]:
        """Normalized names of the concepts a fact is linked to (for overlap)."""
        return {
            self._concept_norm[c]
            for c in self._concepts_of_fact.get(fact_id, set())
            if self._concept_norm.get(c)
        }

    def facts_for_concepts(self, concept_ids) -> list[str]:
        """Memory ids linked to any of the given concepts via ``about_entity``."""
        out: list[str] = []
        seen: set[str] = set()
        for cid in concept_ids:
            for fid in self._facts_by_concept.get(cid, []):
                if fid not in seen and fid in self._facts:
                    seen.add(fid)
                    out.append(fid)
        out.sort(key=_id_num)
        return out

    def rank_facts(self, query: str, fact_ids) -> list[FactHit]:
        """Score a set of facts against the query (max(keyword, 0.6*vector))."""
        ids = [fid for fid in fact_ids if fid in self._facts]
        if not ids:
            return []
        keywords = extract_keywords(query)
        qv = self._embed(query)
        contents = [self._fact_content(self._facts[fid]) for fid in ids]
        cvecs = self._provider.embed_many(contents)
        hits: list[FactHit] = []
        for fid, content, cv in zip(ids, contents, cvecs):
            kw = keyword_score(keywords, content)
            vec = cosine_similarity(qv, cv)
            score = max(kw, 0.6 * vec)
            if score <= 0.0:
                continue
            hits.append(FactHit(fid, score, self._facts[fid].type, content))
        hits.sort(key=lambda h: (-h.score, h.object_id))
        return hits

    def search_facts(self, query: str, limit: int) -> list[FactHit]:
        """Direct blended keyword+vector search over all retrievable facts."""
        return self.rank_facts(query, list(self._facts.keys()))[:limit]

    def is_fact(self, object_id: str) -> bool:
        """True iff ``object_id`` is a retrievable memory under current filters.

        The controller boundary is untrusted: a buggy or LLM-driven controller
        may return concept ids, excluded/superseded ids, or ids that don't
        exist. Callers must validate every returned id through this before
        writing it into the retrieval result.
        """
        return object_id in self._facts

    @property
    def n_facts(self) -> int:
        return len(self._facts)

    @property
    def n_concepts(self) -> int:
        return len(self._concepts)


class RetrievalController(Protocol):
    def retrieve(
        self, question: str, tools: RetrievalTools, settings
    ) -> RetrievalDecision: ...


# Process-wide active controller. ``None`` => the behavior uses
# DefaultAgenticController (deterministic, offline) when strategy == "agentic".
_ACTIVE: Optional[RetrievalController] = None


def set_active_retrieval_controller(c: Optional[RetrievalController]) -> None:
    """Install the process-wide retrieval controller (None resets to default)."""
    global _ACTIVE
    _ACTIVE = c


def get_active_retrieval_controller() -> Optional[RetrievalController]:
    return _ACTIVE


def _confidence(hits: list[FactHit]) -> float:
    """Deterministic self-assessment: blend top score with coverage."""
    if not hits:
        return 0.0
    top = hits[0].score
    strong = sum(1 for h in hits if h.score >= 0.3)
    coverage = min(strong / 3.0, 1.0)
    return max(0.0, min(1.0, 0.5 * top + 0.5 * coverage))


class DefaultAgenticController:
    """Deterministic, offline agentic controller.

    Each iteration the controller *tries multiple things* and merges their
    candidates, widening the search until it is confident or the budget is spent:

      1. **question-entity match** — entities/topics extracted from the question
         matched exactly against concept names (high precision; symmetric with
         ingest). Gated by ``agentic_match_question_entities``.
      2. **concept vector search** — fuzzy concept recall (always on).
      3. **direct fact search** — keyword+vector over facts as a backup recall
         net, triggered when the concept routes look thin/uncertain. Gated by
         ``agentic_direct_fact_fallback``.

    The merged pool is then *reranked and trimmed* (the "too much info" guard):
    relevance + question-entity overlap, recency as the tie-break, keep top
    ``agentic_rerank_limit``. This keeps same-entity distractors and stale
    siblings out of the reader's context.

    No LLM is used, so it runs reproducibly and key-free. A real LLM controller
    can be injected to replace it; both honor the same budget knobs.
    """

    def retrieve(
        self, question: str, tools: RetrievalTools, settings
    ) -> RetrievalDecision:
        threshold = settings.agentic_confidence_threshold
        max_iter = settings.agentic_max_iterations
        max_facts = settings.agentic_max_facts
        concept_limit = settings.agentic_concept_search_limit

        best: dict[str, FactHit] = {}
        used_concepts: list[str] = []
        confidence = 0.0
        it = 0

        def _merge(hits: list[FactHit]) -> None:
            for h in hits:
                prev = best.get(h.object_id)
                if prev is None or h.score > prev.score:
                    best[h.object_id] = h

        def _note(concept_ids) -> None:
            for cid in concept_ids:
                if cid not in used_concepts:
                    used_concepts.append(cid)

        for it in range(1, max_iter + 1):
            # Strategy 1: high-precision exact match on question entities/topics.
            if settings.agentic_match_question_entities:
                ent_hits = tools.search_concepts_by_entities(question)
                _note(c.concept_id for c in ent_hits)
                linked = tools.facts_for_concepts([c.concept_id for c in ent_hits])
                _merge(tools.rank_facts(question, linked))

            # Strategy 2: fuzzy concept vector search (widening each iteration).
            concept_hits = tools.search_concepts(question, concept_limit * it)
            _note(c.concept_id for c in concept_hits)
            linked = tools.facts_for_concepts([c.concept_id for c in concept_hits])
            _merge(tools.rank_facts(question, linked))

            confidence = _confidence(self._rank(question, best, tools, settings))

            # Strategy 3: direct fact search as a backup recall net.
            if settings.agentic_direct_fact_fallback and (
                confidence < threshold or len(best) < 3
            ):
                _merge(tools.search_facts(question, max_facts))
                confidence = _confidence(self._rank(question, best, tools, settings))

            if confidence >= threshold and len(best) >= 3:
                break

        kept = self._select(question, best, tools, settings)
        fact_ids = [h.object_id for h in kept]
        return RetrievalDecision(
            fact_ids=fact_ids,
            confidence=confidence,
            iterations=it,
            reasoning=(
                f"concepts={len(used_concepts)} pool={len(best)} "
                f"kept={len(fact_ids)} conf={confidence:.2f}"
            ),
            used_concepts=used_concepts,
        )

    @staticmethod
    def _final_score(h: FactHit, q_ents: set, tools, w: float) -> float:
        """Relevance, optionally boosted by question-entity overlap (w>0)."""
        if w <= 0.0:
            return h.score
        overlap = len(tools.fact_concept_norms(h.object_id) & q_ents) if q_ents else 0
        return h.score + w * overlap

    @classmethod
    def _rank(cls, question, best, tools, settings) -> list[FactHit]:
        """Order the candidate pool.

        With the rerank feature OFF (``entity_overlap_weight == 0``) this is the
        prior controller's deterministic sort exactly: ``(-score, object_id)``.
        With it ON, facts are reranked by relevance + question-entity overlap and
        a recency (higher id) tie-break is added.
        """
        w = settings.agentic_entity_overlap_weight
        if w <= 0.0:
            return sorted(best.values(), key=lambda h: (-h.score, h.object_id))
        q_ents = tools.question_entities(question)
        return sorted(
            best.values(),
            key=lambda h: (
                -cls._final_score(h, q_ents, tools, w),
                -_id_num(h.object_id),
                h.object_id,
            ),
        )

    @classmethod
    def _select(cls, question, best, tools, settings) -> list[FactHit]:
        """Order then ADAPTIVELY trim the pool before it reaches the reader.

        With both extras OFF this reproduces the prior controller exactly: the
        deterministic ``(-score, object_id)`` order capped at ``max_facts``. When
        ``keep_ratio`` > 0, keep only facts whose score is within that ratio of
        the top fact's score (a relevance-dropoff gate): a focused question has
        one dominant fact so weaker siblings/distractors fall below the gate,
        while a multi-hop question has many comparably-scored facts that all
        survive. The output is always capped at ``min(max_facts, rerank_limit)``.
        """
        ranked = cls._rank(question, best, tools, settings)
        if not ranked:
            return []
        ratio = settings.agentic_rerank_keep_ratio
        if ratio > 0.0:
            q_ents = tools.question_entities(question)
            w = settings.agentic_entity_overlap_weight
            floor = cls._final_score(ranked[0], q_ents, tools, w) * ratio
            ranked = [
                h for h in ranked if cls._final_score(h, q_ents, tools, w) >= floor
            ]
        cap = min(settings.agentic_max_facts, settings.agentic_rerank_limit)
        return ranked[:cap]
