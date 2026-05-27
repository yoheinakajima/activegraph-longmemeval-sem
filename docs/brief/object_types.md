# Object Types

Implement all object types using Pydantic models or the current ActiveGraph schema convention.

---

## 1. memory_observation

Represents something observed by the system.

**Examples:** user message, assistant message, tool result, document chunk, meeting note, email snippet, benchmark turn, user correction, external event

```python
class MemoryObservation(BaseModel):
    actor: str | None = None
    content: str
    source: str | None = None
    source_id: str | None = None
    occurred_at: datetime | None = None
    observed_at: datetime | None = None
    metadata: dict[str, Any] = {}
```

**Rules:**
- `occurred_at` = when the event described happened
- `observed_at` = when the system ingested or observed it
- Do not conflate `occurred_at` and `observed_at`
- If ActiveGraph provides event timestamps, use those instead of generating timestamps inside behaviors

---

## 2. memory_claim

Represents a durable semantic memory.

**Examples:** "The user prefers lowercase X posts.", "The user dislikes em dashes.", "Fund III target is $20–25M.", "ActiveGraph uses an event log as source of truth."

```python
class MemoryClaim(BaseModel):
    content: str
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    confidence: float = 1.0
    status: Literal[
        "active",
        "superseded",
        "archived",
        "deleted",
        "needs_review"
    ] = "active"
    tags: list[str] = []
    metadata: dict[str, Any] = {}
```

**Rules:**
- Do not require strict subject/predicate/object extraction in the first implementation
- Keep `content` as the primary usable field
- Use structured fields when available
- Do not over-extract from casual messages

---

## 3. episodic_memory

Represents something that happened.

**Examples:** "The user met Variant Fund on May 26, 2026.", "The founder decided not to take capital until $1M in commitments.", "A benchmark run produced a specific result."

```python
class EpisodicMemory(BaseModel):
    content: str
    occurred_at: datetime | None = None
    actors: list[str] = []
    entities: list[str] = []
    source: str | None = None
    confidence: float = 1.0
    status: Literal[
        "active",
        "superseded",
        "archived",
        "deleted",
        "needs_review"
    ] = "active"
    metadata: dict[str, Any] = {}
```

---

## 4. procedural_memory

Represents durable instructions, preferences, policies, or style rules.

**Examples:** "Use lowercase for X posts.", "Avoid em dashes.", "Prefer concise, direct responses.", "When analyzing PDFs, inspect charts visually."

```python
class ProceduralMemory(BaseModel):
    content: str
    applies_to: list[str] = []
    priority: int = 0
    confidence: float = 1.0
    status: Literal[
        "active",
        "superseded",
        "archived",
        "deleted",
        "needs_review"
    ] = "active"
    metadata: dict[str, Any] = {}
```

**Rules:**
- Procedural memories should affect future behavior
- They should be retrievable separately from semantic and episodic memories
- They should support priority
- Higher-priority procedural memory should override lower-priority when clearly conflicting

---

## 5. memory_query

Represents a request to retrieve memory.

```python
class MemoryQuery(BaseModel):
    question: str
    requester: str | None = None
    mode: Literal["standard", "deep"] = "standard"
    memory_types: list[Literal["semantic", "episodic", "procedural"]] = []
    required_data: list[str] = []
    allow_general_knowledge: bool | None = None
    metadata: dict[str, Any] = {}
```

---

## 6. retrieval_plan

Represents a structured retrieval plan.

```python
class RetrievalPlan(BaseModel):
    query_id: str
    vector_queries: list[str] = []
    keywords: list[str] = []
    memory_types: list[Literal["semantic", "episodic", "procedural"]] = []
    mode: Literal["standard", "deep"] = "standard"
    required_data: list[str] = []
    filters: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
```

**Rules:**
- Retrieval planning should be explicit
- The plan should be stored as graph state
- This makes retrieval inspectable and debuggable

---

## 7. memory_retrieval_result

Represents retrieved memories.

```python
class MemoryRetrievalResult(BaseModel):
    query_id: str
    plan_id: str | None = None
    retrieved_object_ids: list[str] = []
    summary: str | None = None
    missing_data: list[str] = []
    confidence: float = 1.0
    metadata: dict[str, Any] = {}
```

---

## 8. memory_answer

Represents an answer generated from retrieved memory.

```python
class MemoryAnswer(BaseModel):
    query_id: str
    retrieval_result_id: str | None = None
    answer: str
    used_memory_ids: list[str] = []
    evidence_ids: list[str] = []
    missing_data: list[str] = []
    confidence: float = 1.0
    metadata: dict[str, Any] = {}
```

**Rules:**
- Answers should link to the memories they used
- Answers should be able to represent missing evidence
- Answers should not silently invent unsupported memories

---

## 9. quantity_claim

Represents a numeric fact with ownership and scope.

```python
class QuantityClaim(BaseModel):
    raw_value: str
    value: float | None = None
    unit: str | None = None
    owner: str | None = None
    property: str | None = None
    item_or_event: str | None = None
    exactness: Literal[
        "exact",
        "approximate",
        "lower_bound",
        "upper_bound",
        "range",
        "unknown"
    ] = "unknown"
    can_sum_exactly: bool = False
    confidence: float = 1.0
    metadata: dict[str, Any] = {}
```

**Reason:** Numeric memory often fails because nearby unrelated numbers are used incorrectly. The graph should encode what each number belongs to.

**Examples:**
- "$20–25M" belongs to Fund III target size
- "36 companies" belongs to fund construction
- "25%" belongs to reserves policy

---

## 10. temporal_ref

Represents a resolved or unresolved time reference.

```python
class TemporalRef(BaseModel):
    text: str
    resolved_at: datetime | None = None
    anchor: str | None = None
    resolution_method: Literal[
        "explicit_date",
        "relative_to_observation",
        "relative_to_event",
        "relative_to_benchmark_now",
        "unresolved"
    ] = "unresolved"
    confidence: float = 1.0
    metadata: dict[str, Any] = {}
```

**Reason:** Memory systems must distinguish:
- when something happened
- when it was observed
- when it was stored
- when the question is being asked

---

## 11. memory_consolidation

Represents a merge or consolidation operation.

```python
class MemoryConsolidation(BaseModel):
    source_memory_ids: list[str]
    consolidated_memory_id: str | None = None
    reason: str
    confidence: float = 1.0
    metadata: dict[str, Any] = {}
```

---

## 12. memory_evaluation

Represents an evaluation of whether retrieved/used memory helped.

```python
class MemoryEvaluation(BaseModel):
    answer_id: str | None = None
    query_id: str | None = None
    used_memory_ids: list[str] = []
    outcome: Literal[
        "helpful",
        "unhelpful",
        "incorrect",
        "unsupported",
        "partially_helpful",
        "unknown"
    ] = "unknown"
    score: float | None = None
    notes: str | None = None
    metadata: dict[str, Any] = {}
```

---

## 13. memory_policy

Represents extraction/retrieval/consolidation policy settings as graph state.

```python
class MemoryPolicy(BaseModel):
    name: str
    description: str | None = None
    extraction_confidence_threshold: float = 0.65
    contradiction_confidence_threshold: float = 0.75
    retrieval_limit: int = 10
    retrieval_mode_default: Literal["standard", "deep"] = "standard"
    consolidate_duplicates: bool = True
    allow_general_knowledge_in_answers: bool = False
    metadata: dict[str, Any] = {}
```

**Reason:** Policies should be comparable across forks. A key ActiveGraph demo should show the same event history under different memory policies.

---

## Additional Request Object Types (Phase 11)

Define these if needed for the forgetting/archival behavior:

```python
class MemoryForgetRequest(BaseModel):
    memory_id: str
    reason: str | None = None
    metadata: dict[str, Any] = {}

class MemoryArchiveRequest(BaseModel):
    memory_id: str
    reason: str | None = None
    metadata: dict[str, Any] = {}
```
