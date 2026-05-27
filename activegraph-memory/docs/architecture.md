# architecture

`activegraph-memory` is an ActiveGraph pack. It does not own a runtime, a
storage layer, or a chat loop. Everything it ships is a contribution to a
host ActiveGraph application:

- **Object types** — typed nodes in the graph (`memory_observation`,
  `memory_claim`, …).
- **Relation types** — typed edges (`derived_from`, `supersedes`, …).
- **Behaviors** — pure functions reacting to `object.created` events.
- **Prompts** — versioned text instructions for the LLM-shaped behaviors
  (the current implementation is deterministic; prompts are shipped so a
  future LLM swap is a one-line change per behavior).
- **Tools** — deterministic helpers (keyword search, scoring,
  normalization, deterministic embeddings).
- **Settings** — a `pydantic.BaseModel` of thresholds and feature flags.

## Event-sourced lifecycle

Nothing in the pack mutates state directly. The host application calls
`graph.add_object("memory_observation", …)`. That emits
`object.created`. Behaviors with matching `where=` filters fire in
deterministic order. Each behavior receives:

- the triggering `event`,
- a constrained `BehaviorGraph` wrapper that automatically stamps
  `actor`, `caused_by`, and `frame_id` on every mutation,
- a `ctx` with a scoped `View` (read-only slice of the graph), and
- pack settings as a typed kwarg.

Because behaviors do not call `datetime.now()`, `uuid.uuid4()`, or any
external service, the same event log replayed against the same pack and
settings produces the same graph state.

## Cascade

```
object.created(memory_observation)
  -> extract_candidate_memories
       creates memory_claim / episodic_memory / procedural_memory
       creates quantity_claim / temporal_ref when applicable
       links derived_from + supports
  -> detect_contradictions_<type>          (per-type behaviors)
       supersedes / contradicts older actives
  -> consolidate_memories_<type>           (per-type behaviors)
       memory_consolidation + consolidated_into
  -> resolve_temporal_refs_<type>          (per-type behaviors)
       temporal_ref + has_temporal_ref
  -> attach_numeric_scope_<type>           (per-type behaviors)
       quantity_claim + has_quantity

object.created(memory_query)
  -> plan_memory_retrieval
       creates retrieval_plan

object.created(retrieval_plan)
  -> retrieve_memories
       creates memory_retrieval_result + retrieved_for

object.created(memory_retrieval_result)
  -> fallback_retrieve  (if missing_data)
  -> answer_with_evidence
       creates memory_answer + used_in_answer

object.created(memory_answer)
  -> evaluate_memory_usage
       creates memory_evaluation + validated_by / invalidated_by

object.created(memory_archive_request | memory_forget_request)
  -> archive_memory | forget_memory
       patches target status to archived / deleted
```

## One pack, two graphs

The unit of comparison in `activegraph-memory` is the settings object.
Two `Graph` instances loaded with the same pack but different
`MemorySettings` will produce different memory volumes from the same
observation stream. `examples/fork_memory_policy.py` makes the
difference visible. When ActiveGraph exposes a first-class fork/diff
API, the same example can be rewritten against a single graph.

## Per-type behavior split

ActiveGraph `where=` filters in the current release accept a single
literal type, not a list. Behaviors that conceptually apply to all
three memory types (`memory_claim`, `episodic_memory`,
`procedural_memory`) are registered three times, each delegating to a
shared `_run` / `_compare` body. This is recorded as a known gap in
`docs/activegraph_native_design.md`.
