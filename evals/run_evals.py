"""Reproducible full-conversation replay. Outputs local evidence before upload."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import subprocess
from time import perf_counter

from dotenv import load_dotenv

from app.catalog import load_catalog_data
from app.config import ROOT, RetrievalConfig, catalog_hash
from app.currency import RateSource, get_rate_provider
from app.embeddings import LocalEmbedder
from app.index import ProductIndex
from app.llm import openai_llm
from app.observability import flush
from app.pipeline import run_turn
from app.schemas import ConversationState
from app.parser import SYSTEM as PARSER_PROMPT
from app.product_type import SYSTEM as TYPE_PROMPT, BATCH_SIZE
from app.responder import SYSTEM as RESPONSE_PROMPT
from evals.datasets import FrozenRateProvider, load_cases, load_overlay
from evals.scoring import aggregate, failure_metrics, score_record


def run_case(case, catalog, categories, index, llm=openai_llm, overlay=None, rate_provider: RateSource | None = None) -> dict:
    started=perf_counter()
    rate_provider = rate_provider or FrozenRateProvider()
    state=ConversationState()
    turns=[]
    try:
        for number,message in enumerate(case['turns']):
            result=run_turn(message,state,catalog,categories,llm,index,case['key'],traffic='evaluation',rate_provider=rate_provider)
            state=result.state
            turn={'turn':number,'result':result.model_dump(mode='json')}
            turns.append(turn)
        error_name = None
    except Exception as error:
        # Keep failures in denominator. Never persist provider exception text/secrets.
        error_name = type(error).__name__
    row = {'key':case['key'],'source':case['source'],'difficulty':case.get('difficulty'),
           'case':case,'v2_expectation':overlay,'turns':turns,'error':error_name,
           'error_stage':'pipeline' if error_name else None, 'duration_ms':(perf_counter()-started)*1000}
    try:
        return score_record(row, catalog)
    except Exception as error:
        # Preserve all predictions even when a scorer itself fails, so a free
        # re-score can recover them. Do not abort the other dataset cases.
        row.update(error=type(error).__name__, error_stage='scoring', metrics=failure_metrics(case))
        return row


def report(rows, metadata) -> str:
    errors=sum(bool(r['error']) for r in rows)
    summary=aggregate(rows)
    lines=['# V2 dataset evaluation', '', f"Cases: {len(rows)}; execution errors: {errors}.",
           '', 'Semantic labels are drafts unless explicitly marked reviewed. Automatic checks do not establish full grounding or task success.',
           '', '## Run configuration', '', '```json',json.dumps(metadata,indent=2,ensure_ascii=False),'```', '', '## Automatic metrics', '']
    for key,score in summary.items():
        lines.append(f"- {key}: {score['mean']:.3f} ({score['numerator']:g}/{score['denominator']})")
    for field in ('source','difficulty'):
        lines.extend(['',f'## By {field}',''])
        for value in sorted({str(r.get(field)) for r in rows}):
            subset=[r for r in rows if str(r.get(field))==value]
            lines.append(f"### {value} ({len(subset)} cases)")
            lines.append('')
            for metric,score in aggregate(subset).items():
                lines.append(f"- {metric}: {score['mean']:.3f} (n={score['denominator']})")
    lines.extend(['','## Case evidence',''])
    for row in rows:
        lines.extend([f"### {row['key']}",'', 'Turns: '+json.dumps(row['case']['turns'],ensure_ascii=False),
                      '', 'Legacy expectation: '+str(row['case'].get('expected_behavior','CSV filters')), ''])
        if row['error']:
            lines.append('ERROR: '+row['error']+' (stage: '+str(row.get('error_stage','unspecified'))+')')
        for turn in row['turns']:
            result=turn['result']
            lines.extend([f"Turn {turn['turn']+1}: {result['reply']}",'',f"Trace ID: {result['trace_id']}",''])
        failures=[k for k,v in row['metrics'].items() if isinstance(v,(int,float)) and v<1]
        lines.append('Non-perfect automatic checks: '+', '.join(failures))
        lines.append('')
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Required: explicitly enable paid gpt-6-luna calls.')
    parser.add_argument('--source',choices=['all','deterministic','behavioral','adversarial','hebrew'],default='all')
    parser.add_argument('--limit',type=int)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--config',type=Path,help='JSON RetrievalConfig overrides, e.g. calibrated thresholds.')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--live-rates',action='store_true',help='Use current API rates instead of the frozen evaluation fixture.')
    args=parser.parse_args()
    if args.workers < 1 or (args.limit is not None and args.limit < 1):
        parser.error('workers and limit must be positive integers')
    if not args.live:
        parser.error('Use --live to enable provider calls; unit checks use pytest.')
    load_dotenv(ROOT/'.env')
    cases=[c for c in load_cases() if args.source=='all' or c['source']==args.source]
    overlays=load_overlay()
    if args.limit: cases=cases[:args.limit]
    rate_provider = get_rate_provider() if args.live_rates else FrozenRateProvider()
    config=RetrievalConfig(**json.loads(args.config.read_text(encoding='utf-8'))) if args.config else RetrievalConfig()
    catalog, categories = load_catalog_data()
    index=ProductIndex(catalog,LocalEmbedder(config),config)
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=args.output or ROOT/'evals'/'artifacts'/timestamp
    output.mkdir(parents=True,exist_ok=False)
    metadata={'timestamp_utc':timestamp,'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'catalog_hash':catalog_hash(catalog),'config':asdict(config),
              'source_hashes':{c['source']:c['source_hash'] for c in cases},
              'labels_status':'draft; semantic release gates not certified',
              'overlay_cases':len(overlays),'reviewed_overlay_cases':sum(o.get('review_status')=='reviewed' for o in overlays.values()),
              'case_count':len(cases),'case_keys':[case['key'] for case in cases],
              'model':'gpt-6-luna','workers':args.workers,'sdk_retries':1}
    metadata['exchange_rate_mode'] = 'live cached, conversation-pinned' if args.live_rates else 'frozen fixture'
    if not args.live_rates:
        metadata['exchange_rate_fixture_sha256'] = hashlib.sha256((ROOT/'datasets/v2/exchange_rates.json').read_bytes()).hexdigest()
    metadata['prompt_hashes']={name:hashlib.sha256(text.encode()).hexdigest() for name,text in
                               [('parser',PARSER_PROMPT),('product_type',TYPE_PROMPT),('responder',RESPONSE_PROMPT)]}
    metadata['product_type_batch_size']=BATCH_SIZE
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    (output/'catalog.json').write_text(json.dumps({'products':[p.model_dump(mode='json') for p in catalog],
                                                  'categories':categories},ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    with (output/'cases.jsonl').open('w',encoding='utf-8') as handle, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_case,c,catalog,categories,index,overlay=overlays.get(c['key']),rate_provider=rate_provider):c['key'] for c in cases}
        for future in as_completed(futures):
            row=future.result()
            rows.append(row)
            handle.write(json.dumps(row,ensure_ascii=False)+'\n'); handle.flush()
            print(f"{len(rows)}/{len(cases)} {row['key']} {'ERROR '+row['error'] if row['error'] else 'done'}",flush=True)
    rows.sort(key=lambda row:row['key'])
    (output/'report.md').write_text(report(rows,metadata),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(aggregate(rows),indent=2),encoding='utf-8')
    flush()
    print('Evidence directory:', output)


if __name__=='__main__':
    main()
