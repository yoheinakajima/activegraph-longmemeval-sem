"""MemorySettings — pack-scoped configuration.

Every field has a default so ``runtime.load_pack(pack)`` works without
explicit ``settings=``. Behaviors access these via typed parameter
injection: ``def my_behavior(event, graph, ctx, *, settings: MemorySettings):``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemorySettings(BaseModel):
    """Configuration for the memory pack."""

    # Feature flags — let users disable parts of the lifecycle
    enable_semantic_memory: bool = True
    enable_episodic_memory: bool = True
    enable_procedural_memory: bool = True
    enable_retrieval_planning: bool = True
    enable_keyword_retrieval: bool = True
    enable_vector_retrieval: bool = True
    enable_contradiction_detection: bool = True
    enable_temporal_resolution: bool = True
    enable_numeric_scope: bool = True
    enable_consolidation: bool = True
    enable_fallback_retrieval: bool = True
    enable_answer_generation: bool = True
    enable_memory_evaluation: bool = True

    # Thresholds
    extraction_confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    contradiction_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    consolidation_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    # Retrieval shape
    retrieval_mode_default: Literal["standard", "deep"] = "standard"
    retrieval_limit: int = Field(default=40, ge=1)
    fallback_retrieval_limit: int = Field(default=20, ge=1)
    include_superseded_in_standard_retrieval: bool = False
    include_archived_in_standard_retrieval: bool = False

    # Answering
    allow_general_knowledge_in_answers: bool = False

    # Concept graph (entity/topic layer). OFF by default so the flat baseline
    # and offline tests are unchanged. When on, extraction links each memory to
    # canonical ``memory_concept`` nodes via ``about_entity``.
    enable_concept_graph: bool = False
    max_concepts_per_memory: int = Field(default=6, ge=1)
    # Secondary dedup: merge concept surface forms whose embeddings are very
    # similar. OFF by default — exact normalized-name match is the primary,
    # deterministic, cost-free dedup. Turning this on embeds every concept name.
    concept_embedding_dedup: bool = False
    concept_dedup_similarity: float = Field(default=0.92, ge=0.0, le=1.0)

    # Retrieval strategy. "flat" = current keyword+vector blend (default).
    # "agentic" = pluggable controller loop: vector-search concepts -> gather
    # linked facts -> self-assess -> fall back to direct fact search -> iterate
    # until confident or budget exhausted. Inert unless set to "agentic".
    retrieval_strategy: Literal["flat", "agentic"] = "flat"
    agentic_max_iterations: int = Field(default=4, ge=1)
    agentic_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    agentic_max_facts: int = Field(default=40, ge=1)
    agentic_concept_search_limit: int = Field(default=10, ge=1)

    # Agentic strategies — the controller "tries multiple things" and merges.
    # All deterministic/offline. Each is an independent retrieval signal:
    #   1. match entities/topics extracted from the QUESTION against concept
    #      names (exact, high precision) — symmetric with ingest extraction.
    #   2. vector-search concept names (fuzzy recall) — always on.
    #   3. direct keyword+vector fact search as a backup recall net.
    # Off by default: matching question entities against concept names maximizes
    # recall, but on LongMemEval-S recall is already saturated (every agentic
    # variant matches/exceeds flat's turn recall). The extra surface-entity
    # matches are mostly distractors that make the reader hedge or pick a sibling,
    # lowering accuracy. Kept as an opt-in option per the original request.
    agentic_match_question_entities: bool = False
    agentic_direct_fact_fallback: bool = True
    # Rerank/trim the merged candidates before they reach the reader. Both are
    # OFF by default because, on LongMemEval-S with a strong reader, both hurt:
    #   * entity-overlap reranking (weight>0) reorders facts and — via the
    #     reader's position bias — makes it hedge/abstain on preference questions
    #     even when the answer is present (single-session-preference 1.0 -> 0.33).
    #   * the trim (fixed-count OR adaptive keep_ratio) lowers turn recall:
    #     multi-hop questions need many facts spread across sessions, and any
    #     mis-ranked distractor in the offline scorer pushes a true fact out.
    # The reader handles a large, plainly relevance-sorted fact set best, so the
    # default agentic path leaves the pool untouched. Both remain available for
    # experimentation: set ``entity_overlap_weight`` > 0 to rerank, and
    # ``keep_ratio`` in (0, 1] to keep only facts within that ratio of the top
    # fact's score. ``rerank_limit`` is a safety cap on the absolute maximum.
    agentic_entity_overlap_weight: float = Field(default=0.0, ge=0.0)
    agentic_rerank_keep_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    agentic_rerank_limit: int = Field(default=40, ge=1)

    # Policy tag — used as a label for diff/fork comparisons
    default_policy_name: str = "default"
