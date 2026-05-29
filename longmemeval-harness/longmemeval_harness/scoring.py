"""Scoring.

Two metrics:

1. Retrieval sidecar (deterministic, no LLM) — answer-in-context. Maps
   retrieved memories back to source turn ids via provenance and checks
   whether the gold evidence turns (``has_answer``) and gold sessions
   (``answer_session_ids``) appear in the assembled context. Abstention
   questions have no gold evidence and are excluded from AIC aggregates
   per upstream convention.

2. Aggregate report — overall judged accuracy, per-question-type accuracy,
   turn/session AIC, and abstention accuracy, computed over stored records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .adapter import EvidenceBundle
from .dataset import Instance


@dataclass
class RetrievalScore:
    turn_recall: Optional[float]
    turn_hit: Optional[bool]
    session_recall: Optional[float]
    session_hit: Optional[bool]
    n_gold_turns: int
    n_gold_sessions: int


def score_retrieval(instance: Instance, bundle: EvidenceBundle) -> RetrievalScore:
    if instance.is_abstention:
        return RetrievalScore(None, None, None, None, 0, 0)

    gold_turns = {
        (t.session_id, t.turn_index)
        for s in instance.sessions
        for t in s.turns
        if t.has_answer
    }
    gold_sessions = set(instance.answer_session_ids)
    ctx_turns = {(sid, idx) for sid, idx in bundle.context_turn_ids}
    ctx_sessions = set(bundle.context_session_ids)

    if gold_turns:
        turn_recall = len(gold_turns & ctx_turns) / len(gold_turns)
        turn_hit = gold_turns <= ctx_turns
    else:
        turn_recall, turn_hit = None, None

    if gold_sessions:
        session_recall = len(gold_sessions & ctx_sessions) / len(gold_sessions)
        session_hit = gold_sessions <= ctx_sessions
    else:
        session_recall, session_hit = None, None

    return RetrievalScore(
        turn_recall=turn_recall,
        turn_hit=turn_hit,
        session_recall=session_recall,
        session_hit=session_hit,
        n_gold_turns=len(gold_turns),
        n_gold_sessions=len(gold_sessions),
    )


def _mean(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def aggregate(records: list[dict]) -> dict:
    """Build the metrics report from stored question records."""
    done = [r for r in records if r.get("status") == "done"]
    n = len(done)

    judged = [r for r in done if r.get("judge_correct") is not None]
    overall_acc = (
        sum(1 for r in judged if r["judge_correct"]) / len(judged)
        if judged
        else None
    )

    # per type
    by_type: dict[str, dict] = {}
    types = sorted({r["question_type"] for r in done})
    for qt in types:
        rows = [r for r in judged if r["question_type"] == qt]
        acc = (
            sum(1 for r in rows if r["judge_correct"]) / len(rows)
            if rows
            else None
        )
        by_type[qt] = {"n": len(rows), "accuracy": acc}

    # abstention vs answerable
    abst = [r for r in judged if r.get("is_abstention")]
    ans = [r for r in judged if not r.get("is_abstention")]
    abst_acc = (
        sum(1 for r in abst if r["judge_correct"]) / len(abst) if abst else None
    )
    ans_acc = (
        sum(1 for r in ans if r["judge_correct"]) / len(ans) if ans else None
    )

    # AIC over non-abstention with gold evidence
    aic_rows = [r for r in done if not r.get("is_abstention")]
    turn_recall = _mean([r.get("turn_recall") for r in aic_rows])
    session_recall = _mean([r.get("session_recall") for r in aic_rows])
    turn_hits = [r.get("turn_hit") for r in aic_rows if r.get("turn_hit") is not None]
    session_hits = [
        r.get("session_hit") for r in aic_rows if r.get("session_hit") is not None
    ]
    turn_hit_rate = (
        sum(1 for h in turn_hits if h) / len(turn_hits) if turn_hits else None
    )
    session_hit_rate = (
        sum(1 for h in session_hits if h) / len(session_hits)
        if session_hits
        else None
    )

    token_totals = {
        "reader_total_tokens": sum(r.get("reader_total_tokens") or 0 for r in done),
        "judge_total_tokens": sum(r.get("judge_total_tokens") or 0 for r in done),
    }

    return {
        "n_questions": n,
        "n_judged": len(judged),
        "overall_accuracy": overall_acc,
        "answerable_accuracy": ans_acc,
        "abstention_accuracy": abst_acc,
        "by_question_type": by_type,
        "turn_aic_recall": turn_recall,
        "turn_aic_hit_rate": turn_hit_rate,
        "session_aic_recall": session_recall,
        "session_aic_hit_rate": session_hit_rate,
        "n_errors": sum(1 for r in records if r.get("status") == "error"),
        "tokens": token_totals,
    }
