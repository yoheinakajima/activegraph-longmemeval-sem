"""Pull concrete failure examples for the paper's qualitative section.

Categories:
  A) single-session-assistant regressions: det-correct but flat-wrong (the
     statistically significant LLM-extraction regression).
  B) flat evidence-present reasoning failures (turn_hit=1 & wrong) by type.
  C) flat retrieval-miss failures (turn_hit=0 & wrong).
  D) flat-correct / retain-wrong regressions (the assistant-retention audit;
     only shown when a ``--retain`` run is supplied).

Run: ../.pythonlibs/bin/python -m analysis.failures   (from longmemeval-harness/)

The run ids are overridable to inspect a later run against the originals.
``--retain`` is a first-class slot (the Track-1 assistant-retention run); pass
it to get the flat-correct/retain-wrong audit (section D):
  ../.pythonlibs/bin/python -m analysis.failures \
      --flat task18-flat-500 --retain task19-retain-500
The 'flat' slot is the run whose failures are categorized; 'det' is the
regression baseline compared against it; 'retain' (if its run dir exists) drives
the section-D regression audit.
"""
from __future__ import annotations

import argparse
import sqlite3
import textwrap
from pathlib import Path

DEFAULT_RUNS = {
    "det": "full-s-sonnet",
    "flat": "task18-flat-500",
    "agentic": "task18-agentic-500",
    "retain": "task19-retain-500",
}
RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def load(run_id: str) -> dict[str, dict]:
    con = sqlite3.connect(RUNS_DIR / run_id / "store.sqlite")
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM questions").fetchall()
    con.close()
    return {r["question_id"]: dict(r) for r in rows}


def show(q: dict, max_hyp: int = 320) -> None:
    print(f"  qid={q['question_id']}  type={q['question_type']}  "
          f"turn_hit={q['turn_hit']} turn_recall={q['turn_recall']} "
          f"n_gold_turns={q['n_gold_turns']}")
    print("  Q:    " + textwrap.shorten(q["question"].replace("\n", " "), 200))
    print("  GOLD: " + textwrap.shorten(str(q["gold_answer"]).replace("\n", " "), 200))
    hyp = (q["hypothesis"] or "").replace("\n", " ")
    print("  PRED: " + textwrap.shorten(hyp, max_hyp))
    print()


def main(run_ids: dict[str, str] | None = None) -> None:
    run_ids = run_ids or DEFAULT_RUNS
    print("# Runs: " + "  ".join(f"{k}={v}" for k, v in run_ids.items()) + "\n")
    det = load(run_ids["det"])
    flat = load(run_ids["flat"])
    agentic = load(run_ids["agentic"])
    retain_id = run_ids.get("retain")
    retain = (
        load(retain_id)
        if retain_id and (RUNS_DIR / retain_id / "store.sqlite").exists()
        else None
    )

    print("=" * 80)
    print("A) single-session-assistant REGRESSIONS (det correct, flat wrong)")
    print("=" * 80)
    regs = [q for q in flat
            if flat[q]["question_type"] == "single-session-assistant"
            and det[q]["judge_correct"] == 1 and flat[q]["judge_correct"] == 0]
    print(f"count = {len(regs)}\n")
    for q in regs:
        show(flat[q])

    print("=" * 80)
    print("B) flat EVIDENCE-PRESENT reasoning failures (turn_hit=1 & wrong), by type")
    print("=" * 80)
    for t in ["temporal-reasoning", "multi-session", "knowledge-update",
              "single-session-preference", "single-session-user"]:
        fails = [q for q in flat
                 if flat[q]["question_type"] == t
                 and flat[q]["is_abstention"] == 0
                 and flat[q]["turn_hit"] == 1 and flat[q]["judge_correct"] == 0]
        print(f"\n--- {t}: {len(fails)} evidence-present failures (showing up to 3) ---\n")
        for q in fails[:3]:
            show(flat[q])

    print("=" * 80)
    print("C) flat RETRIEVAL-MISS failures (turn_hit=0 & wrong), sample")
    print("=" * 80)
    miss = [q for q in flat
            if flat[q]["is_abstention"] == 0
            and flat[q]["turn_hit"] == 0 and flat[q]["judge_correct"] == 0]
    print(f"total retrieval-miss failures = {len(miss)} (showing 5)\n")
    for q in miss[:5]:
        show(flat[q])

    if retain is not None:
        print("=" * 80)
        print("D) flat-correct / retain-wrong REGRESSIONS "
              "(assistant-retention audit)")
        print("=" * 80)
        common = [q for q in flat if q in retain]
        regs = [q for q in common
                if flat[q]["judge_correct"] == 1 and retain[q]["judge_correct"] == 0]
        # Mirror gains for context: where retention flipped a wrong answer right.
        gains = [q for q in common
                 if flat[q]["judge_correct"] == 0 and retain[q]["judge_correct"] == 1]
        print(f"regressions (flat right -> retain wrong) = {len(regs)}; "
              f"gains (flat wrong -> retain right) = {len(gains)}; "
              f"net = {len(gains) - len(regs):+d}\n")
        for q in regs:
            show(retain[q])


def _parse_args() -> dict[str, str]:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--det", default=DEFAULT_RUNS["det"], help="regression baseline run id")
    p.add_argument("--flat", default=DEFAULT_RUNS["flat"],
                   help="run whose failures are categorized")
    p.add_argument("--agentic", default=DEFAULT_RUNS["agentic"], help="third run id")
    p.add_argument("--retain", default=DEFAULT_RUNS["retain"],
                   help="Track-1 assistant-retention run id (drives section D)")
    a = p.parse_args()
    return {"det": a.det, "flat": a.flat, "agentic": a.agentic, "retain": a.retain}


if __name__ == "__main__":
    main(_parse_args())
