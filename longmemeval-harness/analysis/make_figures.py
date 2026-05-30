"""Render the blog figures into ``analysis/figures/`` (committed).

All chart data is computed DETERMINISTICALLY from the run stores + the committed
triage labels (no network). Two schematic diagrams (architecture, proposed
hybrid retrieval) are drawn from static layout. Uses the matplotlib Agg backend
so it runs headless.

Run: ../.pythonlibs/bin/python -m analysis.make_figures   (from longmemeval-harness/)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HARNESS = Path(__file__).resolve().parent.parent
RUNS_DIR = HARNESS / "runs"
DATA_DIR = Path(__file__).resolve().parent / "data"
FIG_DIR = Path(__file__).resolve().parent / "figures"

DET, FLAT, AGENTIC, RETAIN = (
    "full-s-sonnet", "task18-flat-500", "task18-agentic-500", "task19-retain-500"
)
LABELS = {DET: "deterministic", FLAT: "flat", AGENTIC: "agentic", RETAIN: "retain"}
ORDER = [DET, FLAT, AGENTIC, RETAIN]
C = {DET: "#9aa0a6", FLAT: "#4285f4", AGENTIC: "#a142f4", RETAIN: "#0f9d58"}


def load(run_id: str) -> dict[str, dict]:
    con = sqlite3.connect(RUNS_DIR / run_id / "store.sqlite")
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM questions WHERE status='done'").fetchall()
    con.close()
    return {r["question_id"]: dict(r) for r in rows}


def _acc(d: dict) -> float:
    return sum(x["judge_correct"] for x in d.values()) / len(d)


def _save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / name
    fig.savefig(path, dpi=144, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote figures/{name}")


# ---- 1. accuracy ladder -----------------------------------------------------

def fig_accuracy_ladder(runs):
    accs = [_acc(runs[r]) for r in ORDER]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar([LABELS[r] for r in ORDER], accs, color=[C[r] for r in ORDER])
    for b, a in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, a + 0.01, f"{a:.3f}",
                ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("overall accuracy (judge_correct)")
    ax.set_title("LongMemEval-S accuracy by reader / memory mode (n=500)")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "01_accuracy_ladder.png")


# ---- 2. bottleneck flip -----------------------------------------------------

def fig_bottleneck_flip(runs):
    """For answerable questions, split outcomes into retrieval-miss vs
    reasoning-error vs correct — the gap is dominated by retrieval (recall),
    while answers on retrieved evidence are nearly always right."""
    fig, ax = plt.subplots(figsize=(8, 4.2))
    miss, reason_err, correct = [], [], []
    for r in ORDER:
        d = runs[r]
        ans = [q for q in d.values() if not q["is_abstention"]]
        n = len(ans)
        m = sum(1 for q in ans if q["turn_hit"] != 1)
        e = sum(1 for q in ans if q["turn_hit"] == 1 and not q["judge_correct"])
        c = sum(1 for q in ans if q["turn_hit"] == 1 and q["judge_correct"])
        miss.append(m / n); reason_err.append(e / n); correct.append(c / n)
    x = [LABELS[r] for r in ORDER]
    ax.bar(x, correct, color="#0f9d58", label="retrieved gold & correct")
    ax.bar(x, reason_err, bottom=correct, color="#f4b400",
           label="retrieved gold & wrong (reasoning/use)")
    ax.bar(x, miss, bottom=[c + e for c, e in zip(correct, reason_err)],
           color="#db4437", label="gold turn not retrieved (recall miss)")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("fraction of answerable questions")
    ax.set_title("Where answerable-question accuracy is lost (retrieval vs reasoning)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.32), ncol=1, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "02_bottleneck_flip.png")


# ---- 3. assistant retention by type ----------------------------------------

def fig_retention_by_type(runs):
    flat, ret = runs[FLAT], runs[RETAIN]
    types = sorted({q["question_type"] for q in flat.values()})
    fa, ra = [], []
    for t in types:
        fq = [q for q in flat.values() if q["question_type"] == t]
        rq = [q for q in ret.values() if q["question_type"] == t]
        fa.append(sum(x["judge_correct"] for x in fq) / len(fq))
        ra.append(sum(x["judge_correct"] for x in rq) / len(rq))
    import numpy as np

    y = np.arange(len(types))
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.barh(y - 0.2, fa, 0.4, color=C[FLAT], label="flat")
    ax.barh(y + 0.2, ra, 0.4, color=C[RETAIN], label="retain (assistant facts)")
    ax.set_yticks(y); ax.set_yticklabels([t.replace("single-session-", "ss-") for t in types])
    ax.set_xlim(0, 1.0); ax.set_xlabel("accuracy")
    ax.set_title("Assistant-fact retention: accuracy by question type")
    ax.legend(frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "03_assistant_retention_by_type.png")


# ---- 4. context cost --------------------------------------------------------

def fig_context_cost(runs):
    def mean_ctx(d):
        vs = [q["context_tokens"] for q in d.values() if q.get("context_tokens")]
        return sum(vs) / len(vs)

    pairs = [(FLAT, mean_ctx(runs[FLAT])), (RETAIN, mean_ctx(runs[RETAIN]))]
    fig, ax = plt.subplots(figsize=(5.5, 4))
    bars = ax.bar([LABELS[r] for r, _ in pairs], [v for _, v in pairs],
                  color=[C[r] for r, _ in pairs])
    for b, (_, v) in zip(bars, pairs):
        ax.text(b.get_x() + b.get_width() / 2, v + 80, f"{v:,.0f}",
                ha="center", va="bottom", fontweight="bold")
    ax.set_ylabel("mean assembled-context tokens / question")
    ax.set_title("Read-time context cost (flat vs retain)")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "04_context_cost.png")


# ---- 5. matched-hit subset --------------------------------------------------

def fig_matched_hit(runs):
    det, flat = runs[DET], runs[FLAT]
    ids = set(det) & set(flat)
    sub = [q for q in ids
           if not det[q]["is_abstention"] and not flat[q]["is_abstention"]
           and det[q]["turn_hit"] == 1 and flat[q]["turn_hit"] == 1]
    n = len(sub)
    nd = sum(det[q]["judge_correct"] for q in sub) / n
    nf = sum(flat[q]["judge_correct"] for q in sub) / n
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(["deterministic", "flat"], [nd, nf],
                  color=[C[DET], C[FLAT]])
    for b, a in zip(bars, [nd, nf]):
        ax.text(b.get_x() + b.get_width() / 2, a + 0.01, f"{a:.3f}",
                ha="center", va="bottom", fontweight="bold")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("accuracy")
    ax.set_title(f"Matched-hit subset (both retrieved gold, n={n})\n"
                 "reader quality is ~equal — gap is retrieval")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "05_matched_hit_subset.png")


# ---- 6. triage --------------------------------------------------------------

def fig_triage():
    import numpy as np

    runs = [FLAT, RETAIN]
    cats = list("ABCD")
    names = {"A": "A reasoning/use", "B": "B span-loss", "C": "C ordering/noise",
             "D": "D unclear"}
    colors = {"A": "#f4b400", "B": "#db4437", "C": "#4285f4", "D": "#9aa0a6"}
    data = {}
    for r in runs:
        path = DATA_DIR / f"hit1_triage_{r}.json"
        if not path.exists():
            print(f"  skip triage figure: {path.name} missing")
            return
        items = json.loads(path.read_text())
        data[r] = {c: sum(1 for it in items if it["label"] == c) for c in cats}
    x = np.arange(len(runs)); w = 0.2
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for i, c in enumerate(cats):
        vals = [data[r][c] for r in runs]
        ax.bar(x + (i - 1.5) * w, vals, w, color=colors[c], label=names[c])
    ax.set_xticks(x); ax.set_xticklabels([LABELS[r] for r in runs])
    ax.set_ylabel("# evidence-present wrong answers (turn_hit=1)")
    ax.set_title("Why retrieved-evidence answers still fail (LLM triage)")
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "06_evidence_present_triage.png")


# ---- 7. abstention ----------------------------------------------------------

def fig_abstention(runs):
    accs = []
    for r in ORDER:
        ab = [q for q in runs[r].values() if q["is_abstention"]]
        accs.append(sum(q["judge_correct"] for q in ab) / len(ab))
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar([LABELS[r] for r in ORDER], accs, color=[C[r] for r in ORDER])
    for b, a in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, a + 0.01, f"{a:.3f}",
                ha="center", va="bottom", fontweight="bold")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("abstention accuracy (correctly abstained)")
    ax.set_title("Abstention accuracy by mode (n=30 unanswerable)")
    ax.spines[["top", "right"]].set_visible(False)
    _save(fig, "07_abstention_accuracy.png")


# ---- diagrams ---------------------------------------------------------------

def _box(ax, xy, w, h, text, color):
    ax.add_patch(FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.4, edgecolor="#333", facecolor=color))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center",
            fontsize=9.5, wrap=True)


def _arrow(ax, a, b):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14,
                                 linewidth=1.3, color="#333"))


def fig_architecture():
    fig, ax = plt.subplots(figsize=(11, 2.8))
    ax.set_xlim(0, 11); ax.set_ylim(0, 2.8); ax.axis("off")
    stages = [
        ("conversation\nturns", "#e8f0fe"),
        ("extractor LLM\n(claims + obs)", "#d2e3fc"),
        ("embed +\nnamespace", "#fce8e6"),
        ("consolidate\n(dedupe/update)", "#fef7e0"),
        ("retrieve\n(flat / agentic)", "#e6f4ea"),
        ("reader LLM\n(answer / abstain)", "#f3e8fd"),
    ]
    w, h, gap, y = 1.55, 1.2, 0.32, 0.8
    xs = []
    x = 0.25
    for text, color in stages:
        _box(ax, (x, y), w, h, text, color)
        xs.append(x + w)
        x += w + gap
    for i in range(len(stages) - 1):
        _arrow(ax, (xs[i], y + h / 2), (xs[i] + gap, y + h / 2))
    ax.set_title("Semantic-memory write/read pipeline", fontsize=12, pad=8)
    _save(fig, "08_architecture.png")


def fig_hybrid_retrieval():
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.set_xlim(0, 9); ax.set_ylim(0, 4.2); ax.axis("off")
    _box(ax, (0.3, 1.6), 1.7, 1.0, "question", "#e8f0fe")
    _box(ax, (2.6, 2.7), 2.3, 1.0, "claim retrieval\n(semantic memory)", "#d2e3fc")
    _box(ax, (2.6, 0.5), 2.3, 1.0, "raw-span lookup\n(verbatim turn text)", "#fce8e6")
    _box(ax, (5.5, 1.6), 1.6, 1.0, "merge +\nrerank", "#fef7e0")
    _box(ax, (7.3, 1.6), 1.5, 1.0, "reader LLM", "#f3e8fd")
    _arrow(ax, (2.0, 2.1), (2.6, 3.2))
    _arrow(ax, (2.0, 2.1), (2.6, 1.0))
    _arrow(ax, (4.9, 3.2), (5.5, 2.3))
    _arrow(ax, (4.9, 1.0), (5.5, 1.9))
    _arrow(ax, (7.1, 2.1), (7.3, 2.1))
    ax.text(4.5, 3.95,
            "Proposed: keep compressed claims for recall, attach verbatim spans "
            "to fix span-loss (B)",
            ha="center", fontsize=10, style="italic")
    _save(fig, "09_proposed_hybrid_retrieval.png")


def main() -> None:
    runs = {r: load(r) for r in ORDER}
    print("rendering figures ->", FIG_DIR.relative_to(HARNESS))
    fig_accuracy_ladder(runs)
    fig_bottleneck_flip(runs)
    fig_retention_by_type(runs)
    fig_context_cost(runs)
    fig_matched_hit(runs)
    fig_triage()
    fig_abstention(runs)
    fig_architecture()
    fig_hybrid_retrieval()


if __name__ == "__main__":
    main()
