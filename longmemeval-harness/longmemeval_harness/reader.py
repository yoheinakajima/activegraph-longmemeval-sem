"""LLM reader.

A tool-free, temperature-0 reader that answers the question using ONLY
the pack's assembled evidence bundle. Captures the resolved model id,
token counts (exact from the API plus a tiktoken context estimate), and
a truncation flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import (
    MAX_CONTEXT_TOKENS,
    READER_MAX_OUTPUT_TOKENS,
    SCAFFOLDED_MAX_OUTPUT_TOKENS,
)
from .adapter import EvidenceBundle
from .dataset import Instance
from .llm import LLMClient

# Verbatim from the ActiveGraph LongMemEval-S paper harness
# (yoheinakajima/activegraph-longmemeval @ v0.1-paper-longmemeval-s,
# src/activegraph_lme/cli.py) so the reader is a controlled constant across
# the paper's substrate run and this semantic-pack run. PARITY — DO NOT EDIT.
READER_SYSTEM = (
    "You are a helpful assistant answering a user's question about prior "
    "conversations between the user and an assistant. Use ONLY the provided "
    "conversation history. If the history does not contain enough information "
    "to answer, say you don't know. Be concise."
)

# Track 2 (NON-PARITY): a reasoning-scaffolded reader targeting the four
# evidence-present failure modes from the 500-q analysis (temporal arithmetic,
# cross-session aggregation, knowledge-update/supersession, preference
# grounding). It keeps the parity constraints (use ONLY the provided history,
# abstain when evidence is missing, final answer concise) but asks the model to
# reason explicitly first and emit the answer on a delimited ``ANSWER:`` line,
# which the reader parses back out as the (still concise) hypothesis.
_SCAFFOLD_STEPS = (
    "Work through these steps before answering:\n"
    "1. Identify the question type: exact recall, temporal / time-interval "
    "arithmetic, aggregation or counting across sessions, knowledge update (a "
    "fact that changed over time), preference grounding, or other.\n"
    "2. List the specific evidence lines from the history that bear on the "
    "question, with their dates. Quote exact values (numbers, names, dates, "
    "moves, list items).\n"
    "3. Reason explicitly:\n"
    "   - Temporal: compute the date difference / interval step by step using "
    "the dated evidence and today's date.\n"
    "   - Aggregation: enumerate every qualifying item across ALL sessions, then "
    "count or combine them.\n"
    "   - Knowledge update / supersession: when facts conflict, prefer the MOST "
    "RECENT one by date and report the current state.\n"
    "   - Preference: ground the answer in the user's stated or revealed "
    "preferences and prior behavior.\n"
    "4. If the history lacks the information needed, say you don't know."
)

_SCAFFOLD_TAIL = (
    "\n\nAfter your reasoning, output the final answer on its own line as:\n"
    "ANSWER: <concise answer>\n"
    "The text after ANSWER: must be concise and directly answer the question "
    "(or state that you don't know)."
)

SCAFFOLDED_SYSTEM = (
    "You are a careful assistant answering a user's question about prior "
    "conversations between the user and an assistant. Use ONLY the provided "
    "conversation history; never use outside knowledge.\n\n"
    + _SCAFFOLD_STEPS
    + _SCAFFOLD_TAIL
)

SCAFFOLDED_SELFCHECK_SYSTEM = (
    "You are a careful assistant answering a user's question about prior "
    "conversations between the user and an assistant. Use ONLY the provided "
    "conversation history; never use outside knowledge.\n\n"
    + _SCAFFOLD_STEPS
    + "\n5. Self-check: re-read each claim in your answer against the evidence "
    "lines above. If any claim is not directly supported, correct it or abstain."
    + _SCAFFOLD_TAIL
)

_ANSWER_MARKER = "ANSWER:"

_ENCODER = None


def _count_tokens(text: str) -> int:
    global _ENCODER
    if _ENCODER is None:
        import tiktoken

        try:
            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:  # noqa: BLE001
            _ENCODER = False
    if _ENCODER is False:
        return len(text) // 4
    return len(_ENCODER.encode(text))


@dataclass
class ReaderResult:
    hypothesis: str
    requested_model: str
    resolved_model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    context_tokens: int
    truncated: bool


def _truncate_context(context: str) -> tuple[str, bool]:
    """Drop oldest 'Relevant past messages' lines until under budget."""
    if _count_tokens(context) <= MAX_CONTEXT_TOKENS:
        return context, False
    lines = context.split("\n")
    # Keep trimming from the message block (after the header) until it fits.
    truncated = True
    while lines and _count_tokens("\n".join(lines)) > MAX_CONTEXT_TOKENS:
        # remove from the middle-end (oldest messages sit lower in the block)
        del lines[len(lines) // 2]
    return "\n".join(lines), truncated


def build_user_prompt(instance: Instance, context: str) -> str:
    # Verbatim layout from the paper harness `format_user` (cli.py): the pack's
    # assembled evidence bundle is placed where the paper places conversation
    # history, keeping the prompt a controlled constant between the two runs.
    qdate = instance.question_date or "unknown"
    return (
        f"Conversation history:\n{context}\n\n"
        f"Today's date: {qdate}\n"
        f"Question: {instance.question}\n"
        f"Answer:"
    )


def build_scaffolded_user_prompt(instance: Instance, context: str) -> str:
    """Same evidence layout as parity, but asks for explicit reasoning followed
    by the delimited final answer (the system prompt carries the steps)."""
    qdate = instance.question_date or "unknown"
    return (
        f"Conversation history:\n{context}\n\n"
        f"Today's date: {qdate}\n"
        f"Question: {instance.question}\n\n"
        "Reason step by step using the steps above, then end with a single line "
        "'ANSWER: <concise answer>'."
    )


def _parse_scaffolded_answer(text: str) -> str:
    """Return the concise answer after the last ``ANSWER:`` marker; fall back to
    the full (stripped) text if the model did not emit the marker."""
    raw = (text or "").strip()
    idx = raw.upper().rfind(_ANSWER_MARKER)
    if idx == -1:
        return raw
    return raw[idx + len(_ANSWER_MARKER):].strip() or raw


def read(
    client: LLMClient,
    provider: str,
    model: str,
    instance: Instance,
    bundle: EvidenceBundle,
    reader_mode: str = "parity",
    max_tokens: Optional[int] = None,
) -> ReaderResult:
    context, truncated = _truncate_context(bundle.assembled_context)
    mode = reader_mode or "parity"

    if mode == "parity":
        system = READER_SYSTEM
        user = build_user_prompt(instance, context)
        out_tokens = max_tokens or READER_MAX_OUTPUT_TOKENS
    else:
        system = (
            SCAFFOLDED_SELFCHECK_SYSTEM
            if mode == "scaffolded_with_self_check"
            else SCAFFOLDED_SYSTEM
        )
        user = build_scaffolded_user_prompt(instance, context)
        out_tokens = max_tokens or SCAFFOLDED_MAX_OUTPUT_TOKENS

    context_tokens = _count_tokens(user)
    res = client.complete(
        provider=provider,
        model=model,
        system=system,
        user=user,
        temperature=0.0,
        max_tokens=out_tokens,
    )
    hypothesis = (
        res.text.strip()
        if mode == "parity"
        else _parse_scaffolded_answer(res.text)
    )
    return ReaderResult(
        hypothesis=hypothesis,
        requested_model=res.requested_model,
        resolved_model=res.resolved_model,
        prompt_tokens=res.prompt_tokens,
        completion_tokens=res.completion_tokens,
        total_tokens=res.total_tokens,
        context_tokens=context_tokens,
        truncated=truncated,
    )
