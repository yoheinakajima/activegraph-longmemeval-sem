# behavior model

Eleven conceptual behaviors are implemented as twenty registered
`Behavior` objects (some are split per memory type because the
ActiveGraph `where=` filter does not accept `in [...]` yet). All
behaviors live in `activegraph_memory/behaviors/`.

| behavior                  | triggers on                                                 | creates / patches                                            |
|---------------------------|-------------------------------------------------------------|--------------------------------------------------------------|
| `extract_candidate_memories` | `object.created` (memory_observation)                    | memory_claim / episodic_memory / procedural_memory + quantity_claim + temporal_ref |
| `detect_contradictions_*` | `object.created` (memory_claim, episodic, procedural)       | supersedes / contradicts edges, patches old status            |
| `consolidate_memories_*`  | `object.created` (memory_claim, episodic, procedural)       | memory_consolidation + consolidated_into, patches old status  |
| `resolve_temporal_refs_*` | `object.created` (memory_observation, memory_claim, episodic) | temporal_ref + has_temporal_ref                              |
| `attach_numeric_scope_*`  | `object.created` (memory_observation, memory_claim, episodic) | quantity_claim + has_quantity                                |
| `plan_memory_retrieval`   | `object.created` (memory_query)                              | retrieval_plan                                               |
| `retrieve_memories`       | `object.created` (retrieval_plan)                            | memory_retrieval_result + retrieved_for                      |
| `fallback_retrieve`       | `object.created` (memory_retrieval_result) when missing_data | second memory_retrieval_result (is_fallback=True)            |
| `answer_with_evidence`    | `object.created` (memory_retrieval_result)                   | memory_answer + used_in_answer                               |
| `evaluate_memory_usage`   | `object.created` (memory_answer)                             | memory_evaluation + validated_by / invalidated_by            |
| `archive_memory`          | `object.created` (memory_archive_request)                    | patches target status to `archived`                          |
| `forget_memory`           | `object.created` (memory_forget_request)                     | patches target status to `deleted`                           |

## Determinism

The shipped behaviors are pure `@behavior`, not `@llm_behavior`. They
use rule-based heuristics (keyword overlap, normalized signatures,
regex-based number / date extraction) so the test suite passes
offline with no API keys. Prompts are still shipped under
`activegraph_memory/prompts/` so a future maintainer can swap any
behavior to `@llm_behavior` without redesigning the cascade.

## Rules

- No `datetime.now()`, `uuid.uuid4()`, or `random` calls in behavior
  bodies. The runtime stamps timestamps and ids.
- No reads through `graph.all_objects()` / `graph.all_relations()`.
  Iterate `ctx.view.objects(type=…)` / `ctx.view.relations(type=…)`
  instead — the wrapper does not expose the underlying graph's
  iteration methods, and `ctx.view` is the supported read surface.
- No `caused_by=` / `rationale=` kwargs on `graph.add_object`,
  `graph.add_relation`, or `graph.patch_object`. The wrapper stamps
  provenance itself.
- Use `graph.propose_patch(target, op, value, rationale=, evidence=)`
  when you want a reviewable patch instead of a direct write.
