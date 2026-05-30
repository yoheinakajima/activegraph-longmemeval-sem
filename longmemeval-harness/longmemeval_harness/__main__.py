"""CLI entrypoint: ``python -m longmemeval_harness ...``"""

from __future__ import annotations

import argparse
import sys

from .config import (
    DEFAULT_EXTRACTION_MODE,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_PROVIDER,
    DEFAULT_READER_MODE,
    DEFAULT_READER_PRESET,
    DEFAULT_READER_PROVIDER,
    DEFAULT_RETAIN_ASSISTANT_FACTS,
    QUESTION_TYPES,
    READER_MODES,
    READER_PRESETS,
    SAMPLE_SEED,
    SPLITS,
    TIER_SIZES,
)
from .dataset import download_split, sha256_of, split_path
from .orchestrator import RunConfig, run_benchmark


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="longmemeval_harness",
        description="Evaluate the activegraph-memory pack on LongMemEval.",
    )
    p.add_argument("--size", choices=list(TIER_SIZES), default="smoke",
                   help="tier: smoke (~10), small (~50), full (500)")
    p.add_argument("--split", choices=list(SPLITS), default="oracle",
                   help="oracle (dev) or s (real benchmark)")
    p.add_argument("--run-id", default=None,
                   help="override run id (default: <split>-<size>-seed<seed>)")
    p.add_argument("--seed", type=int, default=SAMPLE_SEED)
    p.add_argument("--reader-provider", default=DEFAULT_READER_PROVIDER)
    p.add_argument("--reader", choices=list(READER_PRESETS),
                   default=DEFAULT_READER_PRESET,
                   help="named reader preset (sonnet=paper default, opus=stronger)")
    p.add_argument("--reader-model", default=None,
                   help="explicit reader model id; overrides --reader")
    p.add_argument("--reader-mode", choices=list(READER_MODES),
                   default=DEFAULT_READER_MODE,
                   help="parity (frozen paper reader, default) or NON-PARITY "
                        "scaffolded / scaffolded_with_self_check reasoning reader")
    p.add_argument("--judge-provider", default=DEFAULT_JUDGE_PROVIDER)
    p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    p.add_argument("--no-judge", action="store_true",
                   help="skip the LLM judge (retrieval sidecar + reader only)")
    p.add_argument("--limit", type=int, default=None,
                   help="cap number of sampled questions (debugging)")
    p.add_argument("--concurrency", type=int, default=1,
                   help="parallel worker processes (deterministic ingest is "
                        "CPU-bound; >1 speeds up large splits, default 1)")
    p.add_argument("--download-only", action="store_true",
                   help="download the split, print its SHA-256, and exit")
    p.add_argument("--extraction", choices=["deterministic", "llm"],
                   default=DEFAULT_EXTRACTION_MODE,
                   help="memory extraction: deterministic heuristic (default, "
                        "offline) or llm (gpt-4o-mini, cached; needs OPENAI_API_KEY)")
    p.add_argument("--retain-assistant-facts",
                   action=argparse.BooleanOptionalAction,
                   default=DEFAULT_RETAIN_ASSISTANT_FACTS,
                   help="extract facts from ASSISTANT turns at ingest (default on; "
                        "--no-retain-assistant-facts reproduces the task18 baseline)")
    p.add_argument("--question-type", choices=list(QUESTION_TYPES), default=None,
                   help="restrict the benchmark to a single question type (the "
                        "abstention *_abs variants of that type are included)")
    p.add_argument("--retrieval-strategy", choices=["flat", "agentic"],
                   default="flat",
                   help="retrieval: flat keyword+vector blend (default) or "
                        "agentic concept-graph loop (implies --concept-graph)")
    p.add_argument("--concept-graph", action="store_true",
                   help="build the entity/topic concept graph during ingest "
                        "(auto-enabled by --retrieval-strategy agentic)")
    p.add_argument("--rerank", choices=["off", "llm"], default="off",
                   help="strong LLM reranker over the flat path's candidate "
                        "facts (cached; needs OPENAI_API_KEY). off = baseline.")
    p.add_argument("--rerank-keep", type=int, default=12,
                   help="max facts kept after rerank (only with --rerank llm)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.download_only:
        download_split(args.split)
        path = split_path(args.split)
        print(f"{path.name}  sha256={sha256_of(path)}")
        return 0

    reader_model = args.reader_model or READER_PRESETS[args.reader]

    cfg = RunConfig(
        size=args.size,
        split=args.split,
        run_id=args.run_id,
        reader_provider=args.reader_provider,
        reader_model=reader_model,
        reader_mode=args.reader_mode,
        retain_assistant_facts=args.retain_assistant_facts,
        question_type=args.question_type,
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        seed=args.seed,
        no_judge=args.no_judge,
        limit=args.limit,
        concurrency=args.concurrency,
        extraction=args.extraction,
        retrieval_strategy=args.retrieval_strategy,
        concept_graph=args.concept_graph,
        rerank=args.rerank,
        rerank_keep=args.rerank_keep,
    )
    run_benchmark(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
