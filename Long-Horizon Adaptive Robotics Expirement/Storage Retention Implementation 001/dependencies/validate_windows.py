"""Verify every selected diagnostic interval has complete retained RGB/depth pairs."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

def source(path):
    data=Path(path).read_bytes()
    return {'path':str(Path(path).resolve()),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def validate(required_path,windows_path):
    windows=json.loads(Path(windows_path).read_text())['windows']
    by_id={w['window_id']:w for w in windows}
    if len(by_id)!=len(windows):raise ValueError('Duplicate window identity')
    observed=defaultdict(lambda:defaultdict(set));files=defaultdict(set)
    opener=gzip.open if str(required_path).endswith('.gz') else open
    with opener(required_path,'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            relevant=[d for d in row['dependencies'] if d in by_id]
            if not relevant:continue
            name=Path(row['path']);kind='depth' if name.name.endswith('-depth.npz') else 'rgb'
            if kind=='rgb' and name.suffix!='.png':raise ValueError('Unexpected diagnostic artifact type')
            parts=name.as_posix().split('/');rid=parts[parts.index('attempts')+1]
            identities={(s['event_id'],s['capture_sim_time_s']) for s in row['source_identities'] if 'capture_sim_time_s' in s}
            if not identities:raise ValueError('Diagnostic frame lacks capture identity')
            for wid in relevant:
                w=by_id[wid]
                if rid!=w['run_id']:raise ValueError('Window/frame run identity mismatch')
                candidates={i for i in identities if w['start_capture_sim_time_s']-1e-9<=i[1]<=w['end_capture_sim_time_s']+1e-9}
                if len(candidates)!=1:raise ValueError('Window frame lacks unique in-window observation identity')
                identity=next(iter(candidates))
                if kind in observed[wid][identity]:raise ValueError('Duplicate artifact for window observation')
                observed[wid][identity].add(kind);files[wid].add(row['path'])
    checked=[]
    for wid,w in by_id.items():
        entries=observed[wid]
        if not entries or len(entries)!=w['selected_observations']:raise ValueError('Window observation count mismatch: '+wid)
        if any(pair!={'rgb','depth'} for pair in entries.values()):raise ValueError('Incomplete RGB/depth window: '+wid)
        if len(files[wid])!=2*w['selected_observations']:raise ValueError('Window file count mismatch')
        times=[x[1] for x in entries]
        if min(times)!=w['first_available_capture_sim_time_s'] or max(times)!=w['last_available_capture_sim_time_s']:raise ValueError('Window capture bounds mismatch')
        checked.append({'window_id':wid,'observations':len(entries),'files':len(files[wid])})
    return {'format':'diagnostic-window-completeness-1','status':'passed','required':source(required_path),'windows':source(windows_path),
            'window_count':len(windows),'window_checks':checked,'scope':'Every original saved observation declared by the authenticated extraction has both retained RGB/depth artifacts and exact in-window capture identity; missing nominal captures are not filled.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--required',type=Path,required=True);p.add_argument('--windows',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=validate(a.required,a.windows)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='window_checks'}))
