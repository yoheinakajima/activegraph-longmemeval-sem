"""Regenerate + verify the stable 50-question scaffold development slice.

The scaffolded-reader development used a fixed 50-question slice of the ``s``
split (the same deterministic stratified sample the ``small`` tier draws), so
results on it are reproducible and the slice can be cited by content hash rather
than by referencing a gitignored run directory.

This writes a committed manifest at ``analysis/data/scaffold_slice.json`` with
the seed, size, sampling method, the 50 sorted question ids, and their SHA-256,
then verifies the hash matches the pinned expected value.

Run: ../.pythonlibs/bin/python -m analysis.scaffold_slice   (from longmemeval-harness/)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from longmemeval_harness.config import SAMPLE_SEED, TIER_SIZES
from longmemeval_harness.dataset import load_split, sha256_of, split_path
from longmemeval_harness.sampler import stratified_sample

OUT = Path(__file__).resolve().parent / "data" / "scaffold_slice.json"

# Pinned hash of the sorted 50 ids; regenerating must reproduce this exactly.
EXPECTED_SHA256 = (
    "e293d7b2239da1e2ff2097ae44138e872cfa95e47a5400c0c9fed5c6dcf5a107"
)

SPLIT = "s"
SIZE = TIER_SIZES["small"]  # 50


def build() -> dict:
    instances = load_split(SPLIT)
    ids = sorted(stratified_sample(instances, SIZE, SAMPLE_SEED))
    sha = hashlib.sha256("\n".join(ids).encode()).hexdigest()
    return {
        "description": (
            "Fixed 50-question scaffolded-reader development slice. Identical to "
            "the deterministic stratified sample the 'small' tier draws from the "
            "'s' split; cite by sha256 of the sorted ids."
        ),
        "split": SPLIT,
        "split_file_sha256": sha256_of(split_path(SPLIT)),
        "seed": SAMPLE_SEED,
        "size": SIZE,
        "method": "stratified_sample (largest-remainder by question_type, seeded)",
        "question_ids_sha256": sha,
        "question_ids": ids,
    }


def main() -> None:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    sha = payload["question_ids_sha256"]
    ok = sha == EXPECTED_SHA256
    print(f"wrote {OUT.relative_to(OUT.parents[2])}")
    print(f"  n={payload['size']}  seed={payload['seed']}  sha256={sha}")
    print(f"  matches pinned EXPECTED_SHA256: {ok}")
    if not ok:
        raise SystemExit(
            f"scaffold slice hash drift: got {sha}, expected {EXPECTED_SHA256}"
        )


if __name__ == "__main__":
    main()
