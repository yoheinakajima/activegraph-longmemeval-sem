# activegraph-memory: Full Todo List

Track every task from start to full completion. Check off items as they are completed.

---

## Phase 0: ActiveGraph Research

- [ ] Read ActiveGraph README
- [ ] Read ActiveGraph pack docs
- [ ] Read ActiveGraph behavior docs
- [ ] Read ActiveGraph LLM behavior docs
- [ ] Read ActiveGraph tool docs
- [ ] Read ActiveGraph event log docs
- [ ] Read ActiveGraph object/relation schema docs
- [ ] Read ActiveGraph prompt docs
- [ ] Read ActiveGraph settings docs
- [ ] Read ActiveGraph fork/diff docs
- [ ] Read existing first-party or example packs
- [ ] Read existing tests for packs, behaviors, tools, prompts, fork/diff
- [ ] Identify exact pack API
- [ ] Identify exact object type API
- [ ] Identify exact relation type API
- [ ] Identify exact behavior API
- [ ] Identify exact LLM behavior API
- [ ] Identify exact tool API
- [ ] Identify exact prompt loading/versioning API
- [ ] Identify exact settings API
- [ ] Identify test patterns
- [ ] Identify fork/diff APIs (document if unavailable)
- [ ] Write `docs/activegraph_native_design.md` summarizing all findings and gaps

---

## Phase 1: Repository Skeleton

- [ ] Create `pyproject.toml` with correct entry point: `[project.entry-points."activegraph.packs"] memory = "activegraph_memory:pack"`
- [ ] Confirm correct entry point group name from ActiveGraph source
- [ ] Create `README.md` (initial version — complete in Phase 14)
- [ ] Create `LICENSE`
- [ ] Create `.gitignore`
- [ ] Create `activegraph_memory/__init__.py` (exports `pack`)
- [ ] Create `activegraph_memory/settings.py` (MemorySettings schema)
- [ ] Create `activegraph_memory/types.py` (stub — flesh out in Phase 2)
- [ ] Create `activegraph_memory/relations.py` (stub — flesh out in Phase 2)
- [ ] Create `activegraph_memory/constants.py`
- [ ] Create `tests/test_pack_loads.py`
- [ ] Verify: `pip install -e .` works
- [ ] Verify: package imports as `activegraph_memory`
- [ ] Verify: pack exports correctly
- [ ] Verify: pack registers via entry point
- [ ] Verify: `test_pack_loads.py` passes

---

## Phase 2: Object and Relation Model

### Object types (in `activegraph_memory/types.py` or separate files)
- [ ] `memory_observation` — with `actor`, `content`, `source`, `source_id`, `occurred_at`, `observed_at`, `metadata`
- [ ] `memory_claim` — with `content`, `subject`, `predicate`, `object`, `confidence`, `status`, `tags`, `metadata`
- [ ] `episodic_memory` — with `content`, `occurred_at`, `actors`, `entities`, `source`, `confidence`, `status`, `metadata`
- [ ] `procedural_memory` — with `content`, `applies_to`, `priority`, `confidence`, `status`, `metadata`
- [ ] `memory_query` — with `question`, `requester`, `mode`, `memory_types`, `required_data`, `allow_general_knowledge`, `metadata`
- [ ] `retrieval_plan` — with `query_id`, `vector_queries`, `keywords`, `memory_types`, `mode`, `required_data`, `filters`, `metadata`
- [ ] `memory_retrieval_result` — with `query_id`, `plan_id`, `retrieved_object_ids`, `summary`, `missing_data`, `confidence`, `metadata`
- [ ] `memory_answer` — with `query_id`, `retrieval_result_id`, `answer`, `used_memory_ids`, `evidence_ids`, `missing_data`, `confidence`, `metadata`
- [ ] `quantity_claim` — with `raw_value`, `value`, `unit`, `owner`, `property`, `item_or_event`, `exactness`, `can_sum_exactly`, `confidence`, `metadata`
- [ ] `temporal_ref` — with `text`, `resolved_at`, `anchor`, `resolution_method`, `confidence`, `metadata`
- [ ] `memory_consolidation` — with `source_memory_ids`, `consolidated_memory_id`, `reason`, `confidence`, `metadata`
- [ ] `memory_evaluation` — with `answer_id`, `query_id`, `used_memory_ids`, `outcome`, `score`, `notes`, `metadata`
- [ ] `memory_policy` — with `name`, `description`, thresholds, limits, flags, `metadata`

### Relation types (in `activegraph_memory/relations.py`)
- [ ] `derived_from`
- [ ] `supports`
- [ ] `contradicts`
- [ ] `supersedes`
- [ ] `retrieved_for`
- [ ] `used_in_answer`
- [ ] `has_quantity`
- [ ] `has_temporal_ref`
- [ ] `validated_by`
- [ ] `invalidated_by`
- [ ] `consolidated_into`
- [ ] `governed_by_policy`
- [ ] `about_entity` (defer if entity type unavailable)
- [ ] `same_entity_as` (defer if entity type unavailable)

### Tests
- [ ] Write `tests/test_object_types.py` — validate all 13 schemas with representative examples
- [ ] Write `tests/test_relation_types.py` — assert all 12+ relation types register
- [ ] All tests pass offline

---

## Phase 3: Basic Extraction

- [ ] Create `activegraph_memory/behaviors/__init__.py`
- [ ] Create `activegraph_memory/behaviors/extract_candidate_memories.py`
  - [ ] Trigger on `object.created where object.type == "memory_observation"`
  - [ ] Use LLM behavior (not direct LLM call) for extraction decisions
  - [ ] Create `memory_claim`, `episodic_memory`, `procedural_memory` as appropriate
  - [ ] Create `quantity_claim` if numeric facts present
  - [ ] Create `temporal_ref` if time references present
  - [ ] Link `derived_from` (memory → observation)
  - [ ] Link `supports` (observation → memory)
  - [ ] Respect `extraction_confidence_threshold` from settings
  - [ ] No `datetime.now()`, `uuid.uuid4()`, or direct LLM calls in behavior body
- [ ] Create `activegraph_memory/prompts/extract_candidate_memories.md`
  - [ ] Structured output: `memory_type`, `content`, `confidence`, `reason`, `quantities`, `temporal_refs`
  - [ ] Conservative extraction rules
- [ ] Create fixture: `activegraph_memory/fixtures/simple_conversation.jsonl`
- [ ] Create fixture: `activegraph_memory/fixtures/procedural_memory.jsonl`
- [ ] Write `tests/test_basic_memory_lifecycle.py` (first half — extraction only)
- [ ] Write `tests/test_procedural_memory.py` (first half — extraction only)
- [ ] All tests pass offline using fixtures

---

## Phase 4: Retrieval Planning and Retrieval

- [ ] Create `activegraph_memory/behaviors/plan_memory_retrieval.py`
  - [ ] Trigger on `object.created where object.type == "memory_query"`
  - [ ] Create `retrieval_plan` with keywords, vector_queries, memory_types, mode, required_data, filters
  - [ ] Select `standard` vs `deep` mode appropriately
- [ ] Create `activegraph_memory/prompts/plan_memory_retrieval.md`
- [ ] Create `activegraph_memory/behaviors/retrieve_memories.py`
  - [ ] Trigger on `object.created where object.type == "retrieval_plan"`
  - [ ] Search across `memory_claim`, `episodic_memory`, `procedural_memory`
  - [ ] Filter `archived` and `deleted` by default
  - [ ] Rank: active first, by confidence, keyword match, procedural priority
  - [ ] Create `memory_retrieval_result`
  - [ ] Add `retrieved_for` relations
  - [ ] Respect `retrieval_limit` from settings
- [ ] Create `activegraph_memory/tools/__init__.py`
- [ ] Create `activegraph_memory/tools/keyword_search.py` (deterministic, no network)
- [ ] Create `activegraph_memory/tools/text_normalize.py` (deterministic)
- [ ] Create `activegraph_memory/tools/scoring.py` (deterministic)
- [ ] Write `tests/test_retrieval_planning.py`
- [ ] Write `tests/test_retrieval_links_evidence.py`
- [ ] All tests pass offline

---

## Phase 5: Answer Generation

- [ ] Create `activegraph_memory/behaviors/answer_with_evidence.py`
  - [ ] Trigger on `object.created where object.type == "memory_retrieval_result"`
  - [ ] Create `memory_answer` from retrieved memories
  - [ ] Add `used_in_answer` relations
  - [ ] Apply procedural memories as style/instruction constraints
  - [ ] Populate `missing_data` if evidence insufficient
  - [ ] Do not hallucinate unsupported memories
  - [ ] No direct LLM calls in behavior body
- [ ] Create `activegraph_memory/prompts/answer_with_evidence.md`
- [ ] Write `tests/test_answer_with_evidence.py`
- [ ] Complete `tests/test_basic_memory_lifecycle.py` (full end-to-end)
- [ ] Complete `tests/test_procedural_memory.py` (full flow)
- [ ] All tests pass offline

---

## Phase 6: Contradiction and Supersession

- [ ] Create `activegraph_memory/behaviors/detect_contradictions.py`
  - [ ] Trigger on `object.created where object.type in ["memory_claim", "episodic_memory", "procedural_memory"]`
  - [ ] Compare new memory to existing active memories of same type
  - [ ] Create `contradicts` relation when appropriate
  - [ ] Create `supersedes` relation when appropriate
  - [ ] Patch old memory status to `superseded` or `needs_review`
  - [ ] No deletion of old memories
  - [ ] Respect `contradiction_confidence_threshold` from settings
- [ ] Create `activegraph_memory/prompts/detect_contradictions.md`
- [ ] Create fixture: `activegraph_memory/fixtures/contradiction_conversation.jsonl`
- [ ] Write `tests/test_contradiction_supersession.py`
- [ ] All tests pass offline

---

## Phase 7: Temporal Reasoning

- [ ] Create `activegraph_memory/behaviors/resolve_temporal_refs.py`
  - [ ] Trigger on `object.created where object.type in ["memory_claim", "episodic_memory", "memory_observation"]`
  - [ ] Extract temporal references (today, yesterday, last week, May 26, Q1 2026, etc.)
  - [ ] Resolve explicit dates
  - [ ] Resolve relative dates when anchor is clear
  - [ ] Preserve unresolved references
  - [ ] Create `temporal_ref` objects
  - [ ] Add `has_temporal_ref` relations
  - [ ] Distinguish event time / observation time / storage time / query time
- [ ] Create `activegraph_memory/prompts/resolve_temporal_refs.md`
- [ ] Create fixture: `activegraph_memory/fixtures/temporal_memory.jsonl`
- [ ] Write `tests/test_temporal_refs.py`
- [ ] Write `examples/temporal_memory_demo.py`
- [ ] All tests pass offline

---

## Phase 8: Numeric Attribution

- [ ] Create `activegraph_memory/behaviors/attach_numeric_scope.py`
  - [ ] Trigger on `object.created where object.type in ["memory_claim", "episodic_memory", "memory_observation"]`
  - [ ] Extract numbers and quantities
  - [ ] Identify: raw value, normalized value, unit, owner, property, item/event, exactness, can_sum_exactly
  - [ ] Create `quantity_claim` objects
  - [ ] Add `has_quantity` relations
  - [ ] Do not misattribute nearby unrelated numbers
- [ ] Create `activegraph_memory/prompts/attach_numeric_scope.md`
- [ ] Create fixture: `activegraph_memory/fixtures/numeric_memory.jsonl`
- [ ] Write `tests/test_numeric_scope.py`
- [ ] Write `examples/numeric_memory_demo.py`
- [ ] All tests pass offline

---

## Phase 9: Fallback Retrieval

- [ ] Create `activegraph_memory/behaviors/fallback_retrieve.py`
  - [ ] Trigger on `missing_data` present in `memory_retrieval_result` (or custom event)
  - [ ] Create targeted retrieval plan for each missing item
  - [ ] Run focused retrieval
  - [ ] Merge results into new retrieval result
  - [ ] Preserve relation to original query
  - [ ] Record that fallback was used
  - [ ] Preserve `missing_data` if still unresolved after fallback
- [ ] Create fixture: `activegraph_memory/fixtures/fallback_retrieval.jsonl`
- [ ] Write `tests/test_fallback_retrieval.py`
- [ ] Write `examples/fallback_retrieval_demo.py`
- [ ] All tests pass offline

---

## Phase 10: Consolidation

- [ ] Create `activegraph_memory/behaviors/consolidate_memories.py`
  - [ ] Trigger on memory creation and/or scheduled event (use whatever ActiveGraph supports)
  - [ ] Find duplicate or overlapping memories
  - [ ] Create consolidated memory if useful
  - [ ] Create `memory_consolidation` object
  - [ ] Add `consolidated_into` relations from source memories to consolidated memory
  - [ ] Patch old memories to `archived` or `superseded`
  - [ ] Do not merge materially different memories
  - [ ] Preserve all evidence links
- [ ] Create `activegraph_memory/prompts/consolidate_memories.md`
- [ ] Write `tests/test_memory_consolidation.py`
- [ ] All tests pass offline

---

## Phase 11: Forgetting and Archival

- [ ] Create `activegraph_memory/behaviors/forget_or_archive_memory.py`
  - [ ] Define request object types: `memory_forget_request`, `memory_archive_request`
  - [ ] Archive: patch status to `archived`, preserve lineage, exclude from normal retrieval
  - [ ] Delete: use ActiveGraph deletion mechanism or patch to `deleted`
  - [ ] Make behavior explicit and auditable
- [ ] Write `tests/test_forget_or_archive_memory.py`
- [ ] Write `docs/forgetting_and_archival.md`
- [ ] All tests pass offline

---

## Phase 12: Memory Usage Evaluation

- [ ] Create `activegraph_memory/behaviors/evaluate_memory_usage.py`
  - [ ] Trigger on `memory_answer` creation, manual evaluation, benchmark event, user correction
  - [ ] Create `memory_evaluation`
  - [ ] Link answer to evaluation via `validated_by` or `invalidated_by`
  - [ ] Support all outcome values: helpful/unhelpful/incorrect/unsupported/partially_helpful/unknown
  - [ ] Support benchmark and user correction flows
  - [ ] Do not mutate source memory aggressively in first pass
- [ ] Create `activegraph_memory/prompts/evaluate_memory_usage.md`
- [ ] Write `tests/test_evaluate_memory_usage.py`
- [ ] Write `examples/memory_evaluation_demo.py`
- [ ] All tests pass offline

---

## Phase 13: Fork/Diff Policy Demo

- [ ] Register `memory_policy` object type (if not already done in Phase 2)
- [ ] Register `governed_by_policy` relation (if not already done in Phase 2)
- [ ] Write `examples/fork_memory_policy.py`
  - [ ] Same observation history
  - [ ] Fork A: conservative extraction threshold
  - [ ] Fork B: aggressive extraction threshold
  - [ ] Show Fork B extracts more memories than Fork A
  - [ ] Show diff reveals policy-driven difference
  - [ ] If fork/diff API unavailable: use two graph instances and document limitation
- [ ] Create fixture: `activegraph_memory/fixtures/policy_comparison.jsonl`
- [ ] Write `tests/test_fork_memory_policy.py`
- [ ] All tests pass offline

---

## Phase 14: Documentation Completion

- [ ] Write `docs/architecture.md`
- [ ] Complete `docs/activegraph_native_design.md` (initial version from Phase 0)
- [ ] Write `docs/memory_lifecycle.md` (include lifecycle diagram)
- [ ] Write `docs/object_model.md`
- [ ] Write `docs/relation_model.md`
- [ ] Write `docs/behavior_model.md`
- [ ] Write `docs/prompt_model.md`
- [ ] Write `docs/retrieval_model.md`
- [ ] Write `docs/temporal_reasoning.md`
- [ ] Write `docs/numeric_reasoning.md`
- [ ] Write `docs/contradiction_handling.md`
- [ ] Write `docs/forgetting_and_archival.md` (if not done in Phase 11)
- [ ] Write `docs/evaluation.md`
- [ ] Write `docs/benchmark_plan.md`
- [ ] Write `docs/roadmap.md`
- [ ] Complete `README.md` with all 16 required sections (see `docs/brief/readme_requirements.md`)
- [ ] Add memory lifecycle diagram to README or docs
- [ ] Verify: README uses real APIs (updated after Phase 0 research)
- [ ] Verify: No unsupported performance claims

---

## Phase 15: Benchmark Harness (only if core is stable)

- [ ] Create `activegraph_memory/benchmarks/__init__.py`
- [ ] Create `activegraph_memory/benchmarks/fixtures.py`
- [ ] Create `activegraph_memory/benchmarks/runner.py`
- [ ] Create `activegraph_memory/benchmarks/metrics.py`
- [ ] Create `activegraph_memory/benchmarks/memory_agent_bench_adapter.py`
- [ ] Create `activegraph_memory/benchmarks/longmemeval_adapter.py`
- [ ] Implement metric scaffolding for all 10 benchmark metrics
- [ ] Verify: benchmark datasets not required for normal `pytest` run
- [ ] Verify: small local fixtures pass in CI

---

## Remaining Standalone Tasks

### Tools
- [ ] Create `activegraph_memory/tools/embeddings.py`
  - [ ] `DeterministicEmbeddingProvider` (for tests, no network)
  - [ ] `OptionalOpenAIEmbeddingProvider` (if tool conventions allow)
- [ ] Create `activegraph_memory/tools/vector_search.py` (optional dependency, mock in tests)

### Network / Offline Safety
- [ ] Write `tests/test_no_live_network_in_tests.py`
- [ ] Confirm all tests pass with no API keys and no network access

### Examples (remaining)
- [ ] Write `examples/basic_memory_run.py`
- [ ] Write `examples/contradiction_demo.py`
- [ ] Write `examples/procedural_memory_demo.py`

---

## Final Verification: Acceptance Criteria

Run through every item in `docs/brief/acceptance_criteria.md`:

### Packaging
- [ ] `pip install -e .` works
- [ ] Package imports as `activegraph_memory`
- [ ] Package exports `pack`
- [ ] Pack is discoverable through ActiveGraph entry points

### ActiveGraph Integration
- [ ] Pack loads in ActiveGraph runtime
- [ ] Object types register
- [ ] Relation types register
- [ ] Behaviors register
- [ ] Settings schema works
- [ ] Prompts load
- [ ] Tools load if implemented

### Memory Lifecycle
- [ ] `memory_observation` can create memory objects
- [ ] Memory objects link to observations
- [ ] `memory_query` creates `retrieval_plan`
- [ ] `retrieval_plan` creates `memory_retrieval_result`
- [ ] Retrieved memories link to result
- [ ] `memory_retrieval_result` creates `memory_answer`
- [ ] Used memories link to answer

### Advanced Memory
- [ ] Contradictions can be detected
- [ ] Supersession can be represented
- [ ] Temporal references can be extracted/resolved
- [ ] Numeric claims can be scoped
- [ ] Fallback retrieval can run
- [ ] Memories can be consolidated
- [ ] Memories can be archived/forgotten
- [ ] Memory usage can be evaluated

### Fork/Diff
- [ ] Different memory policies can be compared over the same or similar event history
- [ ] Example demonstrates why event-sourced memory matters

### Tests
- [ ] Tests pass offline
- [ ] Tests require no API keys
- [ ] Tests require no network
- [ ] Tests cover all major object types
- [ ] Tests cover all major relation types
- [ ] Tests cover all major behaviors

### Docs
- [ ] README is clear
- [ ] Architecture docs exist
- [ ] Memory lifecycle docs exist
- [ ] Object/relation/behavior docs exist
- [ ] Examples are documented
- [ ] Roadmap is documented
- [ ] Benchmark plan is documented

### Quality
- [ ] Simple readable Python
- [ ] Typed models
- [ ] Small modules
- [ ] Deterministic tests
- [ ] No hidden side effects
- [ ] No unsupported performance claims
