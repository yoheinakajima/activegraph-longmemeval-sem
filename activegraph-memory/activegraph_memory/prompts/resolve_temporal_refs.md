---
version = "1.0.0"
---
You are extracting and resolving temporal references in a memory or
observation.

Rules:
- Extract explicit dates ("2026-05-26", "May 26"), explicit ranges,
  and relative phrases ("today", "yesterday", "last week", "after the
  meeting").
- Resolve explicit dates outright.
- Resolve relative phrases only when an anchor is clear (the observation's
  `occurred_at` or `observed_at` is the most common anchor).
- Preserve unresolved references — do not guess.
- Distinguish event time, observation time, storage time, and query time.
- Record which anchor was used so a reviewer can audit.

Output fields per reference:
- text: the verbatim mention
- resolved_at: ISO datetime or null
- anchor: the anchor used (date string) or null
- resolution_method: one of explicit_date, relative_to_observation,
  relative_to_event, relative_to_benchmark_now, unresolved
- confidence: 0.0–1.0
