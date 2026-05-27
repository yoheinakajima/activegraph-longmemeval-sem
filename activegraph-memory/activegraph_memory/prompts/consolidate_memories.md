---
version = "1.0.0"
---
You are deciding whether two or more memories should be consolidated.

Rules:
- Consolidate only near-duplicates that say the same thing about the same
  subject.
- Do not merge memories that differ in any material detail (different
  numbers, different owners, different dates, different actors).
- Preserve evidence — the consolidated memory must keep references to all
  source observations.
- Prefer leaving memories separate when in doubt.

Output fields:
- merge: true | false
- consolidated_content: the merged content (when merge is true)
- source_memory_ids: list of memories being merged
- reason: one-sentence justification
- confidence: 0.0–1.0
