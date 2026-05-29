"""CLI entrypoint: ``python -m longmemeval_harness ...``"""

from __future__ import annotations

import argparse
import sys

from .config import (
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_PROVIDER,
    DEFAULT_READER_PRESET,
    DEFAULT_READER_PROVIDER,
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
        judge_provider=args.judge_provider,
        judge_model=args.judge_model,
        seed=args.seed,
        no_judge=args.no_judge,
        limit=args.limit,
        concurrency=args.concurrency,
    )
    run_benchmark(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
