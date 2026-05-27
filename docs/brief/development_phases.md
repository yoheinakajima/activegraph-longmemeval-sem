# Development Phases

Implement the full system in ordered phases. Do not stop at the first phase unless blocked. Each phase should leave the repo in a working state.

---

## Phase 0: ActiveGraph Research

**Tasks:**
- Inspect ActiveGraph docs
- Inspect ActiveGraph repo
- Identify pack API
- Identify object type API
- Identify relation type API
- Identify behavior API
- Identify LLM behavior API
- Identify tool API
- Identify prompt loading/versioning API
- Identify settings API
- Identify test patterns
- Identify fork/diff APIs

**Output:** `docs/activegraph_native_design.md`

---

## Phase 1: Repository Skeleton

**Create:**
- `pyproject.toml`
- `README.md`
- `LICENSE`
- `.gitignore`
- `activegraph_memory/__init__.py`
- `activegraph_memory/settings.py`
- `activegraph_memory/types.py`
- `activegraph_memory/relations.py`
- `activegraph_memory/constants.py`
- `tests/test_pack_loads.py`

**Requirements:**
- `pip install -e .` works
- Package imports
- Pack exports
- Pack registers via entry point
- Basic pack load test passes

---

## Phase 2: Object and Relation Model

**Implement all object types:**
- `memory_observation`
- `memory_claim`
- `episodic_memory`
- `procedural_memory`
- `memory_query`
- `retrieval_plan`
- `memory_retrieval_result`
- `memory_answer`
- `quantity_claim`
- `temporal_ref`
- `memory_consolidation`
- `memory_evaluation`
- `memory_policy`

**Implement all relation types:**
- `derived_from`
- `supports`
- `contradicts`
- `supersedes`
- `retrieved_for`
- `used_in_answer`
- `has_quantity`
- `has_temporal_ref`
- `validated_by`
- `invalidated_by`
- `consolidated_into`
- `governed_by_policy`

**Tests:**
- `test_object_types.py`
- `test_relation_types.py`

---

## Phase 3: Basic Extraction

**Implement:** `extract_candidate_memories`

**Requirements:**
- Fires on `memory_observation` creation
- Creates semantic/episodic/procedural memory
- Links `derived_from`
- Links `supports`
- Uses LLM behavior or fixture equivalent
- Works offline in tests

**Tests:**
- `test_basic_memory_lifecycle.py` (first half)
- `test_procedural_memory.py` (first half)

---

## Phase 4: Retrieval Planning and Retrieval

**Implement:**
- `plan_memory_retrieval`
- `retrieve_memories`
- `keyword_search` tool

**Requirements:**
- `memory_query` creates `retrieval_plan`
- `retrieval_plan` creates `memory_retrieval_result`
- Retrieved memories link via `retrieved_for`
- Supports semantic/episodic/procedural memory
- Filters inactive/deleted memory
- Respects retrieval limit

**Tests:**
- `test_retrieval_planning.py`
- `test_retrieval_links_evidence.py`

---

## Phase 5: Answer Generation

**Implement:** `answer_with_evidence`

**Requirements:**
- `memory_retrieval_result` creates `memory_answer`
- Answer uses retrieved memories
- Used memories link via `used_in_answer`
- `missing_data` preserved
- Procedural memories influence answer style/instructions

**Tests:**
- `test_answer_with_evidence.py`
- `test_basic_memory_lifecycle.py` (full)
- `test_procedural_memory.py` (full)

---

## Phase 6: Contradiction and Supersession

**Implement:** `detect_contradictions`

**Requirements:**
- New memories are compared to active nearby memories
- `contradicts` relation created when appropriate
- `supersedes` relation created when appropriate
- Old memories patched to `superseded` when safe
- Uncertain cases marked `needs_review`
- No deletion

**Tests:**
- `test_contradiction_supersession.py`

---

## Phase 7: Temporal Reasoning

**Implement:** `resolve_temporal_refs`

**Requirements:**
- Extract temporal refs
- Resolve explicit dates
- Resolve relative dates with anchors
- Preserve unresolved refs
- Link via `has_temporal_ref`
- Distinguish `occurred_at`, `observed_at`, query time

**Tests:** `test_temporal_refs.py`

**Example:** `examples/temporal_memory_demo.py`

---

## Phase 8: Numeric Attribution

**Implement:** `attach_numeric_scope`

**Requirements:**
- Extract numeric facts
- Identify owner/property/unit/exactness
- Avoid unrelated nearby numbers
- Create `quantity_claim`
- Link via `has_quantity`

**Tests:** `test_numeric_scope.py`

**Example:** `examples/numeric_memory_demo.py`

---

## Phase 9: Fallback Retrieval

**Implement:** `fallback_retrieve`

**Requirements:**
- Detect `missing_data`
- Create targeted retrieval plan
- Retrieve again
- Link fallback to original query/result
- Preserve `missing_data` if still unresolved

**Tests:** `test_fallback_retrieval.py`

**Example:** `examples/fallback_retrieval_demo.py`

---

## Phase 10: Consolidation

**Implement:** `consolidate_memories`

**Requirements:**
- Detect duplicate/overlapping memories
- Create consolidated memory when safe
- Create `memory_consolidation` object
- Link source memories via `consolidated_into`
- Preserve evidence
- Do not merge materially different memories

**Tests:** `test_memory_consolidation.py`

---

## Phase 11: Forgetting and Archival

**Implement:** `forget_or_archive_memory`

Add request object types if needed: `memory_archive_request`, `memory_forget_request`

**Requirements:**
- Archive sets status `archived`
- Delete sets status `deleted` or uses ActiveGraph deletion mechanism
- Standard retrieval excludes archived/deleted memories
- Lineage preserved unless official deletion semantics say otherwise

**Tests:** `test_forget_or_archive_memory.py`

**Docs:** `docs/forgetting_and_archival.md`

---

## Phase 12: Memory Usage Evaluation

**Implement:** `evaluate_memory_usage`

**Requirements:**
- Create `memory_evaluation`
- Link answer to evaluation
- Support `helpful`/`unhelpful`/`incorrect`/`unsupported`/`partially_helpful`/`unknown`
- Support benchmark and user correction flows

**Tests:** `test_evaluate_memory_usage.py`

**Example:** `examples/memory_evaluation_demo.py`

---

## Phase 13: Fork/Diff Policy Demo

**Implement:**
- `memory_policy` object
- `governed_by_policy` relation if useful
- `examples/fork_memory_policy.py`
- `tests/test_fork_memory_policy.py`

**Requirements:**
- Same event history can be replayed/forked under different memory policies
- Diff reveals different extracted memories or relations
- Example clearly shows ActiveGraph advantage

If exact fork/diff APIs are unavailable:
- Document limitation
- Simulate comparison with two graph instances
- Keep interface close to future fork/diff API

---

## Phase 14: Documentation Completion

Complete all docs in `docs/`:
- `architecture.md`
- `activegraph_native_design.md`
- `memory_lifecycle.md`
- `object_model.md`
- `relation_model.md`
- `behavior_model.md`
- `prompt_model.md`
- `retrieval_model.md`
- `temporal_reasoning.md`
- `numeric_reasoning.md`
- `contradiction_handling.md`
- `forgetting_and_archival.md`
- `evaluation.md`
- `benchmark_plan.md`
- `roadmap.md`

Docs should be concise. Use diagrams where helpful. Do not make unsupported performance claims.

---

## Phase 15: Benchmark Harness Design

**Implement only if core package is stable.**

Create:
```
activegraph_memory/benchmarks/
  __init__.py
  fixtures.py
  runner.py
  metrics.py
  memory_agent_bench_adapter.py
  longmemeval_adapter.py
```

Or follow current repo conventions if ActiveGraph has its own benchmark patterns.

**Benchmark support should measure:**
- Memory extraction correctness
- Evidence linkage correctness
- Retrieval correctness
- Answer correctness
- Temporal accuracy
- Numeric attribution accuracy
- Contradiction handling
- Fallback usefulness
- Memory usage quality
- Policy comparison across forks

**Rules:**
- Do not require benchmark datasets to be downloaded in normal package tests
- Use small local fixtures for CI

---

## Benchmark Metrics (Phase 15)

| Metric | Description |
|---|---|
| Extraction Precision | Did the system extract only durable memories? Did it avoid trivial memories? |
| Extraction Recall | Did the system capture important durable facts? |
| Evidence Link Accuracy | Does each memory link back to the right observation? |
| Retrieval Accuracy | Did retrieval return the needed memory? Did it avoid irrelevant memories? |
| Answer Grounding | Was the answer supported by retrieved memories? |
| Temporal Accuracy | Were dates and relative references handled correctly? |
| Numeric Attribution Accuracy | Were numbers attached to the correct owner/property? |
| Contradiction Handling | Did the system detect contradiction or supersession correctly? |
| Fallback Usefulness | Did fallback retrieval recover missing evidence? |
| Policy Diff Value | Can different memory policies be replayed/forked and compared? |
