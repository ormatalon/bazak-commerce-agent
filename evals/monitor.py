"""Generate a small local monitoring view from sanitized runtime events."""

import argparse
from collections import Counter
from html import escape
import json
from pathlib import Path

import numpy as np

from app.config import ROOT
from app.monitoring import JOURNAL


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal',type=Path,default=JOURNAL)
    parser.add_argument('--output',type=Path,default=ROOT/'monitoring/dashboard.html')
    args=parser.parse_args()
    if not args.journal.exists():
        raise SystemExit('No runtime events yet. Run the app or dataset replay first.')
    events=[json.loads(line) for line in args.journal.read_text(encoding='utf-8').splitlines() if line.strip()]
    sections=[]
    for traffic in sorted({e['traffic'] for e in events}):
        rows=[e for e in events if e['traffic']==traffic]
        latency=[e['duration_ms'] for e in rows]
        errors=sum(bool(e['error']) for e in rows)
        reasons=Counter(reason for e in rows for reason in e['reasons'])
        sections.append(f"<section><h2>{escape(traffic)} · {len(rows)} turns</h2><p>Errors: {errors}; fallback turns: {sum(e['fallback'] for e in rows)}; p50: {np.percentile(latency,50):.0f} ms; p95: {np.percentile(latency,95):.0f} ms.</p><p>Outcomes: {escape(json.dumps(reasons))}</p></section>")
    evidence=''.join(f"<tr><td>{escape(e['timestamp_utc'])}</td><td>{escape(e['traffic'])}</td><td>{e['duration_ms']:.0f}</td><td>{e['card_count']}</td><td>{escape(e['error'] or ', '.join(e['reasons']))}</td><td>{escape(e['trace_id'] or 'unavailable')}</td></tr>" for e in events[-100:][::-1])
    html='<!doctype html><meta charset="utf-8"><title>Bazak V2 monitoring</title><style>body{font:15px system-ui;margin:32px;max-width:1200px;color:#202124}h1{font-size:24px}section{border-bottom:1px solid #ddd;padding:12px 0}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd;font-size:13px}table{border-collapse:collapse;width:100%}</style>'
    html+='<h1>Bazak V2 monitoring</h1><p>Source: local runtime journal. Regenerate this view after a session. Percentiles describe this sample only; LLM token/cost detail lives in the linked LangSmith project.</p>'
    html+=''.join(sections)+'<h2>Latest 100 turns</h2><table><thead><tr><th>UTC</th><th>Traffic</th><th>Latency (ms)</th><th>Cards</th><th>Outcome/error</th><th>LangSmith trace ID</th></tr></thead><tbody>'+evidence+'</tbody></table>'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(html,encoding='utf-8')
    print('Monitoring view:',args.output)


if __name__=='__main__':
    main()
