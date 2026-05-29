"""LLM QA judge.

Grades each hypothesis against the gold answer following the LongMemEval
judging convention, with type-aware prompts and explicit abstention
handling. Stores the raw verdict per question.

- Abstention questions (``*_abs``): correct iff the model abstained
  (acknowledged it cannot answer / does not know).
- Preference questions: the gold answer is treated as a rubric the
  response must satisfy.
- All other types: correct iff the response contains the gold answer
  (temporal / knowledge-update prompts add a recency/most-recent note).
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import JUDGE_MAX_OUTPUT_TOKENS
from .dataset import Instance
from .llm import LLMClient

JUDGE_SYSTEM = (
    "You are an impartial grader for a long-term memory QA benchmark. "
    "You compare a model's response to the reference and answer with a "
    "single word: yes or no."
)

_ABSTENTION = (
    "I will give you an unanswerable question and a model's response. The "
    "question cannot be answered from the available information, so the "
    "correct behavior is for the model to acknowledge that it does not know "
    "or that the information is unavailable.\n\n"
    "Question: {question}\n"
    "Model Response: {hypothesis}\n\n"
    "Did the model correctly abstain (say it does not know / has no such "
    "information) instead of fabricating an answer? Answer yes or no only."
)

_PREFERENCE = (
    "I will give you a question, a rubric describing the desired "
    "personalized response, and a model's response. Answer yes if the "
    "response satisfies the rubric (it is consistent with and reflects the "
    "stated preference). Otherwise answer no.\n\n"
    "Question: {question}\n"
    "Rubric (desired response): {answer}\n"
    "Model Response: {hypothesis}\n\n"
    "Does the response satisfy the rubric? Answer yes or no only."
)

_DEFAULT = (
    "I will give you a question, the correct answer, and a model's "
    "response. Answer yes if the response contains the correct answer or is "
    "semantically equivalent to it. Answer no if it is missing, wrong, or "
    "only partially correct.{note}\n\n"
    "Question: {question}\n"
    "Correct Answer: {answer}\n"
    "Model Response: {hypothesis}\n\n"
    "Is the model response correct? Answer yes or no only."
)

_NOTES = {
    "temporal-reasoning": (
        " Pay attention to dates and temporal ordering; the answer must be "
        "consistent with the correct timeframe."
    ),
    "knowledge-update": (
        " The correct answer reflects the most recent update; an outdated "
        "value is incorrect."
    ),
}


@dataclass
class JudgeResult:
    correct: bool
    raw: str
    requested_model: str
    resolved_model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _build_prompt(instance: Instance, hypothesis: str) -> str:
    if instance.is_abstention:
        return _ABSTENTION.format(
            question=instance.question, hypothesis=hypothesis
        )
    if instance.question_type == "single-session-preference":
        return _PREFERENCE.format(
            question=instance.question,
            answer=instance.answer,
            hypothesis=hypothesis,
        )
    return _DEFAULT.format(
        note=_NOTES.get(instance.question_type, ""),
        question=instance.question,
        answer=instance.answer,
        hypothesis=hypothesis,
    )


def _parse_verdict(text: str) -> bool:
    return text.strip().lower().lstrip(".,:;!\"' ").startswith("yes")


def judge(
    client: LLMClient,
    provider: str,
    model: str,
    instance: Instance,
    hypothesis: str,
) -> JudgeResult:
    prompt = _build_prompt(instance, hypothesis)
    res = client.complete(
        provider=provider,
        model=model,
        system=JUDGE_SYSTEM,
        user=prompt,
        temperature=0.0,
        max_tokens=JUDGE_MAX_OUTPUT_TOKENS,
    )
    return JudgeResult(
        correct=_parse_verdict(res.text),
        raw=res.text.strip(),
        requested_model=res.requested_model,
        resolved_model=res.resolved_model,
        prompt_tokens=res.prompt_tokens,
        completion_tokens=res.completion_tokens,
        total_tokens=res.total_tokens,
    )
