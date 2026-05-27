---
version = "1.0.0"
---
You are extracting numeric facts from a memory or observation and giving
each one an explicit scope.

Numeric memory often fails because nearby unrelated numbers are
misattributed. The graph should encode what each number belongs to.

For each number you extract:
- raw_value: the verbatim mention, including unit symbols ("$20–25M")
- value: a normalized float when unambiguous
- unit: $, %, USD, count, etc.
- owner: the entity or thing the number describes
- property: the measured property (target, size, reserves, headcount, …)
- item_or_event: a finer-grained pointer when relevant (e.g., "Fund III")
- exactness: exact | approximate | lower_bound | upper_bound | range | unknown
- can_sum_exactly: true only when summing this with peers is meaningful

Rules:
- If owner is unclear, set owner to null. Do not guess.
- Represent ranges as ranges, not as midpoints unless the source is explicit.
- Do not attach the wrong entity to a number.
