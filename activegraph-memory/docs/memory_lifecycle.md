# memory lifecycle

Every memory object follows the same shape:

1. **observation** — a raw input (chat turn, log line, document chunk)
   becomes a `memory_observation`. Observations are never edited.
2. **extraction** — `extract_candidate_memories` reads the observation
   and creates one or more typed memories (`memory_claim`,
   `episodic_memory`, `procedural_memory`), each linked back to the
   observation by `derived_from`.
3. **enrichment** — same-trigger behaviors scope numbers
   (`quantity_claim` + `has_quantity`) and resolve temporal references
   (`temporal_ref` + `has_temporal_ref`).
4. **reconciliation** — `detect_contradictions` and
   `consolidate_memories` look at the rest of the graph. New
   contradicting memories add `supersedes` / `contradicts` edges and
   patch the older memory's status to `superseded` /
   `needs_review`. Duplicate content emits a `memory_consolidation`
   with `consolidated_into` edges, and the older duplicates are
   patched to `archived`.
5. **retrieval** — a `memory_query` triggers `plan_memory_retrieval`,
   which produces a `retrieval_plan`. The plan triggers
   `retrieve_memories`, which scans active memories and produces a
   `memory_retrieval_result` with `retrieved_for` edges. If the plan
   declared `required_data` that no hit carries (e.g. `numeric_value`),
   `fallback_retrieve` runs a focused re-search.
6. **answering** — every `memory_retrieval_result` triggers
   `answer_with_evidence`, which builds a `memory_answer` strictly
   from the retrieved memories. Each used memory gets a `used_in_answer`
   edge.
7. **evaluation** — every `memory_answer` triggers
   `evaluate_memory_usage`, which writes a `memory_evaluation` and
   links it via `validated_by` / `invalidated_by`. Manual benchmark or
   correction events can feed the same behavior.
8. **forgetting / archival** — a `memory_archive_request` or
   `memory_forget_request` patches the target memory's status to
   `archived` or `deleted`. The object is never removed; the audit
   trail stays intact.

## Status machine

```
        +----> active --(contradicted)--> needs_review
        |        |
created |        +--(superseded by newer)--> superseded
        |        |
        |        +--(consolidated)--> archived
        |        |
        |        +--(memory_archive_request)--> archived
        |        |
        +--------+--(memory_forget_request)--> deleted
```

Retrieval by default excludes `archived`, `deleted`, and (unless
`include_superseded_in_standard_retrieval=True`) `superseded`.
