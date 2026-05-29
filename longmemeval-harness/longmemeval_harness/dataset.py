"""Dataset acquisition and typed loading for LongMemEval.

Downloads the cleaned ``oracle`` and ``s`` splits from their HuggingFace
release into ``data/``, records each file's SHA-256, and parses each
instance into typed records with per-turn provenance fields.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import DATA_DIR, HF_BASE, SPLITS

_DATE_FORMATS = ("%Y/%m/%d (%a) %H:%M", "%Y/%m/%d %H:%M", "%Y/%m/%d")


def parse_date(text: Optional[str]) -> Optional[datetime]:
    """Best-effort parse of a LongMemEval session date string."""
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


@dataclass
class Turn:
    session_id: str
    turn_index: int
    role: str
    content: str
    has_answer: bool


@dataclass
class Session:
    session_id: str
    date: Optional[str]
    turns: list[Turn] = field(default_factory=list)

    @property
    def date_obj(self) -> Optional[datetime]:
        return parse_date(self.date)


@dataclass
class Instance:
    question_id: str
    question_type: str
    question: str
    answer: str
    question_date: Optional[str]
    answer_session_ids: list[str]
    sessions: list[Session]

    @property
    def is_abstention(self) -> bool:
        return self.question_id.endswith("_abs")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_path(split: str, data_dir: Path = DATA_DIR) -> Path:
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; expected one of {list(SPLITS)}")
    return data_dir / SPLITS[split]


def download_split(
    split: str, data_dir: Path = DATA_DIR, force: bool = False
) -> Path:
    """Download a split into ``data_dir`` if not already present."""
    dest = split_path(split, data_dir)
    if dest.exists() and not force:
        return dest
    data_dir.mkdir(parents=True, exist_ok=True)
    url = f"{HF_BASE}/{SPLITS[split]}"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    print(f"[dataset] downloading {split} from {url}")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)
    print(f"[dataset] saved {dest} ({dest.stat().st_size:,} bytes)")
    return dest


def _parse_instance(raw: dict) -> Instance:
    session_ids = raw.get("haystack_session_ids") or []
    sessions_raw = raw.get("haystack_sessions") or []
    dates = raw.get("haystack_dates") or []
    sessions: list[Session] = []
    for i, turns_raw in enumerate(sessions_raw):
        sid = session_ids[i] if i < len(session_ids) else f"session_{i}"
        date = dates[i] if i < len(dates) else None
        turns = [
            Turn(
                session_id=sid,
                turn_index=j,
                role=t.get("role", ""),
                content=t.get("content", ""),
                has_answer=bool(t.get("has_answer", False)),
            )
            for j, t in enumerate(turns_raw)
        ]
        sessions.append(Session(session_id=sid, date=date, turns=turns))
    return Instance(
        question_id=raw["question_id"],
        question_type=raw["question_type"],
        question=raw["question"],
        answer=str(raw.get("answer", "")),
        question_date=raw.get("question_date"),
        answer_session_ids=list(raw.get("answer_session_ids") or []),
        sessions=sessions,
    )


def load_split(
    split: str, data_dir: Path = DATA_DIR, download: bool = True
) -> list[Instance]:
    """Load and parse a split into typed ``Instance`` records."""
    dest = split_path(split, data_dir)
    if not dest.exists():
        if download:
            download_split(split, data_dir)
        else:
            raise FileNotFoundError(
                f"{dest} not found; run with download enabled or use "
                f"`python -m longmemeval_harness --download-only --split {split}`"
            )
    with open(dest, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return [_parse_instance(r) for r in raw]
