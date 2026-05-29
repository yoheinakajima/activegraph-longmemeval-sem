"""Run manifest and output writers (manifest.json, hypotheses.jsonl, metrics.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
        fh.write("\n")


def write_manifest(run_dir: Path, manifest: dict) -> None:
    write_json(run_dir / "manifest.json", manifest)


def write_hypotheses(run_dir: Path, records: list[dict]) -> None:
    rows = [r for r in records if r.get("status") == "done"]
    rows.sort(key=lambda r: r.get("question_id", ""))
    path = run_dir / "hypotheses.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(
                json.dumps(
                    {
                        "question_id": r.get("question_id"),
                        "question_type": r.get("question_type"),
                        "is_abstention": r.get("is_abstention"),
                        "question": r.get("question"),
                        "gold_answer": r.get("gold_answer"),
                        "hypothesis": r.get("hypothesis"),
                        "judge_correct": r.get("judge_correct"),
                        "turn_hit": r.get("turn_hit"),
                        "session_hit": r.get("session_hit"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_metrics(run_dir: Path, metrics: dict) -> None:
    write_json(run_dir / "metrics.json", metrics)
