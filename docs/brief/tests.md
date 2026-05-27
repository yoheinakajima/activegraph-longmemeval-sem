# Tests

All tests must be deterministic. No live OpenAI calls. No live web calls. No external services.

Use fixture LLM outputs, mock tools, or deterministic tools.

Store tests in: `tests/`

---

## test_pack_loads.py

Assert:
- package imports
- pack exists
- pack name is `memory`
- object types are registered
- relation types are registered
- behaviors are registered
- settings schema loads
- prompts load

---

## test_object_types.py

Assert all object schemas validate representative examples:
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

---

## test_relation_types.py

Assert relation types register correctly:
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

---

## test_basic_memory_lifecycle.py

Flow:
1. Add `memory_observation`
2. Run runtime
3. Assert memory object created
4. Assert `derived_from` relation exists
5. Assert `supports` relation exists
6. Add `memory_query`
7. Run runtime
8. Assert `retrieval_plan` exists
9. Assert `memory_retrieval_result` exists
10. Assert `memory_answer` exists
11. Assert `used_in_answer` relation exists

---

## test_procedural_memory.py

Flow:
1. Add procedural preference observation
2. Run runtime
3. Assert `procedural_memory` created
4. Query for style guidance
5. Assert procedural memory retrieved
6. Assert answer uses procedural memory

---

## test_contradiction_supersession.py

Flow:
1. Add initial memory
2. Add superseding memory
3. Run runtime
4. Assert `contradicts` or `supersedes` relation exists
5. Assert old memory is not deleted
6. Assert old memory status is `superseded` or `needs_review`

---

## test_retrieval_links_evidence.py

Assert:
- Retrieval creates `memory_retrieval_result`
- Relevant memories are linked via `retrieved_for`
- Irrelevant memories are not linked

---

## test_answer_with_evidence.py

Assert:
- Answer uses retrieved memory
- `used_in_answer` relation exists
- Unsupported answer is not generated when evidence is missing
- `missing_data` is populated when needed

---

## test_retrieval_planning.py

Assert:
- `memory_query` creates `retrieval_plan`
- Simple query uses `standard` mode
- Timeline or numeric query uses `deep` mode when appropriate
- `required_data` is populated when appropriate

---

## test_fallback_retrieval.py

Assert:
- `missing_data` triggers fallback
- Fallback creates targeted retrieval plan
- Fallback result links back to original query
- Missing data is reduced or preserved explicitly

---

## test_temporal_refs.py

Assert:
- Explicit date is resolved
- Relative date with anchor is resolved
- Relative date without anchor remains unresolved
- `temporal_ref` is linked with `has_temporal_ref`

---

## test_numeric_scope.py

Assert:
- `quantity_claim` is created
- Number is attached to correct owner/property
- Nearby unrelated number is not misattributed
- `has_quantity` relation exists

---

## test_memory_consolidation.py

Assert:
- Duplicate memories can consolidate
- Source memories link to consolidated memory
- Evidence is preserved
- Materially different memories are not merged

---

## test_forget_or_archive_memory.py

Assert:
- Archive changes status to `archived`
- Archived memory is excluded from standard retrieval
- Deleted memory is excluded from retrieval
- Lineage is preserved unless ActiveGraph has explicit deletion semantics

---

## test_evaluate_memory_usage.py

Assert:
- `memory_answer` can be evaluated
- `memory_evaluation` is created
- `validated_by` or `invalidated_by` relation exists

---

## test_fork_memory_policy.py

Assert:
- Same event prefix can produce different memory states under different policies
- Diff can be inspected or approximated
- Policy objects or settings are linked to results if possible

---

## test_no_live_network_in_tests.py

Assert or enforce:
- Tests do not require external API keys
- Tests do not call live OpenAI
- Tests do not call web
- Tests pass offline
