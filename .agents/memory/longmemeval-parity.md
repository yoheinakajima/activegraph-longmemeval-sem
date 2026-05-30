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

**Result — semantic pack on cleaned `s` (n=500, run-id `full-s-sonnet`, May 2026):**
Overall QA accuracy **60.6%** (303/500), 0 errors/0 pack_errors. Reader
`claude-sonnet-4-5-20250929`, judge `gpt-4o-2024-11-20`, data sha256
`d6f21ea9d60a0d56…`. By type: single-session-assistant 96.4%, single-session-user
82.9%, knowledge-update 75.6%, temporal-reasoning 56.4%, single-session-preference
36.7%, multi-session 34.6%. Abstention 83.3% (25/30), answerable 59.1%.
Deterministic retrieval sidecar: turn_hit 50.2%, session_hit 77.4%. Mean reader
context ~7.5k tokens (NOT the paper's ~2.5k budget — different system). This is the
deferred semantic-memory experiment, NOT a repro of the paper's 85.6% substrate
number. Weakest on cross-session synthesis (multi-session, preference).

**Speed lever:** ingest is CPU-bound (deterministic, no LLM, ~21s/q); harness has a
`--concurrency N` flag (ProcessPoolExecutor, default 1) — N=3 on the 4-core box gave
~3x throughput with byte-identical per-question results (fresh Graph/Runtime/pack,
temp-0). Workspace sleeps when idle, so a long run only advances while awake.

**Long runs MUST be workflows, not nohup.** A `nohup ... &` background job in a
bash tool call gets reaped when that tool call's shell session ends (dies ~immediately
after the launching call returns, regardless of `nohup`). Symptom: run advances only
during the launching call's own `sleep`, then process count = 0. Fix: launch via
`configureWorkflow` (console outputType) — workflow processes are Replit-managed and
persist across tool calls. The harness resumes from `runs/<id>/store.sqlite` (table
`questions`, not `records`) so a killed run loses nothing on relaunch. Memory: the s
split is heavy (277MB JSON in parent + per-worker graphs); concurrency 2 is safe on
the 7.7GB box, 4 risked OOM alongside the auto-restarting full-s workflow.

**Replit AI proxy has NO embeddings endpoint** (`POST /embeddings` → INVALID_ENDPOINT;
see ai-integrations-openai "Unsupported Capabilities"). To use real
`text-embedding-3-small` (dim 1536) you need a real `OPENAI_API_KEY` (default base_url),
which also serves `gpt-4o-2024-08-06` (so judge-snapshot parity IS achievable with a
real key, unlike via the proxy). Pack stays key-agnostic; harness installs the provider.

**Embedding cache (reproducibility + speed):** `CachedEmbeddingProvider`
(`longmemeval_harness/embedding_cache.py`) wraps the pack provider with a process-safe
SQLite disk cache at `.cache/embeddings.sqlite`, keyed by blake2b(model+text). Store
vectors as float64 ('d') so a cached read is bit-identical to the first API value →
re-runs reproducible & free. LongMemEval-S reuses distractor sessions across questions,
so hit rate is high (one 50-q s-slice → ~22.8k unique vectors cover the rest).
WAL + busy_timeout for the ProcessPoolExecutor workers.

**Result — STRONG semantic pack (real embeddings + retrieval_limit=40 + vector on),
50-q s-slice (run-id `strong-embed-s`, May 2026):** Overall **68%** (34/50) vs the
deterministic-retrieval baseline 60.6% on full-s (same stratified slice comparable by
type) → +7.4 pts. Judge `gpt-4o-2024-08-06` (real key). By type: knowledge-update
100% (8), single-session-assistant 100% (6), single-session-user 71% (7), multi-session
69% (13), single-session-preference 33% (3), temporal-reasoning 38% (13). turn_aic_recall
0.815, session_aic_recall 0.98. 0 errors. temporal-reasoning is now the weak spot.
NOTE: this is the 50-q slice only; full-s strong run + Phase-2 LLM extraction not yet done.

**Phase 2 — LLM memory extraction (opt-in, cached):** the pack's
`extract_candidate_memories` behavior accepts an injected extractor via
`set_active_extractor` (default None → deterministic 1-memory-per-observation
heuristic, kept for offline/test determinism). Harness installs a cached
gpt-4o-mini (temp 0, JSON) extractor behind `--extraction llm` (+ real
OPENAI_API_KEY); manifest records requested-vs-resolved so a silent
no-key fallback to deterministic is never mislabeled. **Durable lessons:**
(1) pre-warm the extraction cache concurrently over ALL of a question's turns
*before* run_until_idle — the per-observation behavior calls run sequentially,
so cold per-call latency otherwise dominates; (2) NEVER cache an LLM failure as
an empty result — distinguish None (transient, skip write, retry w/ backoff)
from [] (genuine "nothing durable"), or a rate-limit blip poisons the cache
permanently; (3) clamp extracted confidence to [0,1] before building pack
objects (pydantic schema rejects out-of-range). **Result (50-q s-slice,
May 2026):** overall **88%** vs the 68% strong-deterministic baseline (+20 pts),
0 errors. multi-session 1.0, temporal-reasoning 0.77 (was 0.38 — biggest gain),
single-session-preference still weakest (0.67). Cost: extraction is the slow
part on a cold cache (~4 min ingest/q for ~485 turns); warm cache makes re-runs
fast+free. Full-s Phase-2 run is a separate user-confirmed step.

**Full-500 LLM baselines (run-ids `task18-flat-500`, `task18-agentic-500`, May
2026):** the first real product-config numbers at scale — LLM extraction, sonnet
reader, gpt-4o judge, NO rerank/HyDE, 0 errors each. **flat+LLM = 0.834**,
**agentic+LLM = 0.840** vs the deterministic-extraction full-s baseline 0.606
(`full-s-sonnet`). Per type (n; det → flat → agentic): knowledge-update (78)
.756→.846→.808; multi-session (133) .346→.827→.827; single-session-assistant (56)
.964→.750→.750; single-session-preference (30) .367→.867→.933; single-session-user
(70) .829→.943→.943; temporal-reasoning (133) .564→.805→.835. Retrieval sidecar
(det→flat→agentic): turn_recall .608→.940→.929, turn_hit .502→.906→.887,
session_hit .774→.983→.979. Reader tokens 4.23M→4.53M→4.32M.
**Three durable verdicts:**
(a) **LLM extraction is the dominant lever** — +0.228 over deterministic at scale
(NOT a slice artifact; the 0.94 slice was optimistic but the direction holds).
(b) **At 500, flat ≈ agentic** (0.834 vs 0.840 = +3 questions, well inside binomial
noise sd≈0.017). The 50-q claim "flat 0.94 > agentic 0.90" does NOT replicate — the
ordering is a wash at scale. Agentic *looks* precision-consistent (no precision
metric is reported, but it gets equal accuracy from −4.7% reader tokens and slightly
lower recall), with type-local gains (temporal +.030, preference +.066) offset by
knowledge-update −.038. Not worth flipping the default for +3 noise.
(c) **The bottleneck has flipped from recall to reader/precision.** Deterministic was
recall-limited (turn_recall .61 ≈ accuracy .61). LLM extraction lifts turn_recall to
.94 and turn_hit to .906, so recall is no longer binding; yet accuracy is only .834 —
a ~7-pt gap where *all* gold turns are retrieved but the reader still answers wrong,
plus ~9 pts of genuine turn misses. The next lever is reader synthesis on
evidence-present failures + the hard types (single-session-assistant, temporal,
multi-session), not retrieval breadth. **Notable inversion:** single-session-assistant
was the BEST type for deterministic (.964) and the WORST under LLM (.750) — LLM
extraction regressed assistant-turn questions; flag for the extraction-quality track.

**Phase-2 weak-type tuning (50-q s-slice, May 2026):** targeted the two weakest
types (temporal-reasoning, single-session-preference) via PACK/adapter only — the
reader prompt is a deliberately frozen controlled constant (substrate↔pack parity),
so it is OFF-LIMITS. **Durable lessons:** (1) the temporal misses were NOT retrieval
(turn_hit=1) — the frozen reader simply restates a salient duration ("for six weeks")
instead of subtracting; surfacing absolute dates next to the message lets it compute.
(2) the high-value lever was resolving ongoing-duration phrases ("for N weeks/months
now", "for about three months") to a START date (anchor − N) and rendering it as
"<phrase> = since <date>", so questions of the form "how long had I been doing X when
event Y" become start→event subtraction. (3) GOTCHA: adding a new
`resolution_method` value silently fails unless it is added to the `TemporalRef`
Literal in types.py — the behavior throws ValidationError and the ref never surfaces
(symptom: resolution works in isolation but "= since" count is 0 in assembled
context). **Result:** overall 0.88→0.94, temporal-reasoning 0.769→0.923 (12/13;
guitar→"four weeks", bird→"two months" both flipped), knowledge-update 0.875→1.0,
ALL strong types unchanged (multi-session/ssa 1.0, ssu 0.857). single-session-preference
stayed 0.667 (n=3): the 1 failure is a deep retrieval recall miss (turn_hit=0, gold
preference turn never surfaced among 21 retrieved sessions) — not safely fixable from
the pack without risking the perfect strong types. Runs: baseline `phase2-llm-s`,
final `task7-v3-s`. (`task7-v2-s` was a void run — duration refs silently failed the
Literal validation, so it equaled v1/baseline on temporal.)
