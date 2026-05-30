"""LLM triage of evidence-present wrong answers (turn_hit=1 & judge wrong).

``turn_hit=1`` proves the gold turn's provenance reached the assembled context;
it does NOT prove the answer-bearing span survived extraction. This script asks
a cheap auditor model to classify each such failure into one of four labels:

  A = reasoning / evidence-use failure (facts present & faithful, reader wrong)
  B = compression / fidelity / span-loss (the exact value is absent)
  C = ordering / noise / conflict (answer present but buried among distractors)
  D = unclear / possible judge false-negative

It also computes a deterministic gold-term coverage cross-check (fraction of
gold-answer content words present in the context) as a sanity signal for B.

This makes LIVE OpenAI calls (auditor model, OPENAI_API_KEY) so it is the only
non-free step. Results are written to a COMMITTED labels file
``analysis/data/hit1_triage_<run>.json`` that ``analysis.cleanup_tables`` reads
without any network access. Re-running is deterministic (temp 0) but not free.

Run: ../.pythonlibs/bin/python -m analysis.hit1_triage   (from longmemeval-harness/)
     ../.pythonlibs/bin/python -m analysis.hit1_triage --runs task18-flat-500 task19-retain-500
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"
DATA_DIR = Path(__file__).resolve().parent / "data"
MODEL = "gpt-4o-mini"

_STOP = set(
    "the a an and or of to in on for with at by from as is are was were be been "
    "this that these those it its their his her your you i we they he she my our "
    "what when where which who how why do does did had has have will would should "
    "could can about into over under more most than then them me us also if not no "
    "yes any some all each per via using used use".split()
)

RUBRIC = """You audit why a long-term-memory QA system gave a WRONG answer even though a memory
derived from the gold turn was retrieved (turn_hit=1 proves provenance coverage, NOT that the
answer text survived extraction). Classify the failure into EXACTLY ONE label:

A = reasoning/evidence-use failure: the specific facts needed are PRESENT and faithful in the
    context, but the reader computed/aggregated/selected/grounded wrong (e.g. temporal
    arithmetic error, cross-session miscount/sum, picked a stale value though the update is
    present, gave a generic answer though the preference is present).
B = compression/fidelity/span-loss: the specific value/span needed to answer is ABSENT from the
    context. A memory about the topic is present, but extraction paraphrased/compressed away the
    exact fact, so the reader literally cannot read off the answer. (For derived answers like
    temporal math, the SOURCE facts being absent also counts as B; if the source facts ARE
    present and only the arithmetic is wrong, that is A.)
C = ordering/noise/conflict: the answer IS present but buried among many distractors or
    conflicting entries, and the reader latched onto a wrong but plausible nearby item.
D = unclear / possible judge false-negative: cannot tell, or the model response looks arguably
    correct or the gold is ambiguous.

Return ONLY compact JSON: {"label":"A|B|C|D","reason":"<=20 words"}"""


def _content_tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower())
            if len(t) > 2 and t not in _STOP}


def gold_coverage(gold: str, ctx: str) -> float:
    g = _content_tokens(gold)
    if not g:
        return 1.0
    return len(g & _content_tokens(ctx)) / len(g)


def load_hit1_wrong(run_id: str) -> list[dict]:
    """Deterministically rebuild the evidence-present wrong-answer items from the
    run store (turn_hit=1, answerable, judge wrong)."""
    con = sqlite3.connect(RUNS_DIR / run_id / "store.sqlite")
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT question_id, question_type, question, gold_answer, hypothesis, "
        "assembled_context FROM questions "
        "WHERE is_abstention=0 AND turn_hit=1 AND judge_correct=0 AND status='done'"
    ).fetchall()
    con.close()
    return [
        {
            "qid": r["question_id"],
            "type": r["question_type"],
            "question": r["question"],
            "gold": r["gold_answer"],
            "hypothesis": r["hypothesis"],
            "context": r["assembled_context"] or "",
        }
        for r in rows
    ]


def classify(client, item: dict) -> tuple[str, str]:
    ctx = (item["context"] or "")[:80000]
    user = (f'QUESTION_TYPE: {item["type"]}\nQUESTION: {item["question"]}\n'
            f'GOLD_ANSWER: {item["gold"]}\nMODEL_ANSWER(wrong): {item["hypothesis"]}\n\n'
            f'RETRIEVED_CONTEXT:\n{ctx}')
    try:
        r = client.chat.completions.create(
            model=MODEL, temperature=0, max_tokens=120,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": RUBRIC},
                      {"role": "user", "content": user}])
        out = json.loads(r.choices[0].message.content)
        lab = out.get("label", "D").strip().upper()[:1]
        return (lab if lab in "ABCD" else "D"), out.get("reason", "")
    except Exception as exc:  # noqa: BLE001 - record, do not crash the batch
        return "D", f"ERR:{exc}"


def triage_run(run_id: str, workers: int = 8) -> list[dict]:
    from openai import OpenAI

    client = OpenAI()  # real OPENAI_API_KEY, default base_url
    items = load_hit1_wrong(run_id)
    for it in items:
        it["cov"] = round(gold_coverage(it["gold"], it["context"]), 3)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        labs = list(ex.map(lambda it: classify(client, it), items))
    for it, (lab, reason) in zip(items, labs):
        it["label"], it["reason"] = lab, reason
    out = [{k: it[k] for k in ("qid", "type", "cov", "label", "reason",
                               "gold", "hypothesis")} for it in items]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"hit1_triage_{run_id}.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    cnt = Counter(it["label"] for it in out)
    low = sum(1 for it in out if it["cov"] < 0.5)
    print(f"=== {run_id}: n={len(out)} hit=1 wrong  -> {path.name} ===")
    for lab in "ABCD":
        print(f"   {lab}: {cnt.get(lab, 0)}")
    print(f"   [coverage cross-check] gold-term coverage <50%: {low}/{len(out)}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", nargs="+",
                   default=["task18-flat-500", "task19-retain-500"],
                   help="run ids to triage")
    p.add_argument("--workers", type=int, default=8)
    a = p.parse_args()
    for run_id in a.runs:
        triage_run(run_id, a.workers)


if __name__ == "__main__":
    main()
