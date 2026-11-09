"""Offline development-only threshold selection, requiring reviewed labels."""

import argparse
from dataclasses import asdict, replace
import json

import numpy as np

from app.catalog import load_catalog
from app.config import ROOT, RetrievalConfig
from app.embeddings import LocalEmbedder
from app.index import ProductIndex


def select_thresholds(rows: list[dict]) -> dict:
    best=None
    for borderline in (0.5,1.0,1.5,2.0):
        for strong in (1.5,2.0,2.5,3.0):
            if strong<=borderline: continue
            tp=fp=fn=0
            for row in rows:
                accepted=row['z_score']>=strong or (row['z_score']>=borderline and row.get('category_match',False))
                positive=row['semantic_grade']==2
                tp+=accepted and positive; fp+=accepted and not positive; fn+=not accepted and positive
            precision=tp/(tp+fp) if tp+fp else 0
            recall=tp/(tp+fn) if tp+fn else 0
            f1=2*precision*recall/(precision+recall) if precision+recall else 0
            candidate={'borderline_threshold':borderline,'strong_threshold':strong,'precision':precision,'recall':recall,'f1':f1,'false_accepts':fp}
            if best is None or (fp==0,f1,precision)>(best['false_accepts']==0,best['f1'],best['precision']):
                best=candidate
    return best


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',default=ROOT/'datasets/v2/relevance.jsonl',type=__import__('pathlib').Path)
    parser.add_argument('--output',required=True,type=__import__('pathlib').Path)
    args=parser.parse_args()
    rows=[json.loads(s) for s in args.labels.read_text(encoding='utf-8').splitlines() if s.strip()]
    reviewed=[r for r in rows if r.get('review_status')=='reviewed' and r.get('split')=='development']
    if not reviewed or not any(r['semantic_grade']==0 for r in reviewed) or not any(r['semantic_grade']==2 for r in reviewed):
        raise SystemExit('Calibration requires human-reviewed development positives AND negatives. Drafts cannot certify thresholds.')
    config=RetrievalConfig(); index=ProductIndex(load_catalog(),LocalEmbedder(config),config)
    by_id={p.id:i for i,p in enumerate(index.products)}
    vectors={}
    for row in reviewed:
        query=row['query']
        if query not in vectors:
            s=index.similarities(index.embedder.encode([query],query=True)[0])
            vectors[query]=(s-s.mean())/s.std() if s.std()>1e-8 else np.zeros_like(s)
        row['z_score']=float(vectors[query][by_id[row['product_id']]])
    choice=select_thresholds(reviewed)
    result=replace(config,strong_threshold=choice['strong_threshold'],borderline_threshold=choice['borderline_threshold'],calibrated=True)
    args.output.write_text(json.dumps(asdict(result),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(choice,indent=2))


if __name__=='__main__':
    main()
