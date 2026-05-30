# Instrumentation TODO

The harness persists enough to reproduce every accuracy / retrieval table in the
blog, but several **cost** quantities are not yet written to the store or
manifest. They surface as `not recorded` in `analysis/cleanup_tables.py`
(table 5). This file lists what to add so future runs can report end-to-end cost
without re-deriving it.

## Currently recorded (per question, in `store.sqlite`)
- `reader_prompt_tokens`, `reader_completion_tokens` — read-time reader usage.
- `context_tokens` — size of the assembled context handed to the reader.
- `ingest_n_claims`, `ingest_n_obs` — FINAL (post-consolidation) memory counts.
- `turn_hit`, `judge_correct`, `is_abstention`, question metadata.

## Not recorded (write-side cost is invisible)
| Field | Why it matters | Where to capture |
| --- | --- | --- |
| extractor LLM call count (per question) | write-time call volume | extraction path / `extraction_cache` |
| extractor input / output tokens | dominant write-time token cost | extractor response usage |
| embedding API calls / tokens | vector-store write cost | embed step |
| pre-consolidation memory count | dedupe/update yield (only final `n_claims` is kept) | before consolidation |
| per-question write latency breakdown (extract vs embed vs consolidate) | find the write bottleneck | wrap each stage |
| object-store bytes per question | per-item storage cost (only aggregate `store.sqlite` size today) | object-store writer |

## Suggested shape
Add a `write_cost` JSON column on `questions` (or a sibling `write_cost` table
keyed by `question_id`) with:

```json
{
  "extractor_calls": 0,
  "extractor_prompt_tokens": 0,
  "extractor_completion_tokens": 0,
  "embedding_calls": 0,
  "embedding_tokens": 0,
  "memories_pre_consolidation": 0,
  "latency_ms": {"extract": 0, "embed": 0, "consolidate": 0},
  "object_store_bytes": 0
}
```

Keep it additive (nullable) so older runs and the existing tables stay valid;
`cleanup_tables.py` already renders missing fields as `not recorded`.
