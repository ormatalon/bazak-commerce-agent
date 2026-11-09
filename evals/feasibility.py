"""Final-stage diagnostic of relative relevance; not human-labeled release scoring."""

import json
from pathlib import Path

from dotenv import load_dotenv

from app.catalog import load_catalog
from app.config import ROOT, RetrievalConfig
from app.embeddings import LocalEmbedder
from app.index import ProductIndex
from app.schemas import Direction, SearchSpec
from app.search import rank_all


def main():
    load_dotenv(ROOT/'.env')
    config=RetrievalConfig()
    index=ProductIndex(load_catalog(),LocalEmbedder(config),config)
    probes=[('gaming console',[]),('electric wheelchair',[]),('3D printer',[]),
            ('laptop',['laptops']),('perfume',['fragrances']),('מחשב נייד',['laptops'])]
    rows=[]
    for query,categories in probes:
        ranked=rank_all(SearchSpec(directions=[Direction(query=query,categories=categories)]),index)[0]
        accepted=[c for c in ranked if c.relevant]
        rows.append({'query':query,'categories':categories,'accepted_count':len(accepted),
                     'accepted':[c.model_dump(mode='json') for c in accepted[:3]],
                     'top':[c.model_dump(mode='json') for c in ranked[:3]]})
    path=ROOT/'evals/artifacts/feasibility.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'config_hash':config.fingerprint(),'index':index.identity,
                               'status':'diagnostic probes; not reviewed ground truth','probes':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    for row in rows:
        print(json.dumps({'query':row['query'],'accepted_count':row['accepted_count'],
                          'accepted_titles':[c['product']['title'] for c in row['accepted']]},ensure_ascii=True))
    print('Evidence:',path)


if __name__=='__main__':
    main()
