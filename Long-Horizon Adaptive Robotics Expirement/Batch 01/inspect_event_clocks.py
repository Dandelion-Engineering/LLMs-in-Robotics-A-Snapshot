"""Queue-only bounded diagnosis of explicitly named development event streams."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

RUNTIME=Path(__file__).resolve().parents[1]/'Runtime'
sys.path.insert(0,str(RUNTIME))
from release_runner import queued_job

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    job=queued_job(expected_script=__file__)
    if not 1<=len(args.run_id)<=12 or len(set(args.run_id))!=len(args.run_id):raise ValueError('One to twelve distinct explicit runs')
    if args.output.exists():raise ValueError('Fresh diagnostic output required')
    records=[]
    for run_id in args.run_id:
        if not run_id.startswith('B01-dev-') or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in run_id):raise ValueError('Invalid development run ID')
        path=RUNTIME.parent/'Evidence'/'raw'/run_id/'events.jsonl'
        digest=hashlib.sha256();previous=None;violations=[];list_events=[];count=0
        with path.open('rb') as stream:
            for raw in stream:
                digest.update(raw);event=json.loads(raw);count+=1
                stamp={k:event.get(k) for k in ('event_id','event_type','source','sim_time_s','wall_elapsed_s')}
                if previous:
                    reversed_clocks={key:{'previous':previous[key],'current':stamp[key]} for key in ('sim_time_s','wall_elapsed_s')
                                     if isinstance(stamp[key],(int,float)) and isinstance(previous[key],(int,float)) and stamp[key]<previous[key]}
                    if reversed_clocks:
                        violations.append({'previous':previous,'current':stamp,'clocks':reversed_clocks})
                if not isinstance(event.get('payload'),dict):list_events.append({**stamp,'payload_type':type(event.get('payload')).__name__})
                previous=stamp
        records.append({'run_id':run_id,'source_path':str(path),'source_sha256':digest.hexdigest(),'event_count':count,
                        'backward_clocks':violations,'non_object_payloads':list_events})
    output={'queue_job_id':job['id'],'scope':'diagnosis only; original event order, clocks and bytes unchanged','runs':records}
    with args.output.open('x',encoding='utf-8') as stream:json.dump(output,stream,indent=2);stream.write('\n')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
