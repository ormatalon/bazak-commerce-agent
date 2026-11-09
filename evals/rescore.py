"""Re-score recorded V2 outputs without model calls or overwriting original evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from app.schemas import Product
from evals.datasets import load_evidence
from evals.run_evals import report
from evals.scoring import aggregate, score_record


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--output',type=Path,help='New directory for rescored evidence; originals are never overwritten.')
    args=parser.parse_args()
    evidence=args.evidence
    metadata, rows = load_evidence(evidence)
    catalog=[Product.model_validate(p) for p in json.loads((evidence/'catalog.json').read_text(encoding='utf-8'))['products']]
    rows = [score_record(row, catalog) for row in rows]
    output = args.output or evidence/'rescored'
    output.mkdir(parents=True, exist_ok=False)
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
