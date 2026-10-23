"""Bind streamed current source hashes back to preserved diagnostic provenance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
EXP=ROOT/'Long-Horizon Adaptive Robotics Expirement'
INDEX=EXP/'Evidence/derived/evaluation-r4-administrative005-001/index.json'
def ref(path,raw):return {'path':str(path.resolve()),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--decisions',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.decisions.read_bytes();decision=json.loads(raw);source_hashes=decision['sources']
    index_raw=INDEX.read_bytes();index=json.loads(index_raw);checked=[];unavailable=[]
    for row in index['runs']:
        d=row['derived']['diagnostics']
        if d['status']!='completed':
            unavailable.append({'run_id':row['run_id'],'status':d['status'],'reason':d.get('reason')});continue
        bound=d['artifact'];path=Path(bound['path']);data=path.read_bytes();identity=ref(path,data)
        if identity['sha256']!=bound['sha256'] or identity['bytes']!=bound['bytes']:raise ValueError('Prior derivative changed '+str(path))
        diagnostics=json.loads(data);matches=[]
        for name,s in diagnostics['sources'].items():
            key=Path(s['path']).resolve().relative_to(ROOT).as_posix()
            if key not in source_hashes:continue
            current=source_hashes[key]
            if current['sha256']!=s['sha256'] or current['bytes']!=s['bytes']:raise ValueError('Current source differs from original diagnostics: '+key)
            matches.append(name)
        if 'events.jsonl' not in matches:raise ValueError('Missing streamed event provenance '+row['run_id'])
        checked.append({'run_id':row['run_id'],'prior_diagnostic':identity,'source_names_compared':matches})
    if len(checked)!=263 or len(unavailable)!=1:raise ValueError('Expected263 terminal and1 administrative unavailable disposition')
    report={'format':'r4-retention-source-reconciliation-1','status':'passed','extraction':ref(a.decisions,raw),'derivative_index':ref(INDEX,index_raw),
            'terminal_event_streams_equal_prior_diagnostics':len(checked),'checked':checked,'unavailable':unavailable,
            'scope':'Current event hashes were measured during the official extraction job. Every terminal event stream matches its authenticated original diagnostic source hash; also compares available result and selected top-contact motion hashes. Administrative partial evidence retains its new extraction identity without inventing a prior completed derivative.'}
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ('checked','unavailable')}))
if __name__=='__main__':main()
