"""Orchestrator: ties the pipeline together behind one resumable command.

Per run it loads a split, pins its SHA-256, deterministically samples the
chosen tier, then for each not-yet-completed question: drives the pack
(ingest + query), runs the LLM reader, scores retrieval (deterministic),
and runs the LLM judge — persisting every step to the run store. On
startup it skips already-completed ids so the run resumes after any
interruption. After the loop it (re)writes the manifest, hypotheses.jsonl,
and metrics report from the durable store.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from activegraph_memory import MemorySettings, pack

from . import __version__
from .adapter import run_pack
from .config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_PROVIDER,
    DEFAULT_READER_MODEL,
    DEFAULT_READER_PROVIDER,
    RUNS_DIR,
    SAMPLE_SEED,
    TIER_SIZES,
)
from .dataset import load_split, sha256_of, split_path
from .judge import judge as run_judge
from .llm import LLMClient
from .manifest import write_hypotheses, write_manifest, write_metrics
from .reader import read as run_reader
from .sampler import stratified_sample
from .scoring import aggregate, score_retrieval
from .store import RunStore


@dataclass
class RunConfig:
    size: str = "smoke"
    split: str = "oracle"
    run_id: Optional[str] = None
    reader_provider: str = DEFAULT_READER_PROVIDER
    reader_model: str = DEFAULT_READER_MODEL
    judge_provider: str = DEFAULT_JUDGE_PROVIDER
    judge_model: str = DEFAULT_JUDGE_MODEL
    seed: int = SAMPLE_SEED
    no_judge: bool = False
    limit: Optional[int] = None

    def default_run_id(self) -> str:
        return f"{self.split}-{self.size}-seed{self.seed}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_benchmark(cfg: RunConfig) -> dict:
    if cfg.size not in TIER_SIZES:
        raise ValueError(f"unknown size {cfg.size!r}; pick from {list(TIER_SIZES)}")

    run_id = cfg.run_id or cfg.default_run_id()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[run] {run_id}  split={cfg.split}  size={cfg.size}")
    instances = load_split(cfg.split)
    data_path = split_path(cfg.split)
    data_sha = sha256_of(data_path)
    by_id = {i.question_id: i for i in instances}

    sample_ids = stratified_sample(instances, TIER_SIZES[cfg.size], cfg.seed)
    if cfg.limit is not None:
        sample_ids = sample_ids[: cfg.limit]

    store = RunStore(run_dir / "store.sqlite")
    completed = store.completed_ids()
    todo = [q for q in sample_ids if q not in completed]
    print(
        f"[run] sample={len(sample_ids)}  already_done={len(completed & set(sample_ids))}"
        f"  todo={len(todo)}"
    )

    settings = MemorySettings()
    client = LLMClient()
    started = time.time()
    resolved = {
        "reader": cfg.reader_model,
        "judge": cfg.judge_model,
    }

    for n, qid in enumerate(todo, 1):
        inst = by_id[qid]
        base = {
            "question_id": qid,
            "question_type": inst.question_type,
            "is_abstention": inst.is_abstention,
            "question": inst.question,
            "question_date": inst.question_date,
            "gold_answer": inst.answer,
        }
        try:
            t0 = time.time()
            bundle = run_pack(inst, settings)
            t_ingest = time.time() - t0

            t0 = time.time()
            reader = run_reader(
                client, cfg.reader_provider, cfg.reader_model, inst, bundle
            )
            t_read = time.time() - t0
            resolved["reader"] = reader.resolved_model

            sc = score_retrieval(inst, bundle)

            judge_fields: dict = {
                "judge_requested_model": None,
                "judge_resolved_model": None,
                "judge_correct": None,
                "judge_raw": None,
                "judge_total_tokens": None,
            }
            t_judge = 0.0
            if not cfg.no_judge:
                t0 = time.time()
                jr = run_judge(
                    client, cfg.judge_provider, cfg.judge_model, inst, reader.hypothesis
                )
                t_judge = time.time() - t0
                resolved["judge"] = jr.resolved_model
                judge_fields = {
                    "judge_requested_model": jr.requested_model,
                    "judge_resolved_model": jr.resolved_model,
                    "judge_correct": jr.correct,
                    "judge_raw": jr.raw,
                    "judge_total_tokens": jr.total_tokens,
                }

            record = {
                **base,
                "status": "done",
                "error": None,
                "ingest_n_obs": bundle.n_observations,
                "ingest_n_claims": bundle.n_claims,
                "pack_errors": bundle.pack_errors,
                "retrieved_object_ids": bundle.retrieved_object_ids,
                "used_memory_ids": bundle.used_memory_ids,
                "evidence_ids": bundle.evidence_ids,
                "context_turn_ids": bundle.context_turn_ids,
                "context_session_ids": bundle.context_session_ids,
                "retrieval_summary": bundle.retrieval_summary,
                "assembled_context": bundle.assembled_context,
                "hypothesis": reader.hypothesis,
                "reader_requested_model": reader.requested_model,
                "reader_resolved_model": reader.resolved_model,
                "reader_prompt_tokens": reader.prompt_tokens,
                "reader_completion_tokens": reader.completion_tokens,
                "reader_total_tokens": reader.total_tokens,
                "context_tokens": reader.context_tokens,
                "truncated": reader.truncated,
                "turn_recall": sc.turn_recall,
                "turn_hit": sc.turn_hit,
                "session_recall": sc.session_recall,
                "session_hit": sc.session_hit,
                "n_gold_turns": sc.n_gold_turns,
                "n_gold_sessions": sc.n_gold_sessions,
                **judge_fields,
                "t_ingest": t_ingest,
                "t_read": t_read,
                "t_judge": t_judge,
                "t_total": t_ingest + t_read + t_judge,
            }
            store.upsert(record)
            flag = "" if record["judge_correct"] is None else (
                "OK" if record["judge_correct"] else "X "
            )
            print(
                f"[{n}/{len(todo)}] {qid} {inst.question_type} {flag} "
                f"turn_hit={sc.turn_hit} ({t_ingest:.1f}s ingest)"
            )
        except Exception as exc:  # noqa: BLE001 - record + continue
            store.upsert(
                {
                    **base,
                    "status": "error",
                    "error": f"{exc}\n{traceback.format_exc()}",
                }
            )
            print(f"[{n}/{len(todo)}] {qid} ERROR: {exc}")

    wall = time.time() - started
    records = store.all_records()
    metrics = aggregate(records)

    manifest = {
        "run_id": run_id,
        "created_at": _now_iso(),
        "harness_version": __version__,
        "pack_name": pack.name,
        "pack_version": pack.version,
        "dataset": {
            "split": cfg.split,
            "file": data_path.name,
            "sha256": data_sha,
            "n_instances": len(instances),
        },
        "sample": {
            "size_tier": cfg.size,
            "target_size": TIER_SIZES[cfg.size],
            "actual_size": len(sample_ids),
            "seed": cfg.seed,
        },
        "models": {
            "reader": {
                "provider": cfg.reader_provider,
                "requested": cfg.reader_model,
                "resolved": resolved["reader"],
            },
            "judge": {
                "provider": cfg.judge_provider,
                "requested": cfg.judge_model,
                "resolved": resolved["judge"],
                "enabled": not cfg.no_judge,
            },
        },
        "memory_settings": settings.model_dump(),
        "wall_clock_seconds": wall,
        "status_counts": store.status_counts(),
        "metrics": metrics,
    }

    write_manifest(run_dir, manifest)
    write_hypotheses(run_dir, records)
    write_metrics(run_dir, metrics)
    store.close()

    print(f"\n[done] {run_id} in {wall:.1f}s")
    print(f"[done] overall_accuracy={metrics['overall_accuracy']}")
    print(f"[done] outputs in {run_dir}")
    return manifest
