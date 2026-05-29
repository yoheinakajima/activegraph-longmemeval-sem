# longmemeval-harness

A self-contained, resumable benchmark harness that evaluates the
[`activegraph-memory`](../activegraph-memory) pack on the
[LongMemEval](https://github.com/xiaowu0162/LongMemEval) benchmark. It is
groundwork for a follow-up to the ActiveGraph *"Evidence Compilation Before
Semantic Memory"* result.

The pack is a **frozen, read-only dependency** — this harness imports only
its public surface (`Graph`, `Runtime`, `pack`, `MemorySettings`) and never
modifies it.

## What is under test

The semantic memory pipeline, end to end:

```
conversation turns ──▶ memory_observation (deterministic ingest, no LLM)
                          │
                          ▼
                   claims / episodic / procedural
                          │
                   memory_query ──▶ retrieval ──▶ assembled evidence bundle
                          │
                          ▼
                  LLM reader  ──▶ hypothesis answer
                          │
            ┌─────────────┴──────────────┐
            ▼                             ▼
  retrieval sidecar (no LLM)        LLM judge (GPT-4o)
  turn-AIC / session-AIC            QA accuracy
```

Ingestion is deterministic and calls no LLM (matching the blog's substrate
discipline). Only the **reader** and the **judge** use LLMs, via
Replit-managed AI integrations (no API keys required; usage is billed to
your Replit credits):

- **Reader** — Anthropic `claude-sonnet-4-5` (temperature 0, tool-free), matching the paper harness.
- **Judge** — OpenAI `gpt-4o` (the LongMemEval judging convention).

Both are configurable (see flags below).

### Parity with the ActiveGraph LongMemEval-S paper

The original result lives in
[`yoheinakajima/activegraph-longmemeval`](https://github.com/yoheinakajima/activegraph-longmemeval)
(release `v0.1-paper-longmemeval-s`) and its
[blog write-up](https://activegraph.ai/blog/evidence-compilation-before-semantic-memory-longmemeval).
**That paper measured the deterministic *substrate* ("evidence compilation
*before* semantic memory") — turn-node graphs with embedding/lexical retrieval
and no LLM at ingest. This harness measures the *semantic memory pack*, which
the paper explicitly names as the follow-up experiment it does not run.** So
this is the next experiment in that line, not a reproduction of the paper's
85.6% number.

To keep the two directly comparable, the controllable evaluation knobs are
aligned to the paper:

| knob          | paper (`v0.1-paper-longmemeval-s`) | here                          | parity |
|---------------|------------------------------------|-------------------------------|--------|
| reader        | `claude-sonnet-4-5`, temp 0, tool-free, max_tokens 1024 | same | ✅ |
| judge         | `gpt-4o-2024-08-06`, temp 0        | `gpt-4o` → `gpt-4o-2024-11-20` | ⚠️ snapshot unavailable on Replit proxy; both temp 0 (paper: ~±1 pt) |
| split (headline) | `s` (n=500)                     | `--split s --size full`       | ✅ |
| AIC convention | exclude 30 abstentions, McNemar  | same                          | ✅ |
| retrieval     | dense embeddings (`text-embedding-3-small`) over turn nodes | the **pack's own** retrieval (this is the system under test, not a knob) | n/a |
| reader prompt | shared template (in repo `cli.py`) | **byte-identical** system + user template | ✅ |

The manifest records every model **requested vs. resolved**, so all parity
gaps are auditable per run.

**Reader model switch.** The reader is selectable via a named preset so trying a
stronger model is a one-flag change:

- `--reader sonnet` (default) → `claude-sonnet-4-5` (paper-aligned)
- `--reader opus` → `claude-opus-4-5` (stronger)
- `--reader-model <id>` overrides with any explicit model id.

Everything else (prompt, temperature 0, tool-free, max_tokens, judge, metrics)
stays fixed, so a sonnet-vs-opus comparison isolates reader strength.

## Install

The harness depends on `activegraph` and the `activegraph-memory` pack,
which are already installed in this environment. The extra runtime deps
(`openai`, `anthropic`, `requests`, `tiktoken`) are installed too. To run in
a fresh environment:

```bash
pip install -e ../activegraph-memory
pip install openai anthropic requests tiktoken
```

## Data

Splits are pulled from the HuggingFace
[`xiaowu0162/longmemeval-cleaned`](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)
release into `data/` (never vendored via git):

- `oracle` — `longmemeval_oracle.json` (dev split; evidence-only haystack, small)
- `s` — `longmemeval_s_cleaned.json` (the real benchmark; ~500 sessions/question)

Download and print the file's SHA-256 without running anything:

```bash
python -m longmemeval_harness --download-only --split oracle
python -m longmemeval_harness --download-only --split s
```

(The orchestrator also downloads automatically on first run.)

## Run

All runs are a single command. Run from inside `longmemeval-harness/`:

```bash
# Smoke (~10 questions) on the oracle dev split
python -m longmemeval_harness --size smoke --split oracle

# Small (~50)
python -m longmemeval_harness --size small --split oracle

# Full (500) on the real benchmark split — long; resume-friendly
python -m longmemeval_harness --size full --split s
```

### Tiers

| size  | questions | use                                   |
|-------|-----------|---------------------------------------|
| smoke | ~10       | wiring check                          |
| small | ~50       | quick signal                          |
| full  | 500       | the whole benchmark                   |

Sampling is **deterministic** (seed 42) and **stratified** across all six
question types (and the abstention variants), so each tier is reproducible
and representative.

### Useful flags

| flag                  | meaning                                                     |
|-----------------------|-------------------------------------------------------------|
| `--split`             | `oracle` (dev) or `s` (benchmark)                           |
| `--size`              | `smoke` / `small` / `full`                                  |
| `--run-id`            | override the run id (default `<split>-<size>-seed<seed>`)   |
| `--seed`              | sampling seed (default 42)                                  |
| `--reader-provider`   | `anthropic` (default) or `openai`                           |
| `--reader`            | reader preset: `sonnet` (default, paper) or `opus` (stronger) |
| `--reader-model`      | explicit reader model id (overrides `--reader`)            |
| `--judge-provider`    | `openai` (default) or `anthropic`                           |
| `--judge-model`       | judge model id                                              |
| `--no-judge`          | skip the LLM judge (retrieval sidecar + reader only)       |
| `--limit N`           | cap sampled questions (debugging)                          |
| `--download-only`     | download the split, print its SHA-256, and exit            |

## Resume

Every question's result is committed to a SQLite store as it completes. The
**run id is stable** for a given `(split, size, seed)`, so if a run is
interrupted (Replit restart, timeout, crash) just **re-run the exact same
command** — it reads the completed question ids and skips them, picking up
where it left off. The full `s` run is long and is meant to be run and
resumed inside Replit this way.

## Outputs

Each run writes to `runs/<run_id>/`:

| file                | contents                                                                 |
|---------------------|--------------------------------------------------------------------------|
| `store.sqlite`      | the durable per-question record (all analyzable fields; resume source)   |
| `manifest.json`     | dataset SHA-256, sample seed/size, reader+judge models (requested & resolved), pack version, memory settings, wall-clock, status counts, metrics |
| `hypotheses.jsonl`  | one line per question: question, gold answer, hypothesis, judge verdict, AIC hits |
| `metrics.json`      | aggregate report (below)                                                  |

### Metrics

- **`overall_accuracy`** — LLM-judged QA accuracy over all sampled questions.
- **`answerable_accuracy` / `abstention_accuracy`** — split out; for
  abstention (`*_abs`) questions, "correct" means the model abstained.
- **`by_question_type`** — accuracy per question type.
- **`turn_aic_recall` / `turn_aic_hit_rate`** — deterministic
  answer-in-context: did the gold evidence turns (`has_answer`) reach the
  assembled context? (recall = fraction of gold turns present; hit = all
  present). Retrieved memories are mapped back to source turns via the
  pack's `derived_from` provenance.
- **`session_aic_recall` / `session_aic_hit_rate`** — same at the session
  level against `answer_session_ids`.

Abstention questions have no gold evidence and are excluded from AIC
aggregates per upstream convention.

The store keeps per-question correctness vectors, so publication-grade
statistics (McNemar, bootstrap CIs) can be computed later from
`store.sqlite` without re-running.

## Layout

```
longmemeval-harness/
├── README.md
├── pyproject.toml
├── data/                       # downloaded splits (gitignored)
├── runs/                       # per-run outputs (gitignored)
└── longmemeval_harness/
    ├── config.py               # paths, dataset release, tiers, default models
    ├── dataset.py              # download + SHA-256 + typed parse
    ├── sampler.py              # deterministic stratified sampling
    ├── adapter.py              # pack driver (ingest → query → evidence bundle)
    ├── llm.py                  # OpenAI/Anthropic clients over the AI proxy
    ├── reader.py               # tool-free temperature-0 reader
    ├── judge.py                # GPT-4o judge (type-aware + abstention)
    ├── scoring.py              # turn/session AIC + aggregate report
    ├── store.py                # resumable SQLite run store
    ├── manifest.py             # manifest / hypotheses / metrics writers
    ├── orchestrator.py         # ties it together; resume logic
    └── __main__.py             # CLI (python -m longmemeval_harness)
```

## Scope

In scope: the semantic pack pipeline only, on `oracle` and `s`, tiered and
resumable, with full data capture. Out of scope: any change to the pack;
other baselines (full-context, BM25, dense-RAG, session-level); the
`longmemeval_m` split; GitHub work (no submodules/forks/pushes); and
publication-grade statistics (the harness stores what's needed to compute
them later).
