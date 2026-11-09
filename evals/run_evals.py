"""Reproducible full-conversation replay. Outputs local evidence before upload."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from time import perf_counter

from dotenv import load_dotenv

from app.catalog import load_catalog, load_categories
from app.config import ROOT, RetrievalConfig, catalog_hash
from app.embeddings import LocalEmbedder
from app.index import ProductIndex
from app.llm import openai_llm
from app.observability import flush
from app.pipeline import run_turn
from app.schemas import ConversationState
from evals.datasets import load_cases, load_overlay
from evals.scoring import aggregate, score_turn


def run_case(case, catalog, categories, index, llm=openai_llm, overlay=None) -> dict:
    started=perf_counter()
    state=ConversationState()
    turns=[]
    try:
        for number,message in enumerate(case['turns']):
            result=run_turn(message,state,catalog,categories,llm,index,case['key'],traffic='evaluation')
            state=result.state
            turn={'turn':number,'result':result.model_dump(mode='json')}
            turn['metrics']=score_turn(result,case,catalog)
            turns.append(turn)
        metrics=dict(turns[-1]['metrics'])
        invariant_keys=['catalog_card_fidelity','no_duplicates','no_known_prompt_leak','no_unshown_catalog_titles',
                        'no_unsupported_dollar_amounts','exact_numeric_compliance','parsed_exclusion_rule_compliance','alternative_disclosure']
        for key in invariant_keys:
            values=[t['metrics'][key] for t in turns if t['metrics'].get(key) is not None]
            metrics[key]=min(values) if values else None
        if overlay:
            draft=score_turn(result,{**case,**overlay},catalog)
            prefix='v2_' if overlay.get('review_status')=='reviewed' else 'v2_draft_'
            metrics.update({prefix+k:v for k,v in draft.items() if k in ('intent_accuracy','mode_accuracy','legacy_category_accuracy')})
        return {'key':case['key'],'source':case['source'],'difficulty':case.get('difficulty'),
                'case':case,'v2_expectation':overlay,'turns':turns,'metrics':metrics,'error':None,
                'duration_ms':(perf_counter()-started)*1000}
    except Exception as error:
        # Keep failures in denominator. Never persist provider exception text/secrets.
        return {'key':case['key'],'source':case['source'],'difficulty':case.get('difficulty'),
                'case':case,'turns':turns,'metrics':{'execution_success':0.0},
                'error':type(error).__name__,'duration_ms':(perf_counter()-started)*1000}


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
            lines.append('ERROR: '+row['error']); continue
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
    args=parser.parse_args()
    if not args.live:
        parser.error('Use --live to enable provider calls; unit checks use pytest.')
    load_dotenv(ROOT/'.env')
    cases=[c for c in load_cases() if args.source=='all' or c['source']==args.source]
    overlays=load_overlay()
    if args.limit: cases=cases[:args.limit]
    config=RetrievalConfig(**json.loads(args.config.read_text())) if args.config else RetrievalConfig()
    catalog=load_catalog(); categories=load_categories()
    index=ProductIndex(catalog,LocalEmbedder(config),config)
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=args.output or ROOT/'evals'/'artifacts'/timestamp
    output.mkdir(parents=True,exist_ok=False)
    metadata={'timestamp_utc':timestamp,'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'catalog_hash':catalog_hash(catalog),'config':asdict(config),
              'source_hashes':{c['source']:c['source_hash'] for c in cases},
              'labels_status':'draft; semantic release gates not certified',
              'overlay_cases':len(overlays),'reviewed_overlay_cases':sum(o.get('review_status')=='reviewed' for o in overlays.values()),
              'case_count':len(cases),'model':'gpt-6-luna','workers':args.workers,'sdk_retries':1}
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    (output/'catalog.json').write_text(json.dumps({'products':[p.model_dump(mode='json') for p in catalog],
                                                  'categories':categories},ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[]
    with (output/'cases.jsonl').open('w',encoding='utf-8') as handle, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_case,c,catalog,categories,index,overlay=overlays.get(c['key'])):c['key'] for c in cases}
        for future in as_completed(futures):
            row=future.result()
            row['metrics']['execution_success']=float(not row['error'])
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
