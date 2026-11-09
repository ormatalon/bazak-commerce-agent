"""Read source cases without mutating their V1 expectations."""

import csv
import hashlib
import json
from pathlib import Path

from app.config import ROOT

SOURCES = ("deterministic", "behavioral", "adversarial", "hebrew")


def load_cases(root: Path = ROOT / "datasets") -> list[dict]:
    cases = []
    for source in SOURCES:
        path = root / (source + (".csv" if source == "deterministic" else ".jsonl"))
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle)) if path.suffix == ".csv" else [json.loads(s) for s in handle if s.strip()]
        for row in rows:
            key = f"{source}:{row['id']}"
            turns = row.get("turns") or [row["query"]]
            if not turns or not all(isinstance(t, str) and t.strip() for t in turns):
                raise ValueError(f"invalid turns: {key}")
            cases.append({**row, "key": key, "source": source, "turns": turns,
                          "source_hash": hashlib.sha256(path.read_bytes()).hexdigest()})
    if len({c["key"] for c in cases}) != len(cases):
        raise ValueError("duplicate source case identity")
    return cases


def load_overlay(root: Path = ROOT / "datasets" / "v2") -> dict[str, dict]:
    path = root / "expectations.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len({row["key"] for row in rows}) != len(rows):
        raise ValueError("duplicate overlay identity")
    return {row["key"]: row for row in rows}
