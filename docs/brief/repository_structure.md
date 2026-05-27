# Repository Structure

Use this structure unless current ActiveGraph conventions strongly suggest a better one.

```
activegraph-memory/
  README.md
  LICENSE
  pyproject.toml
  .gitignore
  activegraph_memory/
    __init__.py
    settings.py
    types.py
    relations.py
    constants.py
    behaviors/
      __init__.py
      extract_candidate_memories.py
      detect_contradictions.py
      retrieve_memories.py
      answer_with_evidence.py
      plan_memory_retrieval.py
      fallback_retrieve.py
      resolve_temporal_refs.py
      attach_numeric_scope.py
      consolidate_memories.py
      forget_or_archive_memory.py
      evaluate_memory_usage.py
    prompts/
      extract_candidate_memories.md
      detect_contradictions.md
      plan_memory_retrieval.md
      answer_with_evidence.md
      resolve_temporal_refs.md
      attach_numeric_scope.md
      consolidate_memories.md
      evaluate_memory_usage.md
    tools/
      __init__.py
      keyword_search.py
      vector_search.py
      embeddings.py
      text_normalize.py
      scoring.py
    fixtures/
      simple_conversation.jsonl
      contradiction_conversation.jsonl
      procedural_memory.jsonl
      numeric_memory.jsonl
      temporal_memory.jsonl
      fallback_retrieval.jsonl
      policy_comparison.jsonl
  examples/
    basic_memory_run.py
    contradiction_demo.py
    procedural_memory_demo.py
    temporal_memory_demo.py
    numeric_memory_demo.py
    fallback_retrieval_demo.py
    fork_memory_policy.py
    memory_evaluation_demo.py
  tests/
    test_pack_loads.py
    test_object_types.py
    test_relation_types.py
    test_basic_memory_lifecycle.py
    test_procedural_memory.py
    test_contradiction_supersession.py
    test_retrieval_links_evidence.py
    test_answer_with_evidence.py
    test_retrieval_planning.py
    test_fallback_retrieval.py
    test_temporal_refs.py
    test_numeric_scope.py
    test_memory_consolidation.py
    test_forget_or_archive_memory.py
    test_evaluate_memory_usage.py
    test_fork_memory_policy.py
    test_no_live_network_in_tests.py
  docs/
    architecture.md
    activegraph_native_design.md
    memory_lifecycle.md
    object_model.md
    relation_model.md
    behavior_model.md
    prompt_model.md
    retrieval_model.md
    temporal_reasoning.md
    numeric_reasoning.md
    contradiction_handling.md
    forgetting_and_archival.md
    evaluation.md
    benchmark_plan.md
    roadmap.md
```

## Notes on Structure

- `activegraph_memory/` — the main Python package
- `activegraph_memory/behaviors/` — all behavior implementations (one file per behavior)
- `activegraph_memory/prompts/` — prompt templates (one `.md` file per LLM behavior)
- `activegraph_memory/tools/` — deterministic tools used by behaviors
- `activegraph_memory/fixtures/` — `.jsonl` fixture files for offline testing
- `examples/` — standalone runnable demos (not part of the installed package)
- `tests/` — pytest tests, all deterministic, no network, no live model calls
- `docs/` — human-readable documentation for the project

## Benchmark Harness (Phase 15 only — implement if core is stable)

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
