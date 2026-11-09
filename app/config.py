"""Versioned configuration. Thresholds stay provisional until final evaluation."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from functools import lru_cache
import subprocess

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def source_revision() -> str:
    """Resolve once per process so traces can be tied to their implementation."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL, timeout=2).strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


@dataclass(frozen=True)
class RetrievalConfig:
    model: str = "intfloat/multilingual-e5-small"
    revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    title_weight: float = 0.6
    category_boost: float = 0.1
    strong_threshold: float = 2.0
    borderline_threshold: float = 1.0
    candidate_window: int = 10
    text_version: int = 1
    calibrated: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.title_weight <= 1:
            raise ValueError("title weight must be between zero and one")
        if self.strong_threshold <= self.borderline_threshold:
            raise ValueError("strong threshold must exceed borderline threshold")

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()


def catalog_hash(products: list) -> str:
    payload = [p.model_dump(mode="json") for p in products]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
