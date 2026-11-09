"""Re-score recorded V2 outputs without model calls or overwriting original evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from app.schemas import Product, TurnResult
from evals.run_evals import report
from evals.scoring import aggregate, score_turn


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    evidence=args.evidence
    metadata=json.loads((evidence/'metadata.json').read_text(encoding='utf-8'))
    catalog=[Product.model_validate(p) for p in json.loads((evidence/'catalog.json').read_text(encoding='utf-8'))['products']]
    rows=[json.loads(s) for s in (evidence/'cases.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    if len(rows)!=metadata['case_count']:
        raise SystemExit('Refusing to publish a partial replay as a complete evaluation.')
    for row in rows:
        if row['error']:
            continue
        for turn in row['turns']:
            result=TurnResult.model_validate(turn['result'])
            turn['metrics']=score_turn(result,row['case'],catalog)
        row['metrics']=dict(row['turns'][-1]['metrics'])
        for key in ('catalog_card_fidelity','no_duplicates','no_known_prompt_leak','no_unshown_catalog_titles',
                    'no_unsupported_dollar_amounts','exact_numeric_compliance','parsed_exclusion_rule_compliance','alternative_disclosure'):
            values=[turn['metrics'][key] for turn in row['turns'] if turn['metrics'].get(key) is not None]
            row['metrics'][key]=min(values) if values else None
        overlay=row.get('v2_expectation')
        if overlay:
            scores=score_turn(result,{**row['case'],**overlay},catalog)
            prefix='v2_' if overlay.get('review_status')=='reviewed' else 'v2_draft_'
            row['metrics'].update({prefix+k:v for k,v in scores.items() if k in ('intent_accuracy','mode_accuracy','legacy_category_accuracy')})
        row['metrics']['execution_success']=1.0
    output=evidence/'rescored'
    output.mkdir(exist_ok=False)
    metadata['prediction_source']=str(evidence.resolve())
    metadata['scorer_git_sha']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    metadata['scorer_sha256']=hashlib.sha256(Path(__file__).with_name('scoring.py').read_bytes()).hexdigest()
    (output/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(evidence/'catalog.json',output/'catalog.json')
    (output/'cases.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(aggregate(rows),indent=2)+'\n',encoding='utf-8')
    (output/'report.md').write_text(report(rows,metadata),encoding='utf-8')
    print('Rescored evidence:',output)


if __name__=='__main__':
    main()
