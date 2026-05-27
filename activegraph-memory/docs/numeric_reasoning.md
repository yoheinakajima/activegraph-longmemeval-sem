# numeric reasoning

`attach_numeric_scope` extracts numbers from observations and memories,
then writes a `quantity_claim` linked back via `has_quantity`.

## What gets extracted

For each match the extractor records:

- `raw_value` — the substring that matched (`"$250 million"`,
  `"35%"`, `"12,000"`).
- `value` — the normalized numeric value (`250000000.0`, `35.0`,
  `12000.0`).
- `unit` — `"USD"`, `"%"`, or empty when no unit is detected.
- `owner` — best-effort guess at who/what owns the quantity
  (`"fund"`, `"acme"`), inferred from neighboring tokens.
- `property` — best-effort guess at the property
  (`"reserves"`, `"revenue"`, `"users"`).
- `exactness` — `exact` when the source did not hedge,
  `approximate` when the source said "about", "around", "roughly".
- `can_sum_exactly` — `True` for `exact`, `False` otherwise. A
  downstream consumer can reject `sum()` over a mixed bag of
  approximate quantities.

## Why scope the quantity

A bare number in a `memory_observation` is useless to a retrieval
system. By promoting numbers to `quantity_claim` objects with
explicit owner/property, the answer behavior can:

- Bias retrieval toward `quantity_claim` when the question requires
  a numeric value.
- Refuse to mix `exact` and `approximate` quantities of the same
  property.
- Tell the user the source was hedged ("the source said *about* $250M").

## What the deterministic extractor does not do

- Currency conversion.
- Unit-arithmetic across mismatched units.
- Resolution of pronoun owners ("she said it was $250M" → who is
  "she"). The pack records the raw text and leaves resolution to a
  future LLM-shaped behavior or to a host application that knows the
  conversation context.
