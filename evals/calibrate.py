"""Offline development-only threshold selection, requiring reviewed labels."""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np

from app.catalog import load_catalog
from app.config import ROOT, RetrievalConfig, catalog_hash
from app.embeddings import LocalEmbedder
from app.index import ProductIndex


def threshold_quality(result: dict) -> tuple:
    viable = result['precision'] >= 0.9 and result['recall'] > 0
    return viable, result['false_accepts'] == 0, result['f1'], result['precision']


def select_thresholds(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError('Cannot select thresholds from an empty label set')
    best=None
    for borderline in (0.5,1.0,1.5,2.0):
        for strong in (1.5,2.0,2.5,3.0):
            if strong<=borderline: continue
            tp=fp=fn=0
            for row in rows:
                accepted=row.get('informative',True) and (row['z_score']>=strong or (row['z_score']>=borderline and row.get('category_match',False)))
                positive=row['semantic_grade']==2
                tp+=accepted and positive; fp+=accepted and not positive; fn+=not accepted and positive
            precision=tp/(tp+fp) if tp+fp else 0
            recall=tp/(tp+fn) if tp+fn else 0
            f1=2*precision*recall/(precision+recall) if precision+recall else 0
            candidate={'borderline_threshold':borderline,'strong_threshold':strong,'precision':precision,'recall':recall,'f1':f1,'false_accepts':fp}
            if best is None or threshold_quality(candidate) > threshold_quality(best):
                best=candidate
    if best['precision'] < 0.9 or best['recall'] == 0:
        raise ValueError('No viable threshold configuration found; calibration was not certified.')
    return best


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',default=ROOT/'datasets/v2/relevance.jsonl',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    rows=[json.loads(s) for s in args.labels.read_text(encoding='utf-8').splitlines() if s.strip()]
    reviewed=[r for r in rows if r.get('review_status')=='reviewed' and r.get('split')=='development']
    if not reviewed or not any(r['semantic_grade']==0 for r in reviewed) or not any(r['semantic_grade']==2 for r in reviewed):
        raise SystemExit('Calibration requires human-reviewed development positives AND negatives. Drafts cannot certify thresholds.')
    catalog = load_catalog()
    fingerprint = catalog_hash(catalog)
    if any(row.get('catalog_hash') != fingerprint for row in reviewed):
        raise SystemExit('Reviewed labels must identify the exact current catalog_hash.')
    config=RetrievalConfig(); index=ProductIndex(catalog,LocalEmbedder(config),config)
    by_id={p.id:i for i,p in enumerate(index.products)}
    vectors={}
    for row in reviewed:
        query=row['query']
        if query not in vectors:
            s=index.similarities(index.embedder.encode([query],query=True)[0])
            informative = bool(s.std()>1e-8)
            vectors[query]=((s-s.mean())/s.std() if informative else np.zeros_like(s), informative)
        if row['product_id'] not in by_id:
            raise SystemExit('Reviewed label refers to a product absent from the catalog.')
        row['z_score']=float(vectors[query][0][by_id[row['product_id']]])
        row['informative']=vectors[query][1]
    try:
        choice=select_thresholds(reviewed)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    result=replace(config,strong_threshold=choice['strong_threshold'],borderline_threshold=choice['borderline_threshold'],calibrated=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(choice,indent=2))


if __name__=='__main__':
    main()
