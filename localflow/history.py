"""Local dictation history, stored as JSON Lines on this machine only."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import data_dir


@dataclass
class Entry:
    timestamp: float
    raw: str
    cleaned: str
    duration_seconds: float


def history_path() -> Path:
    return data_dir() / "history.jsonl"


def append(entry: Entry, path: Path | None = None) -> None:
    path = path or history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def read_recent(limit: int = 20, path: Path | None = None) -> list[Entry]:
    path = path or history_path()
    if not path.exists():
        return []
    entries: list[Entry] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(Entry(**json.loads(line)))
    return entries[-limit:]


def record(raw: str, cleaned: str, duration_seconds: float) -> None:
    append(
        Entry(
            timestamp=time.time(),
            raw=raw,
            cleaned=cleaned,
            duration_seconds=duration_seconds,
        )
    )
