"""Static configuration: paths, dataset release, tiers, default models."""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------- paths
HARNESS_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = HARNESS_ROOT / "data"
RUNS_DIR = HARNESS_ROOT / "runs"

# ---------------------------------------------------------------- dataset
# LongMemEval cleaned release on HuggingFace (no GitHub / no vendoring).
HF_BASE = (
    "https://huggingface.co/datasets/"
    "xiaowu0162/longmemeval-cleaned/resolve/main"
)
SPLITS = {
    "oracle": "longmemeval_oracle.json",      # dev split (evidence-only haystack)
    "s": "longmemeval_s_cleaned.json",        # real benchmark (~500 sessions/q)
}

# ---------------------------------------------------------------- tiers
TIER_SIZES = {"smoke": 10, "small": 50, "full": 500}
SAMPLE_SEED = 42

# The six LongMemEval question types. ``*_abs`` question ids are the
# abstention variants of these types (no gold evidence; correct == abstain).
QUESTION_TYPES = [
    "single-session-user",
    "single-session-assistant",
    "single-session-preference",
    "temporal-reasoning",
    "knowledge-update",
    "multi-session",
]

# ---------------------------------------------------------------- models
# Aligned with the ActiveGraph LongMemEval-S paper harness
# (yoheinakajima/activegraph-longmemeval, release v0.1-paper-longmemeval-s)
# for cross-comparability, via Replit-managed AI integrations:
#   Reader  — claude-sonnet-4-5, temperature 0, tool-free  (paper value)
#   Judge   — gpt-4o, temperature 0                         (LongMemEval convention)
# Parity caveat: the paper pinned judge snapshot gpt-4o-2024-08-06, which is
# NOT exposed by the Replit proxy; "gpt-4o" here resolves to gpt-4o-2024-11-20
# (recorded as requested-vs-resolved in every manifest). Both run at temp 0;
# the paper notes judge-snapshot contribution is ~+/-1 pt.
DEFAULT_READER_PROVIDER = "anthropic"

# Named reader presets so swapping to a stronger model is a one-flag change
# (`--reader opus`). All are Anthropic; resolved dated snapshots are recorded
# per run in the manifest. Verified available on the Replit proxy May 2026.
READER_PRESETS = {
    "sonnet": "claude-sonnet-4-5",  # paper-aligned default -> claude-sonnet-4-5-20250929
    "opus": "claude-opus-4-5",      # stronger -> claude-opus-4-5-20251101
}
DEFAULT_READER_PRESET = "sonnet"
DEFAULT_READER_MODEL = READER_PRESETS[DEFAULT_READER_PRESET]

DEFAULT_JUDGE_PROVIDER = "openai"
DEFAULT_JUDGE_MODEL = "gpt-4o"

# Reader context budget (tiktoken estimate). Above this we truncate oldest
# messages and flag the question as truncated.
MAX_CONTEXT_TOKENS = 110_000
READER_MAX_OUTPUT_TOKENS = 1024  # paper reader max_tokens
JUDGE_MAX_OUTPUT_TOKENS = 16
