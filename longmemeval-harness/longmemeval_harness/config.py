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
# Same model families as the blog/result, via Replit-managed AI integrations.
# Reader: Anthropic Sonnet. Judge: GPT-4o (the LongMemEval judging convention).
DEFAULT_READER_PROVIDER = "anthropic"
DEFAULT_READER_MODEL = "claude-sonnet-4-6"
DEFAULT_JUDGE_PROVIDER = "openai"
DEFAULT_JUDGE_MODEL = "gpt-4o"

# Reader context budget (tiktoken estimate). Above this we truncate oldest
# messages and flag the question as truncated.
MAX_CONTEXT_TOKENS = 110_000
READER_MAX_OUTPUT_TOKENS = 512
JUDGE_MAX_OUTPUT_TOKENS = 16
