"""Write a fresh exact smoke or pilot qualification manifest; never launch."""
import argparse
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
RCI=CAMPAIGN.parent
REPO=RCI.parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['smoke','stock','home'],required=True)
    p.add_argument('--revision',required=True);p.add_argument('--run-id',required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.kind=='smoke':source=RCI/'readiness-session-10/records/smoke-002-manifest.json'
    else:source=RCI/('campaign-001/predeclared-v1/RCI001-C01-'+a.kind+'-01.json')
    value=json.loads(source.read_text(encoding='utf-8'))
    value.update(run_id=a.run_id,framework_revision=a.revision,noise_seed=a.seed,prior_attempt=None,
                 qualification_stage='campaign002-'+a.kind+'-qualification',outer_campaign_protocol='RCI001-Campaign002-qualification-v1')
    value['runtime_workspace']=str(Path(os.environ['LOCALAPPDATA'])/'RobotCodex'/'Campaign002'/'qualification'/a.run_id)
    sources=(list((CAMPAIGN/'harness').glob('*.py'))+list((CAMPAIGN/'assessment').glob('*.py'))
             +list((RCI/'readiness-session-10/assessment').glob('*.py'))+[HERE/'native_suite.py',
                 CAMPAIGN/'transport-repair.md', CAMPAIGN/'timing-repair.md', HERE/'smoke-001-read-diagnosis.md'])
    value['runtime_input_files']=[p.relative_to(REPO).as_posix() for p in sorted(sources)]
    with a.output.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({'run_id':a.run_id,'kind':a.kind,'model_invocations':value['model_turns_max']}))

if __name__=='__main__':main()
