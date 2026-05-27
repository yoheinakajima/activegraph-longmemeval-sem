# benchmark plan

This document records what the benchmark harness should measure and
why, *not* the harness itself. The harness lands in a follow-up
release once the core pack is stable in user-facing apps.

## Targets

- **MemoryAgentBench** — multi-turn, long-horizon memory benchmark
  (Sept 2025). Tests update / consolidation / contradiction more
  than raw recall.
- **LongMemEval** — long-context recall benchmark
  (Sept 2024). Tests retrieval over multi-session histories.

Both ship as JSONL conversation transcripts; the adapter converts
each turn into a `memory_observation` and each test question into a
`memory_query`, then reads the emitted `memory_answer`.

## Ten metrics

1. **answer accuracy** — graded by the benchmark's own grader.
2. **retrieval recall@k** — fraction of gold memories present in
   `memory_retrieval_result.retrieved_object_ids`.
3. **retrieval precision@k** — fraction of returned memories that
   actually appear in the gold set.
4. **evidence faithfulness** — fraction of `memory_answer.used_memory_ids`
   that point to memories whose `content` is consistent with the
   answer text. Computed by a separate grader.
5. **supersession latency** — number of observations between a
   contradiction and the resulting `supersedes` edge.
6. **contradiction false-positive rate** — fraction of `contradicts`
   edges where the two memories are not actually contradictory by
   the gold judge.
7. **consolidation precision** — fraction of `memory_consolidation`
   markers where the merged memories were actually duplicates by
   the gold judge.
8. **temporal extraction rate** — fraction of gold temporal refs
   that the pack actually wrote as `temporal_ref` objects.
9. **numeric extraction rate** — same, for `quantity_claim`.
10. **policy-difference yield** — for the fork demo: how many more
    memories does the aggressive policy retain than the
    conservative one, and how does that translate into answer
    accuracy delta?

## Offline-first

The benchmark harness must not require live network in CI. The
adapters convert the public benchmark JSONL files into local
fixtures the test suite can run on a small slice (`pytest -k bench
-x`). A separate `make full-bench` target runs the full datasets
when the user has them on disk.
