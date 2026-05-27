# forgetting and archival

The pack supports two operator-issued request types:

- `memory_archive_request` — "stop returning this memory in normal
  retrieval but keep it on disk."
- `memory_forget_request` — "treat this memory as deleted everywhere."

Each request carries `memory_id` (required) and an optional `reason`
string for audit.

## What the behavior does

`archive_memory` patches the target memory's `status` to `"archived"`.
`forget_memory` patches the target memory's `status` to `"deleted"`.
Neither behavior removes the underlying object from the graph. The
object's full event history and provenance stay intact.

## Why not really delete

Two reasons:

1. **Replay safety.** The graph is event-sourced. Replaying the event
   log produces the current state. If a memory were physically
   removed, every downstream object that pointed to it (a
   `memory_retrieval_result` that returned it, a `memory_answer`
   that cited it, a `memory_evaluation` that judged that answer)
   would be orphaned. The audit trail would lie.
2. **Compliance.** A real forget request usually has a reason: the
   user asked for their data to be removed, or the operator decided
   the memory was wrong. Keeping the request object and the status
   transition lets you prove the action was taken without keeping
   the content visible.

If your host application needs hard deletion for compliance, run a
periodic compaction that physically removes objects with
`status="deleted"` plus their incoming `derived_from`,
`retrieved_for`, and `used_in_answer` edges. Keep the
`memory_forget_request` itself so the audit survives.

## Retrieval semantics

By default, `retrieve_memories` and `fallback_retrieve` exclude
`archived`, `deleted`, and (unless
`include_superseded_in_standard_retrieval=True`) `superseded` from
the candidate set.
