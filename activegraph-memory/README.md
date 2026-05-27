# activegraph-memory

An installable [ActiveGraph](https://pypi.org/project/activegraph/) pack
named `memory` that implements an event-sourced memory lifecycle:
observations become typed memories, memories get reconciled
(contradiction, supersession, consolidation), queries produce plans
and answers grounded in retrieved evidence, and every answer is
evaluated. Memories are never deleted — status transitions
(`active` → `superseded` / `needs_review` / `archived` / `deleted`)
preserve the audit trail.

## 1. What this is

A pack you load into an existing ActiveGraph runtime:

```python
from activegraph import Graph, Runtime
from activegraph_memory import pack, MemorySettings

g = Graph()
rt = Runtime(g)
rt.load_pack(pack, settings=MemorySettings())
```

After load, the pack contributes 15 object types, 12 relation types,
20 registered behaviors, 8 prompts, and a settings schema. It does
not own a runtime, a storage layer, or a chat loop.

## 2. Install

```bash
pip install activegraph
pip install -e .       # from this repo
```

The pack is discoverable via the `activegraph.packs` entry point
group declared in `pyproject.toml`. Once installed, `import
activegraph_memory` succeeds and `activegraph_memory.pack` is the
`Pack` instance the runtime loads.

## 3. Run the basic example

```bash
python examples/basic_memory_run.py
```

Produces output like:

```
object types: {'memory_observation': 1, 'memory_claim': 1,
               'memory_query': 1, 'retrieval_plan': 1,
               'memory_retrieval_result': 1, 'memory_answer': 1,
               'memory_evaluation': 1}
relation types: {'derived_from': 1, 'supports': 1,
                 'retrieved_for': 2, 'used_in_answer': 1,
                 'validated_by': 1}

answer: Yohei prefers lowercase X posts and dislikes em dashes.
used memory ids: ['memory_claim#2']
```

## 4. Memory lifecycle at a glance

```
observation
   │
   ▼
extract ─► memory_claim / episodic / procedural
   │           │
   │           ├─► detect_contradictions ─► supersedes / contradicts
   │           ├─► consolidate           ─► memory_consolidation
   │           ├─► temporal              ─► temporal_ref
   │           └─► numeric               ─► quantity_claim
   │
   ▼
memory_query
   │
   ▼
plan ─► retrieval_plan
            │
            ▼
        retrieve ─► memory_retrieval_result
                       │
                       ▼
                  fallback (if missing_data)
                       │
                       ▼
                  answer_with_evidence ─► memory_answer
                                              │
                                              ▼
                                         evaluate ─► memory_evaluation
```

Full lifecycle in [`docs/memory_lifecycle.md`](docs/memory_lifecycle.md).

## 5. Object and relation model

- 15 object types: `memory_observation`, `memory_claim`,
  `episodic_memory`, `procedural_memory`, `memory_query`,
  `retrieval_plan`, `memory_retrieval_result`, `memory_answer`,
  `quantity_claim`, `temporal_ref`, `memory_consolidation`,
  `memory_evaluation`, `memory_policy`, `memory_archive_request`,
  `memory_forget_request`.
- 12 relation types: `derived_from`, `supports`, `contradicts`,
  `supersedes`, `retrieved_for`, `used_in_answer`, `has_quantity`,
  `has_temporal_ref`, `validated_by`, `invalidated_by`,
  `consolidated_into`, `governed_by_policy`.

See [`docs/object_model.md`](docs/object_model.md) and
[`docs/relation_model.md`](docs/relation_model.md).

## 6. Behaviors

Eleven conceptual behaviors implemented as twenty registered
`Behavior` objects (split per memory type because ActiveGraph's
`where=` filter does not accept `in [...]` yet). See
[`docs/behavior_model.md`](docs/behavior_model.md).

## 7. Determinism

All shipped behaviors are `@behavior`, not `@llm_behavior`. They use
rule-based heuristics so the test suite passes offline with no API
keys and no network. Prompts are shipped under
`activegraph_memory/prompts/` so a future maintainer can swap any
behavior to LLM mode without redesigning the cascade. See
[`docs/prompt_model.md`](docs/prompt_model.md).

## 8. Settings

`MemorySettings` (a `pydantic.BaseModel`) carries thresholds and
feature flags:

| setting                                             | default | meaning                                                                  |
|-----------------------------------------------------|---------|--------------------------------------------------------------------------|
| `extraction_confidence_threshold`                   | 0.65    | minimum confidence to keep an extracted memory                            |
| `contradiction_confidence_threshold`                | 0.75    | minimum confidence to call a contradiction a supersession                 |
| `consolidation_confidence_threshold`                | 0.85    | minimum confidence to consolidate duplicate memories                      |
| `retrieval_mode_default`                            | "standard" | "standard" or "deep" (deep includes superseded/archived)              |
| `retrieval_limit`                                   | 10      | max hits per retrieval                                                    |
| `fallback_retrieval_limit`                          | 5       | max hits in fallback re-search                                            |
| `include_superseded_in_standard_retrieval`          | False   | include `superseded` memories in non-deep retrieval                       |
| `include_archived_in_standard_retrieval`            | False   | include `archived` memories in non-deep retrieval                         |
| `enable_keyword_retrieval`                          | True    | run the keyword search tool                                               |
| `enable_vector_retrieval`                           | False   | run the vector search tool (stub; off by default)                         |
| `enable_contradiction_detection`                    | True    | run `detect_contradictions`                                               |
| `enable_consolidation`                              | True    | run `consolidate_memories`                                                |
| `enable_temporal_resolution`                        | True    | run `resolve_temporal_refs`                                               |
| `enable_numeric_scope`                              | True    | run `attach_numeric_scope`                                                |
| `enable_fallback_retrieval`                         | True    | re-search on `missing_data`                                               |
| `enable_answer_generation`                          | True    | run `answer_with_evidence`                                                |
| `enable_memory_evaluation`                          | True    | run `evaluate_answer`                                                     |
| `allow_general_knowledge_in_answers`                | False   | let the answer behavior speak past retrieval                              |
| `default_policy_name`                               | "default" | label stamped on `memory_retrieval_result.metadata.policy`              |

Two `Graph` instances loaded with the same pack but different
`MemorySettings` form a policy comparison; see
[`examples/fork_memory_policy.py`](examples/fork_memory_policy.py).

## 9. Examples

| script                              | shows                                              |
|-------------------------------------|----------------------------------------------------|
| `examples/basic_memory_run.py`      | full lifecycle end to end                          |
| `examples/contradiction_demo.py`    | supersession patches old memory status              |
| `examples/procedural_memory_demo.py`| "always do X" memories applied to answers          |
| `examples/temporal_memory_demo.py`  | extraction of temporal references                  |
| `examples/numeric_memory_demo.py`   | scoped quantity claims                             |
| `examples/fallback_retrieval_demo.py`| missing-data fallback re-search                   |
| `examples/memory_evaluation_demo.py`| per-answer evaluation                              |
| `examples/fork_memory_policy.py`    | conservative vs aggressive extraction policies     |

## 10. Tests

```bash
pytest
```

51 tests, all offline. The suite covers pack registration, every
object and relation type, the full memory lifecycle, procedural
memory, retrieval planning, evidence linking, answer grounding,
contradiction and supersession, temporal and numeric extraction,
fallback retrieval, consolidation, forgetting and archival,
evaluation, the policy comparison, and an explicit no-network test.

## 11. Project layout

```
activegraph_memory/
├── __init__.py              # assembles the Pack instance
├── settings.py              # MemorySettings (pydantic)
├── constants.py             # status / policy / type constants
├── types.py                 # 15 ObjectType pydantic schemas
├── relations.py             # 12 RelationType declarations
├── behaviors/               # 11 conceptual behaviors (20 registered)
├── prompts/                 # 8 prompts for LLM-mode swap
├── tools/                   # deterministic helpers
└── fixtures/                # 7 .jsonl observation streams
docs/                        # 14 design documents
examples/                    # 8 runnable demos
tests/                       # 17 test files, 51 tests
```

## 12. Rules for behaviors

If you add or modify a behavior, follow the contract in
[`docs/behavior_model.md`](docs/behavior_model.md):

- No `datetime.now()`, `uuid.uuid4()`, or `random` in behavior
  bodies. The runtime stamps timestamps and ids.
- Read through `ctx.view.objects(type=…)` /
  `ctx.view.relations(type=…)`, not `graph.all_objects()`.
- Do not pass `caused_by=` or `rationale=` to `graph.add_object`,
  `graph.add_relation`, or `graph.patch_object`. The
  `BehaviorGraph` wrapper stamps provenance itself.
- Use `graph.propose_patch(target, op, value, rationale=, evidence=)`
  when you want a reviewable patch instead of a direct write.

## 13. Two graphs, not one fork

ActiveGraph does not yet expose a first-class fork/diff API, so the
policy comparison runs two `Graph` instances with different
`MemorySettings` against the same observation stream. When fork/diff
lands, [`examples/fork_memory_policy.py`](examples/fork_memory_policy.py)
collapses to a single graph with two branches.

## 14. Known gaps

Recorded in [`docs/activegraph_native_design.md`](docs/activegraph_native_design.md)
and [`docs/roadmap.md`](docs/roadmap.md):

- `where=` filters take one literal type, so the four behaviors
  conceptually shared across memory types are registered three
  times each (20 behaviors instead of 11). When `in [...]` lands,
  this collapses.
- No first-class `entity` object type, so `about_entity` and
  `same_entity_as` are deferred to v0.2.
- No first-class fork/diff API; the policy demo runs two graphs.
- The `OptionalOpenAIEmbeddingProvider` is a stub; the
  deterministic embedding provider is the default.

## 15. Performance claims

None. The pack ships a deterministic implementation with no
benchmark numbers because the benchmark harness is on the roadmap
([`docs/benchmark_plan.md`](docs/benchmark_plan.md)). The shipped
heuristics are intentionally conservative — they catch obvious
supersession / consolidation / numeric / temporal cases and stay
quiet on the rest, leaving recall for the future LLM-mode swap.

## 16. License

MIT. See [`LICENSE`](LICENSE).
