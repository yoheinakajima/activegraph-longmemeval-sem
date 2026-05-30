"""Pull concrete failure examples for the paper's qualitative section.

Categories:
  A) single-session-assistant regressions: det-correct but flat-wrong (the
     statistically significant LLM-extraction regression).
  B) flat evidence-present reasoning failures (turn_hit=1 & wrong) by type.
  C) flat retrieval-miss failures (turn_hit=0 & wrong).

Run: ../.pythonlibs/bin/python -m analysis.failures   (from longmemeval-harness/)
"""
from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path

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


def main() -> None:
    det = load("full-s-sonnet")
    flat = load("task18-flat-500")
    agentic = load("task18-agentic-500")

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


if __name__ == "__main__":
    main()
