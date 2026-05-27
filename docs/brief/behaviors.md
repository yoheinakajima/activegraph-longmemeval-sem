# Behaviors

Use ActiveGraph behaviors, LLM behaviors, and tools according to current framework conventions.

**Determinism rules** — see `docs/brief/overview.md` for the full list of what is forbidden inside behavior bodies.

---

## Behavior 1: extract_candidate_memories

**Purpose:** Extract durable memory objects from a new `memory_observation`.

**Trigger:**
```
object.created where object.type == "memory_observation"
```
Use exact ActiveGraph event/filter syntax after checking docs.

**Behavior:**
For each observation, decide whether it contains durable memory.

May create:
- `memory_claim`
- `episodic_memory`
- `procedural_memory`
- `quantity_claim`
- `temporal_ref`

For each created memory:
- link memory to source observation with `derived_from`
- link source observation to memory with `supports`
- attach `quantity_claim` objects if numeric facts are extracted
- attach `temporal_ref` objects if time references are extracted

**Extraction Guidelines — Prioritize:**
- durable user preferences
- durable project facts
- durable entity facts
- explicit decisions
- corrections
- procedural instructions
- facts likely to matter later
- dated events
- important numbers with clear ownership

**Extraction Guidelines — Avoid:**
- trivial one-off phrasing
- temporary context with no future value
- unsupported inference
- overly broad summarization
- conversational filler

**Memory Type Selection:**
- `procedural_memory` → instructions, preferences, style rules, policies
- `episodic_memory` → events with actors, dates, outcomes
- `memory_claim` → stable facts about entities, projects, people

**Rules:**
- Use LLM behavior for extraction decisions
- Use fixture/mock LLM output in tests
- Respect `extraction_confidence_threshold` from settings
- Do not extract if confidence is below threshold
- Generate one memory per distinct durable fact, not one per sentence

---

## Behavior 2: detect_contradictions

**Purpose:** Detect contradictions or supersessions between a new memory and existing active memories.

**Trigger:**
```
object.created where object.type in [
  "memory_claim",
  "episodic_memory",
  "procedural_memory"
]
```

**Behavior:**
Compare new memory against existing active memories of the same type.

If contradiction is detected:
- create `contradicts` relation between conflicting memories
- patch old memory status to `needs_review` (if uncertain) or `superseded` (if clearly superseded)

If supersession is detected:
- create `supersedes` relation from new memory to old memory
- patch old memory status to `superseded`

**Rules:**
- Do not delete old memories — preserve lineage
- Weak tension ≠ contradiction — use `needs_review` when uncertain
- Only compare memories of relevant types
- Use LLM behavior for contradiction judgment
- Respect `contradiction_confidence_threshold` from settings

---

## Behavior 3: plan_memory_retrieval

**Purpose:** Convert a `memory_query` into a structured `retrieval_plan`.

**Trigger:**
```
object.created where object.type == "memory_query"
```

**Behavior:**
Create a `retrieval_plan` object.

The plan should include:
- `keywords`
- `vector_queries`
- `memory_types`
- `mode`
- `required_data`
- `filters`

**Retrieval Modes:**

`standard` — use for:
- simple questions
- direct preference lookup

`deep` — use for:
- timelines
- aggregations
- multi-hop questions
- questions involving dates
- questions involving numbers
- questions involving contradictions
- questions requiring history

**Output:** Create `retrieval_plan`, link it to query if relation exists or store `query_id`.

---

## Behavior 4: retrieve_memories

**Purpose:** Retrieve relevant memories for a `retrieval_plan` or `memory_query`.

**Trigger (preferred):**
```
object.created where object.type == "retrieval_plan"
```

**Trigger (fallback):**
```
object.created where object.type == "memory_query"
```

**Behavior:**
Retrieve relevant memory objects. Search across:
- `memory_claim`
- `episodic_memory`
- `procedural_memory`

Using:
- keyword search
- graph filters
- optional vector search
- procedural rule matching
- status filtering (exclude `archived`, `deleted`)
- temporal filtering

**Ranking:** Rank active memories first. Prefer memories with:
- direct keyword match
- strong evidence
- higher confidence
- recent supersession status if relevant
- procedural priority when procedural memory is requested

Include superseded memories only when the query asks about history or why something changed.

**Output:** Create `memory_retrieval_result`. Add `retrieved_for` relations from retrieved memories to the query/result.

---

## Behavior 5: fallback_retrieve

**Purpose:** Run a second retrieval pass when required evidence is missing.

**Trigger:**
```
memory.required_data_missing
```
or:
```
object.created where object.type == "memory_retrieval_result" and missing_data is non-empty
```
Use the exact ActiveGraph mechanism available.

**Behavior:**
For each missing item:
- create targeted retrieval plan
- run focused retrieval
- merge results into a new retrieval result
- preserve relation to original query
- record that fallback was used

**Rules:**
- Fallback should be targeted — do not broaden retrieval blindly
- If evidence remains missing, preserve `missing_data`

---

## Behavior 6: answer_with_evidence

**Purpose:** Generate an answer from retrieved memories.

**Trigger:**
```
object.created where object.type == "memory_retrieval_result"
```

**Behavior:**
Use retrieved memory objects to create a grounded answer.

Create `memory_answer`.

Add `used_in_answer` relations from actually used memories to the answer.

**Rules:**
- Answer only from retrieved memories unless settings explicitly allow general knowledge
- If evidence is insufficient, say so in the answer and populate `missing_data`
- Use procedural memories as style/instruction constraints
- Do not hallucinate unsupported memories
- Do not cite internal object IDs in user-facing prose unless examples require it

---

## Behavior 7: resolve_temporal_refs

**Purpose:** Extract and resolve temporal references from memory objects.

**Trigger:**
```
object.created where object.type in [
  "memory_claim",
  "episodic_memory",
  "memory_observation"
]
```

**Behavior:**
Find temporal references such as: `today`, `yesterday`, `last week`, `in May`, `May 26`, `Q1 2026`, `after the meeting`, `before the fundraise`.

Resolve when possible. Create `temporal_ref`. Add `has_temporal_ref` relations.

**Rules:**
- Preserve unresolved references
- Do not over-resolve ambiguous references
- Record the anchor used for resolution
- Distinguish: event time, observation time, storage time, query time

---

## Behavior 8: attach_numeric_scope

**Purpose:** Extract numeric facts and attach ownership/scope.

**Trigger:**
```
object.created where object.type in [
  "memory_claim",
  "episodic_memory",
  "memory_observation"
]
```

**Behavior:**
Find numbers and quantities. For each quantity, determine:
- raw value
- normalized value if possible
- unit
- owner
- property
- item/event
- exactness
- whether it can be safely summed

Create `quantity_claim`. Add `has_quantity` relations.

**Rules:**
- Do not attach numbers to the wrong entity
- Do not use nearby numbers as evidence unless ownership is clear
- Represent approximate values as approximate
- Represent ranges as ranges, or preserve raw value if no range schema is available

---

## Behavior 9: consolidate_memories

**Purpose:** Merge duplicate or overlapping memories.

**Trigger (any of):**
```
object.created where object.type in ["memory_claim", "episodic_memory", "procedural_memory"]
scheduled consolidation event
manual consolidation request
```
Use whatever ActiveGraph supports.

**Behavior:**
Find duplicate or overlapping memories. Create a consolidated memory if useful.

Create `memory_consolidation`. Add `consolidated_into` relations from source memories to consolidated memory.

Patch old memories to `archived` or `superseded` depending on semantics.

**Rules:**
- Do not consolidate memories that differ materially
- Do not lose evidence links
- The consolidated memory should preserve references to source memories and original observations

---

## Behavior 10: forget_or_archive_memory

**Purpose:** Support explicit forgetting or archival flows.

**Trigger (any of):**
- manual forget request object
- manual archive request object
- procedural deletion instruction

Define object types if needed: `memory_forget_request`, `memory_archive_request`

**Behavior:**

For archive:
- patch memory status to `archived`
- preserve lineage
- exclude archived memory from normal retrieval

For delete:
- use ActiveGraph's established privacy/deletion mechanism if available
- otherwise patch status to `deleted` and exclude from retrieval

**Rules:**
- Do not permanently erase event history unless ActiveGraph has an established deletion/privacy mechanism
- Make the behavior explicit and auditable

---

## Behavior 11: evaluate_memory_usage

**Purpose:** Evaluate whether retrieved/used memory helped produce a good answer.

**Trigger (any of):**
```
object.created where object.type == "memory_answer"
manual evaluation request
benchmark evaluation event
user correction event
```

**Behavior:**
Create `memory_evaluation`. Link evaluation to answer with `validated_by` or `invalidated_by` where appropriate.

**Evaluation Outcomes:**
- `helpful`
- `unhelpful`
- `incorrect`
- `unsupported`
- `partially_helpful`
- `unknown`

**Rules:**
- This behavior is important for future learning
- It should support benchmark integrations
- It should not mutate source memory aggressively in the first pass
