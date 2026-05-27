# temporal reasoning

`resolve_temporal_refs` extracts time references from the `content`
of memory observations and memories, then writes a `temporal_ref`
object linked back via `has_temporal_ref`.

## What the deterministic extractor finds

- Absolute ISO-shaped dates: `2026-05-26`.
- Month + day + year forms: `May 26 2026`, `26 May 2026`.
- Relative forms: `today`, `yesterday`, `last week`, `next quarter`.
- Quarter labels: `Q1 2026`, `Q3'25`.
- Year-only references: `in 2024`.

For absolute dates the `resolved_at` field is filled and
`resolution_method` is `explicit_date`. For relative references the
extractor records the raw `text`, leaves `resolved_at` empty, and
sets `resolution_method` to `relative_to_observation` so a downstream
consumer with access to a clock can resolve it later.

## Four times to distinguish

The pack tracks the four times an event-sourced memory system needs:

1. **event time** — when the thing happened (`occurred_at` on
   `episodic_memory`, or the `resolved_at` on a `temporal_ref`).
2. **observation time** — when the observation was captured
   (`observed_at` on `memory_observation`).
3. **storage time** — when the object was added to the graph
   (stamped by the runtime, not by the pack).
4. **query time** — when the query was asked (`memory_query`'s
   creation timestamp, again stamped by the runtime).

The deterministic implementation never calls a wall clock. If the
caller does not stamp `occurred_at` or `observed_at`, those fields
stay empty rather than the pack inventing a value.
