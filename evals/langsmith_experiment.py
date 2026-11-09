"""Upload an immutable local replay snapshot and evaluate its recorded outputs.

This does not call a model again: it preserves the exact outputs in the local report.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import load_dotenv
from langsmith.evaluation import evaluate

from app.config import ROOT
from app.observability import get_client, redact


def local_metrics(run, example):
    feedback=[{"key": key, "score": value} for key,value in run.outputs.get('metrics',{}).items()
              if isinstance(value,(int,float))]
    duration=run.outputs.get('measured_duration_ms')
    if duration is not None:
        feedback.append({"key":"measured_duration_ms","score":duration})
    return {"results":feedback}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path,help='Directory containing cases.jsonl and metadata.json')
    parser.add_argument('--dataset-id',help='Reuse an immutable snapshot with identical case identities and input turns for comparison.')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    client=get_client()
    if client is None:
        raise SystemExit('Configure LANGSMITH_API_KEY in .env first.')
    rows=[json.loads(line) for line in (args.evidence/'cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    metadata=json.loads((args.evidence/'metadata.json').read_text(encoding='utf-8'))
    by_key={row['key']:row for row in rows}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    implementation=metadata.get('implementation','v2')
    if args.dataset_id:
        dataset=client.read_dataset(dataset_id=args.dataset_id)
    else:
        dataset=client.create_dataset(f"bazak-{implementation}-{metadata['git_sha'][:8]}-{stamp}",
            description='Immutable source-case replay snapshot; labels and outputs retain their review status.',
            metadata=redact(metadata))
        client.create_examples(dataset_id=dataset.id,examples=[{
            'inputs':redact({'key':row['key'],'turns':row['case']['turns']}),
            'outputs':redact({'legacy_expectation':row['case'],'v2_expectation':row.get('v2_expectation')}),
            'metadata':{'case_key':row['key'],'source':row['source'],'difficulty':row.get('difficulty')}
        } for row in rows])
    uploaded=list(client.list_examples(dataset_id=dataset.id))
    if len(uploaded)!=len(rows) or {e.inputs['key'] for e in uploaded}!=set(by_key):
        raise RuntimeError('Uploaded example identities/counts do not match local evidence')
    if any(e.inputs['turns']!=redact(by_key[e.inputs['key']]['case']['turns']) for e in uploaded):
        raise RuntimeError('Snapshot input turns differ from local evidence; no comparison experiment created')

    def recorded_output(inputs):
        row=by_key[inputs['key']]
        return redact({'metrics':row['metrics'],'turns':row['turns'],'error':row['error'],
                       'measured_duration_ms':row.get('duration_ms'),
                       'source_case_key':row['key'],'prediction_origin':'recorded local replay'})

    results=evaluate(recorded_output,data=dataset.id,client=client,evaluators=[local_metrics],
        experiment_prefix=f"{implementation}-{metadata['git_sha'][:8]}",
        metadata={**metadata,'prediction_origin':'recorded local replay; no additional model calls'},
        max_concurrency=4,blocking=True)
    list(results)
    client.flush()
    experiment=client.read_project(project_name=results.experiment_name)
    info={'dataset_id':str(dataset.id),'dataset_url':dataset.url,
          'experiment_name':results.experiment_name,'experiment_id':str(experiment.id),
          'experiment_url':dataset.url+'/compare?selectedSessions='+str(experiment.id),
          'example_count':len(uploaded)}
    (args.evidence/'langsmith.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(info,indent=2))


if __name__=='__main__':
    main()
