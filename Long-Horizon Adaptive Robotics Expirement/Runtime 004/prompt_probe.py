"""Queued live-model adapter probe over one retained public observation.

No simulator is started and no action is executed. Admissible output is only an
interface diagnostic, never successful tending or an architecture result.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time

from candidates import Candidate
from model_runtime import LocalModel


def probe(source, output, minimum_sim_time=0.0):
    source=Path(source);output=Path(output)
    if output.exists():raise FileExistsError(output)
    packet=None; prior_packets=[]
    with (source/'events.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            event=json.loads(line)
            message=event.get('payload',{}).get('message',{})
            if event['event_type']=='candidate_input' and message.get('type')=='step':
                packet=message['packet'];source_event=event['event_id']
                if packet['sim_time'] >= minimum_sim_time:break
                prior_packets.append(packet)
    if packet is None:raise ValueError('No recorded public step packet')
    rows=[]
    with LocalModel() as model, tempfile.TemporaryDirectory(prefix='robot-public-packet-probe-') as tmp:
        for kind in ('A1','A2','A3'):
            candidate=Candidate(kind,Path(tmp)/kind,True)
            for prior in prior_packets:candidate._ingest(prior)
            events=[];calls=[];admitted=None;start=time.perf_counter()
            for turn in range(8):
                request=candidate.step(packet)
                events.extend(candidate.drain_events())
                if request['type']=='model':
                    if len(calls)>=3:break
                    reply=model.complete(request['messages'],request['schema'],max_tokens=1024,seed=19)
                    calls.append({'request':request,'reply':reply})
                    candidate.accept_model(reply['text']);events.extend(candidate.drain_events())
                elif request['type']=='action':
                    admitted=request['action'];break
                else:break
            rows.append({'kind':kind,'wall_duration_s':time.perf_counter()-start,'model_calls':calls,
                         'candidate_events':events,'proposed_action':admitted,'executed':False})
        identity=model.identity
    result={'scope':'Actual local-model calls over a retained public packet; no physical actions or task outcomes',
            'source_run':source.name,'source_event_id':source_event,'source_public_packet':packet,
            'prior_public_packets_ingested':len(prior_packets),
            'history_scope':'Only preceding recorded public step packets; no historical candidate actions or private truth replayed',
            'candidate_sha256':hashlib.sha256(Path(__file__).with_name('candidates.py').read_bytes()).hexdigest(),
            'model_identity':identity,'rows':rows}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'output':str(output),'scope':result['scope'],'proposals':[{'kind':r['kind'],'action':r['proposed_action'],'calls':len(r['model_calls'])} for r in rows]},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--minimum-sim-time',type=float,default=0.0)
    args=p.parse_args();probe(args.source_run,args.output,args.minimum_sim_time)
