"""Minimal local monitoring journal; sanitized facts only, never chat text."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from threading import Lock

from app.config import ROOT

_lock=Lock()
logger=logging.getLogger(__name__)
JOURNAL=ROOT/'monitoring'/'turns.jsonl'


def record_turn(result, traffic: str, duration_ms: float, error: str | None = None,
                path: Path = JOURNAL) -> None:
    event={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'traffic':traffic,
           'duration_ms':duration_ms,'error':error,
           'trace_id':result.trace_id if result else None,
           'intent':result.parsed.intent if result else None,
           'card_count':sum(len(o.cards) for o in result.outcomes) if result else 0,
           'fallback':any(c.alternative for o in result.outcomes for c in o.cards) if result else False,
           'reasons':[o.reason for o in result.outcomes] if result else []}
    try:
        with _lock:
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(event)+'\n')
    except OSError as failure:
        logger.warning('Monitoring journal failed: %s',type(failure).__name__)
