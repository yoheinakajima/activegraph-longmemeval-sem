"""Object type schemas (Pydantic) and ObjectType registry for the memory pack.

13 object types + 2 request types, all per docs/brief/object_types.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from activegraph.packs import ObjectType

# ---------------------------------------------------------------- schemas


class MemoryObservation(BaseModel):
    """Something the system observed: a message, a tool result, a doc chunk."""

    actor: Optional[str] = None
    content: str
    source: Optional[str] = None
    source_id: Optional[str] = None
    occurred_at: Optional[datetime] = None
    observed_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


_STATUS_PATTERN = r"^(active|superseded|archived|deleted|needs_review)$"


class MemoryClaim(BaseModel):
    """A durable semantic memory — a stable fact about an entity, project, person."""

    content: str
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: str = Field(default="active", pattern=_STATUS_PATTERN)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EpisodicMemory(BaseModel):
    """Something that happened — an event with actors, dates, outcomes."""

    content: str
    occurred_at: Optional[datetime] = None
    actors: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: str = Field(default="active", pattern=_STATUS_PATTERN)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProceduralMemory(BaseModel):
    """A durable instruction, preference, policy, or style rule."""

    content: str
    applies_to: list[str] = Field(default_factory=list)
    priority: int = 0
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: str = Field(default="active", pattern=_STATUS_PATTERN)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(BaseModel):
    """A request to retrieve memory."""

    question: str
    requester: Optional[str] = None
    mode: Literal["standard", "deep"] = "standard"
    memory_types: list[Literal["semantic", "episodic", "procedural"]] = Field(
        default_factory=list
    )
    required_data: list[str] = Field(default_factory=list)
    allow_general_knowledge: Optional[bool] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalPlan(BaseModel):
    """A structured retrieval plan derived from a memory_query."""

    query_id: str
    vector_queries: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    memory_types: list[Literal["semantic", "episodic", "procedural"]] = Field(
        default_factory=list
    )
    mode: Literal["standard", "deep"] = "standard"
    required_data: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRetrievalResult(BaseModel):
    """Retrieved memories for a query."""

    query_id: str
    plan_id: Optional[str] = None
    retrieved_object_ids: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
    missing_data: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryAnswer(BaseModel):
    """An answer generated from retrieved memory."""

    query_id: str
    retrieval_result_id: Optional[str] = None
    answer: str
    used_memory_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuantityClaim(BaseModel):
    """A numeric fact with ownership and scope."""

    raw_value: str
    value: Optional[float] = None
    unit: Optional[str] = None
    owner: Optional[str] = None
    property: Optional[str] = None
    item_or_event: Optional[str] = None
    exactness: Literal[
        "exact", "approximate", "lower_bound", "upper_bound", "range", "unknown"
    ] = "unknown"
    can_sum_exactly: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalRef(BaseModel):
    """A resolved or unresolved time reference."""

    text: str
    resolved_at: Optional[datetime] = None
    anchor: Optional[str] = None
    resolution_method: Literal[
        "explicit_date",
        "relative_to_observation",
        "relative_to_event",
        "relative_to_benchmark_now",
        "duration_start",
        "unresolved",
    ] = "unresolved"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryConsolidation(BaseModel):
    """A merge or consolidation operation."""

    source_memory_ids: list[str]
    consolidated_memory_id: Optional[str] = None
    reason: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryEvaluation(BaseModel):
    """An evaluation of whether retrieved/used memory helped."""

    answer_id: Optional[str] = None
    query_id: Optional[str] = None
    used_memory_ids: list[str] = Field(default_factory=list)
    outcome: Literal[
        "helpful",
        "unhelpful",
        "incorrect",
        "unsupported",
        "partially_helpful",
        "unknown",
    ] = "unknown"
    score: Optional[float] = None
    notes: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryPolicy(BaseModel):
    """Extraction/retrieval/consolidation policy as graph state."""

    name: str
    description: Optional[str] = None
    extraction_confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    contradiction_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    retrieval_limit: int = Field(default=10, ge=1)
    retrieval_mode_default: Literal["standard", "deep"] = "standard"
    consolidate_duplicates: bool = True
    allow_general_knowledge_in_answers: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryForgetRequest(BaseModel):
    """Manual request to forget (delete) a memory."""

    memory_id: str
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryArchiveRequest(BaseModel):
    """Manual request to archive a memory."""

    memory_id: str
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- registry


OBJECT_TYPES = [
    ObjectType(name="memory_observation", schema=MemoryObservation,
               description="Something the system observed."),
    ObjectType(name="memory_claim", schema=MemoryClaim,
               description="A durable semantic memory."),
    ObjectType(name="episodic_memory", schema=EpisodicMemory,
               description="An event that happened."),
    ObjectType(name="procedural_memory", schema=ProceduralMemory,
               description="A durable instruction or preference."),
    ObjectType(name="memory_query", schema=MemoryQuery,
               description="A request to retrieve memory."),
    ObjectType(name="retrieval_plan", schema=RetrievalPlan,
               description="A structured retrieval plan."),
    ObjectType(name="memory_retrieval_result", schema=MemoryRetrievalResult,
               description="Retrieved memories for a query."),
    ObjectType(name="memory_answer", schema=MemoryAnswer,
               description="An answer generated from retrieved memory."),
    ObjectType(name="quantity_claim", schema=QuantityClaim,
               description="A numeric fact with owner and scope."),
    ObjectType(name="temporal_ref", schema=TemporalRef,
               description="A resolved or unresolved time reference."),
    ObjectType(name="memory_consolidation", schema=MemoryConsolidation,
               description="A consolidation/merge of duplicate memories."),
    ObjectType(name="memory_evaluation", schema=MemoryEvaluation,
               description="An evaluation of whether memory helped."),
    ObjectType(name="memory_policy", schema=MemoryPolicy,
               description="Extraction/retrieval/consolidation policy."),
    ObjectType(name="memory_forget_request", schema=MemoryForgetRequest,
               description="Manual request to forget a memory."),
    ObjectType(name="memory_archive_request", schema=MemoryArchiveRequest,
               description="Manual request to archive a memory."),
]
