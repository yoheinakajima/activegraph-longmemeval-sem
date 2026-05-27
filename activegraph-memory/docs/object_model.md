# object model

Fifteen object types live in `activegraph_memory/types.py`. Each is a
`pydantic.BaseModel` registered with ActiveGraph via `ObjectType(name=…,
schema=…)` so the runtime validates every `add_object` call against the
declared shape.

| type                       | purpose                                                              |
|----------------------------|----------------------------------------------------------------------|
| `memory_observation`       | Raw input. Never edited.                                             |
| `memory_claim`             | Semantic fact extracted from one or more observations.               |
| `episodic_memory`          | Time-anchored event extracted from an observation.                   |
| `procedural_memory`        | "Always do X" instruction extracted from an observation.             |
| `memory_query`             | A request for retrieval + answer.                                    |
| `retrieval_plan`           | Plan emitted in response to a query.                                 |
| `memory_retrieval_result`  | The hits selected by a plan.                                         |
| `memory_answer`            | Answer assembled strictly from retrieved memories.                   |
| `quantity_claim`           | Scoped numeric fact (raw_value, value, unit, exactness, …).          |
| `temporal_ref`             | Resolved or unresolved time reference.                               |
| `memory_consolidation`     | Marker for "these N memories were merged into one."                   |
| `memory_evaluation`        | Per-answer evaluation (outcome, score, notes).                       |
| `memory_policy`            | Named bundle of thresholds and flags (extension point for fork/diff).|
| `memory_archive_request`   | Operator-issued archive request.                                     |
| `memory_forget_request`    | Operator-issued forget request.                                      |

## Status values

`memory_claim`, `episodic_memory`, and `procedural_memory` all carry a
`status` field with one of:

- `active` — visible to standard retrieval.
- `superseded` — newer memory replaced this one. Hidden from standard
  retrieval unless `include_superseded_in_standard_retrieval=True`.
- `needs_review` — contradicts an existing memory but the supersession
  signal was weak. Hidden from standard retrieval.
- `archived` — taken out of rotation by a request or by consolidation.
  Hidden from standard retrieval.
- `deleted` — explicit forget. Hidden from standard retrieval.

The objects themselves are never removed.

## Provenance

Every object carries provenance stamped by the runtime: the
`caused_by` event id, the active frame id (if any), the actor name,
and the triggering `tool.requested` event ids (when the creator was an
`@llm_behavior` running a tool turn loop). Behaviors must not stamp
provenance themselves — the `BehaviorGraph` wrapper does it
automatically.
