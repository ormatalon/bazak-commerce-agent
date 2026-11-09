"""Read source cases without mutating their V1 expectations."""

import csv
import hashlib
import json
import math
from pathlib import Path

from app.config import ROOT

SOURCES = ("deterministic", "behavioral", "adversarial", "hebrew")


def load_cases(root: Path = ROOT / "datasets") -> list[dict]:
    cases = []
    for source in SOURCES:
        path = root / (source + (".csv" if source == "deterministic" else ".jsonl"))
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle)) if path.suffix == ".csv" else [json.loads(s) for s in handle if s.strip()]
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        for row in rows:
            if not isinstance(row, dict) or row.get('id') in (None, ''):
                raise ValueError(f'invalid case identity in {source}')
            key = f"{source}:{row['id']}"
            turns = row.get("turns", [row.get("query")])
            if not isinstance(turns, list) or not turns or not all(isinstance(t, str) and t.strip() for t in turns):
                raise ValueError(f"invalid turns: {key}")
            cases.append({**row, "key": key, "source": source, "turns": turns,
                          "source_hash": source_hash})
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


def load_evidence(directory: Path) -> tuple[dict, list[dict]]:
    """Validate immutable evidence before re-scoring or creating remote artifacts."""
    metadata = json.loads((directory / 'metadata.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (directory / 'cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    if not rows or len(rows) != metadata.get('case_count'):
        raise ValueError('Evidence is empty or incomplete; no experiment should be created')
    keys = [row['key'] for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate case identity in evidence')
    if 'case_keys' in metadata and set(keys) != set(metadata['case_keys']):
        raise ValueError('Evidence identities differ from the run manifest')
    for row in rows:
        if not isinstance(row['turns'], list) or not isinstance(row['case']['turns'], list):
            raise ValueError(f"Conversation turns must be lists: {row['key']}")
        if not row['error'] and len(row['turns']) != len(row['case']['turns']):
            raise ValueError(f"Incomplete successful conversation: {row['key']}")
        if any(not math.isfinite(value) for value in row['metrics'].values() if isinstance(value, (int, float))):
            raise ValueError(f"Non-finite metric in {row['key']}")
    return metadata, rows
