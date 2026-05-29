"""LLM reader.

A tool-free, temperature-0 reader that answers the question using ONLY
the pack's assembled evidence bundle. Captures the resolved model id,
token counts (exact from the API plus a tiktoken context estimate), and
a truncation flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import MAX_CONTEXT_TOKENS, READER_MAX_OUTPUT_TOKENS
from .adapter import EvidenceBundle
from .dataset import Instance
from .llm import LLMClient

READER_SYSTEM = (
    "You are a careful personal-memory assistant. Answer the user's "
    "question using ONLY the evidence provided (remembered facts and past "
    "messages). Do not use outside knowledge and do not guess. If the "
    "evidence does not contain enough information to answer, reply exactly: "
    "I don't know. Answer directly and concisely."
)

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
    qdate = instance.question_date or "unknown"
    return (
        f"Current date: {qdate}\n\n"
        f"{context}\n\n"
        f"Question: {instance.question}\n"
        f"Answer:"
    )


def read(
    client: LLMClient,
    provider: str,
    model: str,
    instance: Instance,
    bundle: EvidenceBundle,
    max_tokens: int = READER_MAX_OUTPUT_TOKENS,
) -> ReaderResult:
    context, truncated = _truncate_context(bundle.assembled_context)
    user = build_user_prompt(instance, context)
    context_tokens = _count_tokens(user)
    res = client.complete(
        provider=provider,
        model=model,
        system=READER_SYSTEM,
        user=user,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    return ReaderResult(
        hypothesis=res.text.strip(),
        requested_model=res.requested_model,
        resolved_model=res.resolved_model,
        prompt_tokens=res.prompt_tokens,
        completion_tokens=res.completion_tokens,
        total_tokens=res.total_tokens,
        context_tokens=context_tokens,
        truncated=truncated,
    )
