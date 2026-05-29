---
name: LongMemEval paper parity for the harness
description: What the ActiveGraph LongMemEval-S blog/paper actually tested vs. what longmemeval-harness tests, and the exact reader/judge/split settings to match.
---
The blog "Evidence Compilation Before Semantic Memory: ActiveGraph on
LongMemEval-S" (activegraph.ai) + repo `yoheinakajima/activegraph-longmemeval`
(paper release tag `v0.1-paper-longmemeval-s`) is the "first analysis".

**Biggest parity fact — different system under test.** The paper measured the
deterministic *substrate* (turn-node graph, NO LLM at ingest; retrieval via
`activegraph-det-embedding` = cosine over `text-embedding-3-small`, or
`-det-lexical` = IDF token overlap). Headline: 85.6% QA, 86.2% turn-AIC at
2,462 mean context tokens on cleaned `s` (n=500). The paper *explicitly defers*
the semantic-memory test ("That would be the real ActiveGraph semantic-memory
test. This run does not answer it."). `longmemeval-harness/` tests exactly that
deferred system — the `activegraph-memory` semantic pack. So our run is the
follow-up experiment, NOT a reproduction of 85.6%.

**Paper eval knobs to match for comparability:**
- Reader: requested alias `claude-sonnet-4-5`, temp 0, tool-free/web-free, `max_tokens=1024`.
- Judge: `gpt-4o-2024-08-06` (upstream short name `gpt-4o`), temp 0.
- Dense embeddings (their retrieval): `text-embedding-3-small`.
- Split for headline: cleaned `s`, n=500. Budget ~2.5k context tokens for the AG variants; full-context-s budget 180k.
- AIC: exclude the 30 abstention questions (upstream convention); significance via exact McNemar on per-question hit/miss vectors.

**Replit-proxy availability (checked May 2026):** `claude-sonnet-4-5` works
(resolves `claude-sonnet-4-5-20250929`). `gpt-4o-2024-08-06` is NOT exposed —
only `gpt-4o` (resolves `gpt-4o-2024-11-20`). So judge snapshot parity is
impossible on the proxy; document requested-vs-resolved in the manifest. Paper
says judge-snapshot contribution is ~±1 pt.

**Reader prompt parity (DONE):** the paper's shared template lives in
`src/activegraph_lme/cli.py` (`SYSTEM_PROMPT` + `format_user`), NOT in the
reader/ files (the reader just takes system+user strings). Our reader now uses
the byte-identical system prompt and `format_user` layout
("Conversation history:\n{ctx}\n\nToday's date: {date}\nQuestion: {q}\nAnswer:").

**Reader model switch:** `--reader {sonnet,opus}` preset (config `READER_PRESETS`):
sonnet=claude-sonnet-4-5 (default, paper-aligned), opus=claude-opus-4-5
(resolves claude-opus-4-5-20251101). `--reader-model <id>` overrides. Opus ids
available on proxy: claude-opus-4-1 and claude-opus-4-5 (claude-opus-4 is NOT).

**Remaining non-parity:** judge snapshot (gpt-4o-2024-08-06 unavailable; using
gpt-4o-2024-11-20); the pack uses its own keyword/BM25 retrieval (vector
disabled), not the paper's dense embeddings — but that retrieval IS the system
under test, not a knob.
