"""Paired significance + diagnostic analysis for the full-500 LLM baselines.

Pure-stdlib (no numpy/scipy). Loads the run stores keyed by question_id and
computes:
  - overall + per-type accuracy with Wilson 95% CIs
  - paired McNemar (exact two-sided binomial + continuity-corrected chi-square)
    for the meaningful run pairs
  - recall-conditioned accuracy: P(correct | turn_hit=1) vs P(correct | turn_hit=0)
    and the resulting error decomposition (retrieval-miss vs reasoning-on-evidence)
  - turn-hit (retrieval recall) by question type
  - context-token distribution per run

Run: ../.pythonlibs/bin/python -m analysis.significance   (from longmemeval-harness/)

The run ids are overridable so the same A/B machinery can compare any later
runs against the originals. There are four named slots; ``--retain`` is a
first-class slot (the Track-1 assistant-retention run) alongside the original
``--det/--flat/--agentic``:
  ../.pythonlibs/bin/python -m analysis.significance \
      --det full-s-sonnet --flat task18-flat-500 \
      --agentic task18-agentic-500 --retain task19-retain-500
A slot is included only if its run directory exists, so older invocations that
omit ``--retain`` (or run in an env without that run) still work unchanged.
"""
from __future__ import annotations

import argparse
import math
import sqlite3
from pathlib import Path

# Default quartet. Each is a named slot; override any via CLI. ``det/flat/agentic``
# are the Task #18 LLM baselines; ``retain`` is the Track-1 assistant-retention run.
DEFAULT_RUNS = {
    "det": "full-s-sonnet",            # deterministic extraction baseline
    "flat": "task18-flat-500",         # LLM extraction, flat retrieval
    "agentic": "task18-agentic-500",   # LLM extraction, agentic retrieval
    "retain": "task19-retain-500",     # LLM extraction, flat, assistant retention ON
}
# Fixed display order; only slots whose run dir exists are shown.
SLOT_ORDER = ["det", "flat", "agentic", "retain"]
RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def load(run_id: str) -> dict[str, dict]:
    con = sqlite3.connect(RUNS_DIR / run_id / "store.sqlite")
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT question_id, question_type, is_abstention, status, judge_correct, "
        "turn_hit, turn_recall, session_hit, n_gold_turns, context_tokens, "
        "reader_total_tokens, hypothesis, gold_answer, question, assembled_context "
        "FROM questions"
    ).fetchall()
    con.close()
    return {r["question_id"]: dict(r) for r in rows}


# ---- stats helpers (stdlib only) -------------------------------------------

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (center - half, center + half)


def binom_two_sided_p(b: int, c: int) -> float:
    """Exact two-sided McNemar via binomial on discordant pairs (p=0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # two-sided exact: 2 * P(X <= k), capped at 1
    cdf = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * cdf)


def mcnemar_chi2_cc(b: int, c: int) -> tuple[float, float]:
    """Continuity-corrected McNemar chi-square + p-value (df=1)."""
    n = b + c
    if n == 0:
        return (0.0, 1.0)
    chi2 = (abs(b - c) - 1) ** 2 / n
    # survival function of chi-square df=1 = erfc(sqrt(chi2/2))
    p = math.erfc(math.sqrt(chi2 / 2))
    return (chi2, p)


def accuracy(data: dict, ids: list[str]) -> tuple[int, int]:
    k = sum(1 for q in ids if data[q]["judge_correct"] == 1)
    return k, len(ids)


# ---- analysis --------------------------------------------------------------

def main(run_ids: dict[str, str] | None = None) -> None:
    run_ids = run_ids or DEFAULT_RUNS
    # Active slots: present in run_ids with a non-empty id and an existing store.
    slots = [
        s for s in SLOT_ORDER
        if run_ids.get(s) and (RUNS_DIR / run_ids[s] / "store.sqlite").exists()
    ]
    if not slots:
        requested = ", ".join(f"{s}={run_ids.get(s)!r}" for s in SLOT_ORDER) or "(none)"
        raise SystemExit(
            "No active slots: none of the requested runs have a store.sqlite under "
            f"{RUNS_DIR}. Requested: {requested}"
        )
    print("# Runs: " + "  ".join(f"{s}={run_ids[s]}" for s in slots) + "\n")
    runs = {s: load(run_ids[s]) for s in slots}
    # align on the intersection of question_ids present & done in all slots.
    common = set.intersection(
        *[{q for q, r in d.items() if r["status"] == "done"} for d in runs.values()]
    )
    ids = sorted(common)
    types = sorted({runs[slots[0]][q]["question_type"] for q in ids})

    print(f"# Aligned questions across all {len(slots)} runs: {len(ids)}\n")

    cw = 22  # per-slot column width

    # 1. Overall + per-type accuracy with Wilson CI
    print("## Accuracy with Wilson 95% CI")
    print(f"{'slice':<28}" + "".join(f"{s:>{cw}}" for s in slots))

    def acc_cell(d, sub):
        k, n = accuracy(d, sub)
        if n == 0:
            return "-"
        lo, hi = wilson_ci(k, n)
        return f"{k/n:.3f} [{lo:.3f},{hi:.3f}]"

    print(f"{'OVERALL ('+str(len(ids))+')':<28}"
          + "".join(f"{acc_cell(runs[s], ids):>{cw}}" for s in slots))
    for t in types:
        sub = [q for q in ids if runs[slots[0]][q]["question_type"] == t]
        label = f"{t} ({len(sub)})"
        print(f"{label:<28}" + "".join(f"{acc_cell(runs[s], sub):>{cw}}" for s in slots))
    print()

    # 2. McNemar pairwise (only meaningful, present pairs)
    def mcnemar(a: dict, b: dict, sub: list[str]):
        # b_count = a correct & b wrong; c_count = a wrong & b correct
        bb = sum(1 for q in sub if a[q]["judge_correct"] == 1 and b[q]["judge_correct"] == 0)
        cc = sum(1 for q in sub if a[q]["judge_correct"] == 0 and b[q]["judge_correct"] == 1)
        p_exact = binom_two_sided_p(bb, cc)
        chi2, p_chi = mcnemar_chi2_cc(bb, cc)
        return bb, cc, p_exact, chi2, p_chi

    candidate_pairs = [
        ("det", "flat"), ("det", "agentic"), ("det", "retain"),
        ("flat", "agentic"), ("flat", "retain"),
    ]
    pairs = [(a, b) for a, b in candidate_pairs if a in runs and b in runs]
    print("## McNemar paired tests (b = first-only correct, c = second-only correct)")
    for a, b in pairs:
        print(f"\n### {a} vs {b}")
        print(f"{'slice':<28}{'b':>5}{'c':>5}{'net':>6}{'p_exact':>12}{'chi2_cc':>10}{'p_chi2':>12}{'sig':>5}")
        for label, sub in ([("OVERALL", ids)]
                           + [(t, [q for q in ids if runs[slots[0]][q]['question_type'] == t]) for t in types]):
            bb, cc, p_exact, chi2, p_chi = mcnemar(runs[a], runs[b], sub)
            sig = "*" if p_exact < 0.05 else ""
            print(f"{label:<28}{bb:>5}{cc:>5}{cc-bb:>+6}{p_exact:>12.4f}{chi2:>10.2f}{p_chi:>12.4f}{sig:>5}")
    print()

    # 3. Recall-conditioned accuracy + error decomposition (answerable only:
    #    turn_hit is undefined for abstention questions / no gold turns)
    print("## Recall-conditioned accuracy (answerable only; turn_hit defined)")
    print(f"{'run':<10}{'n_ans':>7}{'acc':>8}{'hit_rate':>10}{'acc|hit=1':>11}{'acc|hit=0':>11}{'reason_err':>11}{'retr_err':>10}")
    for s in slots:
        d = runs[s]
        ans = [q for q in ids if d[q]["is_abstention"] == 0 and d[q]["turn_hit"] is not None]
        n = len(ans)
        correct = sum(1 for q in ans if d[q]["judge_correct"] == 1)
        hit1 = [q for q in ans if d[q]["turn_hit"] == 1]
        hit0 = [q for q in ans if d[q]["turn_hit"] == 0]
        acc_h1 = sum(1 for q in hit1 if d[q]["judge_correct"] == 1) / len(hit1) if hit1 else 0
        acc_h0 = sum(1 for q in hit0 if d[q]["judge_correct"] == 1) / len(hit0) if hit0 else 0
        reason_err = sum(1 for q in hit1 if d[q]["judge_correct"] == 0)  # evidence present, wrong
        retr_err = sum(1 for q in hit0 if d[q]["judge_correct"] == 0)    # evidence missing, wrong
        print(f"{s:<10}{n:>7}{correct/n:>8.3f}{len(hit1)/n:>10.3f}{acc_h1:>11.3f}{acc_h0:>11.3f}"
              f"{reason_err/n:>11.3f}{retr_err/n:>10.3f}")
    print("\n  reason_err = share of answerable that are evidence-present failures (turn_hit=1 & wrong)")
    print("  retr_err   = share of answerable that are retrieval-miss failures (turn_hit=0 & wrong)")
    print()

    # 3b. Turn-hit (retrieval recall) by question type — the Track-1 lever.
    print("## Turn-hit rate by question type (answerable only)")
    print(f"{'type':<28}{'n':>6}" + "".join(f"{s:>12}" for s in slots))
    for label, sub_types in [("OVERALL", types)] + [(t, [t]) for t in types]:
        rates = {}
        n_ref = 0
        for s in slots:
            d = runs[s]
            ans = [q for q in ids
                   if d[q]["question_type"] in sub_types
                   and d[q]["is_abstention"] == 0 and d[q]["turn_hit"] is not None]
            n_ref = len(ans)
            hits = sum(1 for q in ans if d[q]["turn_hit"] == 1)
            rates[s] = (hits / n_ref) if n_ref else 0.0
        print(f"{label:<28}{n_ref:>6}" + "".join(f"{rates[s]:>12.3f}" for s in slots))
    print()

    # 4. Context tokens
    print("## Context size (reader context_tokens, answerable+abstention)")
    print(f"{'run':<10}{'mean':>10}{'median':>10}{'p90':>10}")
    for s in slots:
        d = runs[s]
        vals = sorted(d[q]["context_tokens"] for q in ids if d[q]["context_tokens"] is not None)
        n = len(vals)
        if not n:
            continue
        mean = sum(vals) / n
        median = vals[n // 2]
        p90 = vals[int(n * 0.9)]
        print(f"{s:<10}{mean:>10.0f}{median:>10.0f}{p90:>10.0f}")


def _parse_args() -> dict[str, str]:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--det", default=DEFAULT_RUNS["det"], help="run id for the 'det' slot")
    p.add_argument("--flat", default=DEFAULT_RUNS["flat"], help="run id for the 'flat' slot")
    p.add_argument("--agentic", default=DEFAULT_RUNS["agentic"],
                   help="run id for the 'agentic' slot")
    p.add_argument("--retain", default=DEFAULT_RUNS["retain"],
                   help="run id for the 'retain' slot (Track-1 assistant retention)")
    a = p.parse_args()
    return {"det": a.det, "flat": a.flat, "agentic": a.agentic, "retain": a.retain}


if __name__ == "__main__":
    main(_parse_args())
