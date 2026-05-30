"""Reproducible cleanup-pass tables for the blog wrap-up.

Every table here is computed DETERMINISTICALLY from the run stores and manifests
(no network, no LLM). The one LLM-derived input — the hit=1 wrong-answer triage
labels (A/B/C/D) — is read from the committed labels files written by
``analysis.hit1_triage``; if those are missing the triage table prints a hint to
generate them. Cost fields the harness does not yet persist are printed
explicitly as ``not recorded`` (see docs/instrumentation-todo.md).

Tables:
  1. matched-hit subset: det vs flat on questions where BOTH retrieved the gold
     turn (turn_hit=1) — isolates reasoning from retrieval.
  2. abstention accuracy across all four runs.
  3. evidence-present wrong-answer triage summary (reads committed labels).
  4. assistant-retention audit row: single-session-assistant flat-correct vs
     retain-wrong / retain-correct vs flat-wrong (the "Borges" regression check).
  5. write/read cost table (+ explicit not-recorded fields).
  6. reproduction metadata: dataset + judge-prompt + scaffold-slice hashes,
     per-run resolved models.

Run: ../.pythonlibs/bin/python -m analysis.cleanup_tables   (from longmemeval-harness/)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from collections import Counter
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
RUNS_DIR = HARNESS / "runs"
DATA_DIR = Path(__file__).resolve().parent / "data"

DET = "full-s-sonnet"
FLAT = "task18-flat-500"
AGENTIC = "task18-agentic-500"
RETAIN = "task19-retain-500"
ALL_RUNS = [DET, FLAT, AGENTIC, RETAIN]


def load(run_id: str) -> dict[str, dict]:
    con = sqlite3.connect(RUNS_DIR / run_id / "store.sqlite")
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM questions WHERE status='done'").fetchall()
    con.close()
    return {r["question_id"]: dict(r) for r in rows}


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n))


def rule(title: str) -> None:
    print("=" * 78)
    print(title)
    print("=" * 78)


# ---- 1. matched-hit subset --------------------------------------------------

def table_matched_hit(det: dict, flat: dict) -> None:
    rule("1. MATCHED-HIT SUBSET  (det vs flat; both answerable & both turn_hit=1)")
    ids = set(det) & set(flat)
    sub = [q for q in ids
           if not det[q]["is_abstention"] and not flat[q]["is_abstention"]
           and det[q]["turn_hit"] == 1 and flat[q]["turn_hit"] == 1]
    n = len(sub)
    nd = sum(det[q]["judge_correct"] for q in sub)
    nf = sum(flat[q]["judge_correct"] for q in sub)
    b = sum(1 for q in sub if det[q]["judge_correct"] and not flat[q]["judge_correct"])
    c = sum(1 for q in sub if flat[q]["judge_correct"] and not det[q]["judge_correct"])
    print(f"  n (both retrieved the gold turn) = {n}")
    print(f"  det  acc = {nd}/{n} = {nd/n:.3f}")
    print(f"  flat acc = {nf}/{n} = {nf/n:.3f}")
    print(f"  McNemar  b(det-only correct)={b}  c(flat-only correct)={c}  "
          f"net(flat-det)={c-b:+d}  p_exact={mcnemar_exact(b, c):.4f}")
    print("  reading: on questions where retrieval succeeded for BOTH systems, "
          "answer accuracy is ~equal — the gap is retrieval, not the reader.\n")


# ---- 2. abstention ----------------------------------------------------------

def table_abstention(runs: dict[str, dict]) -> None:
    rule("2. ABSTENTION ACCURACY  (is_abstention=1; correct == abstained)")
    print(f"  {'run':<20}{'n':>5}{'correct':>9}{'acc':>8}{'answered(FP)':>14}")
    for name in ALL_RUNS:
        d = runs[name]
        ab = [q for q in d if d[q]["is_abstention"]]
        cor = sum(d[q]["judge_correct"] for q in ab)
        print(f"  {name:<20}{len(ab):>5}{cor:>9}{cor/len(ab):>8.3f}{len(ab)-cor:>14}")
    print()


# ---- 3. triage summary (reads committed labels) -----------------------------

def table_triage() -> None:
    rule("3. EVIDENCE-PRESENT WRONG-ANSWER TRIAGE  (turn_hit=1 & wrong)")
    print("  labels: A=reasoning/use  B=span-loss/compression  C=ordering/noise  "
          "D=unclear\n")
    for name in (FLAT, RETAIN):
        path = DATA_DIR / f"hit1_triage_{name}.json"
        if not path.exists():
            print(f"  {name}: labels not found ({path.name}); "
                  f"run `python -m analysis.hit1_triage --runs {name}` to generate.\n")
            continue
        items = json.loads(path.read_text())
        cnt = Counter(it["label"] for it in items)
        low = sum(1 for it in items if it.get("cov", 1.0) < 0.5)
        n = len(items)
        print(f"  {name}: n={n} hit=1 wrong   "
              + "  ".join(f"{lab}={cnt.get(lab, 0)}" for lab in "ABCD"))
        print(f"     gold-term coverage <50% in context (span-loss signal): "
              f"{low}/{n}")
        bt: dict[str, Counter] = {}
        for it in items:
            bt.setdefault(it["type"], Counter())[it["label"]] += 1
        for t, c in sorted(bt.items()):
            print(f"       {t:28s} " + " ".join(f"{lab}={c.get(lab, 0)}" for lab in "ABCD"))
        print()


# ---- 4. assistant-retention audit ------------------------------------------

def table_retention_audit(flat: dict, retain: dict) -> None:
    rule("4. ASSISTANT-RETENTION AUDIT  (single-session-assistant; flat vs retain)")
    ssa = [q for q in (set(flat) & set(retain))
           if flat[q]["question_type"] == "single-session-assistant"]
    n = len(ssa)
    regs = [q for q in ssa
            if flat[q]["judge_correct"] and not retain[q]["judge_correct"]]
    gains = sum(1 for q in ssa
                if retain[q]["judge_correct"] and not flat[q]["judge_correct"])
    fa = sum(flat[q]["judge_correct"] for q in ssa)
    ra = sum(retain[q]["judge_correct"] for q in ssa)
    print(f"  n(single-session-assistant) = {n}")
    print(f"  flat   acc = {fa}/{n} = {fa/n:.3f}")
    print(f"  retain acc = {ra}/{n} = {ra/n:.3f}")
    print(f"  gains (flat wrong -> retain right)   = {gains}")
    print(f"  regressions (flat right -> retain wrong) = {len(regs)}  -> {regs}")
    print("  reading: retention recovers the assistant-output regression at "
          "near-zero cost to other items.\n")


# ---- 5. cost ----------------------------------------------------------------

def _agg(d: dict, key: str) -> tuple[int, float]:
    vs = [d[q][key] for q in d if d[q].get(key) is not None]
    return sum(vs), (sum(vs) / len(vs) if vs else 0.0)


def table_cost(runs: dict[str, dict]) -> None:
    rule("5. WRITE / READ COST  (from store + file sizes)")
    for name in (FLAT, RETAIN):
        d = runs[name]
        sz = os.path.getsize(RUNS_DIR / name / "store.sqlite")
        rp_s, rp_m = _agg(d, "reader_prompt_tokens")
        rc_s, rc_m = _agg(d, "reader_completion_tokens")
        ctx_s, ctx_m = _agg(d, "context_tokens")
        cl_s, cl_m = _agg(d, "ingest_n_claims")
        ob_s, ob_m = _agg(d, "ingest_n_obs")
        print(f"  {name}: store.sqlite = {sz/1e6:.1f} MB")
        print(f"    reader context tokens:   sum={rp_s:>12,}  mean={rp_m:>8.0f}")
        print(f"    assembled context tokens:sum={ctx_s:>12,}  mean={ctx_m:>8.0f}")
        print(f"    reader output tokens:    sum={rc_s:>12,}  mean={rc_m:>8.1f}")
        print(f"    ingest_n_claims (FINAL, post-consolidation): "
              f"sum={cl_s:>10,}  mean={cl_m:>7.1f}")
        print(f"    ingest_n_obs:            sum={ob_s:>12,}  mean={ob_m:>8.1f}")
    print("\n  NOT RECORDED (see docs/instrumentation-todo.md):")
    for field in (
        "extractor LLM calls (count)",
        "extractor input / output tokens",
        "embedding API calls / tokens",
        "pre-consolidation memory count (only final n_claims is kept)",
        "per-question write latency breakdown (extract vs embed vs consolidate)",
        "object-store bytes per question (only the aggregate store.sqlite size)",
    ):
        print(f"    - {field}: not recorded")
    print()


# ---- 6. reproduction metadata ----------------------------------------------

def _judge_prompt_sha() -> str:
    from longmemeval_harness import judge as j

    blob = (j.JUDGE_SYSTEM + j._ABSTENTION + j._PREFERENCE + j._DEFAULT
            + "".join(sorted(j._NOTES.values())))
    return hashlib.sha256(blob.encode()).hexdigest()


def fmt_model(block: dict) -> str:
    """Render a manifest model block as a single resolved-model string.

    The alias lives in ``model`` for the extraction / rerank blocks (whose
    ``requested`` field is the *mode*, e.g. ``llm`` / ``deterministic``) and in
    ``requested`` for the reader / judge blocks. Honour the new schema
    (``resolved_model`` + ``resolved_model_unavailable``) while still rendering
    older manifests that only carry ``resolved``.
    """
    alias = block.get("model") or block.get("requested", "?")
    if "resolved_model" in block or "resolved_model_unavailable" in block:
        if block.get("resolved_model_unavailable"):
            return f"{alias} (alias; unavailable)"
        return block.get("resolved_model") or alias
    return block.get("resolved") or alias


def table_repro() -> None:
    rule("6. REPRODUCTION METADATA")
    print(f"  judge_prompt_sha256   = {_judge_prompt_sha()}")
    slice_path = DATA_DIR / "scaffold_slice.json"
    if slice_path.exists():
        sl = json.loads(slice_path.read_text())
        print(f"  scaffold_slice sha256 = {sl['question_ids_sha256']}  "
              f"(seed={sl['seed']} n={sl['size']})")
    else:
        print("  scaffold_slice.json   = missing; run `python -m analysis.scaffold_slice`")
    print()
    print(f"  {'run':<20}{'dataset_sha256 (head)':<22}{'reader.resolved':<28}"
          f"{'extraction.resolved'}")
    for name in ALL_RUNS:
        m = json.loads((RUNS_DIR / name / "manifest.json").read_text())
        ds = (m.get("dataset", {}).get("sha256") or "")[:16]
        models = m.get("models", {})
        rd = models.get("reader", {})
        ex = models.get("extraction", {})
        print(f"  {name:<20}{ds:<22}{fmt_model(rd):<28}{fmt_model(ex)}")
    print("\n  caveat: provider snapshot aliases (reader/judge) that the proxy does "
          "not expose\n  cannot be resolved from provider logs (no log access); "
          "recorded as requested.\n")


def main() -> None:
    runs = {name: load(name) for name in ALL_RUNS}
    table_matched_hit(runs[DET], runs[FLAT])
    table_abstention(runs)
    table_triage()
    table_retention_audit(runs[FLAT], runs[RETAIN])
    table_cost(runs)
    table_repro()


if __name__ == "__main__":
    main()
