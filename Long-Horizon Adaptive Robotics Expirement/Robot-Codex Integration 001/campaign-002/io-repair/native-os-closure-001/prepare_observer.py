"""Make fresh external control metadata immediately before next-session UAC.

No capture or model launch. The authentication key stays outside Git and the
model namespace. This is single-use; existing footprints require reconciliation.
"""
import json
from pathlib import Path
import secrets
import time
import uuid
import collect_window
import prepare as p
import trace_control as t


def main():
    p.verify_checks()
    p.common.validate(p.common.MANIFEST,p.common.SNAPSHOT)
    p.common.output_paths(p.common.EVIDENCE,p.common.HOST,p.common.WORKSPACE)
    binding=p.common.ROOT/'observer-preparation.json'
    for path in (binding,t.CONTROL,p.common.RECORDS,p.common.ROOT/'observer-elevation-intent.json'):
        if path.exists(): raise FileExistsError('Single-use footprint already exists: '+str(path))
    value={'run':t.RUN,'revision':t.REVISION,'control_root':str(t.CONTROL),'session':t.SESSION,
        'guid':str(uuid.uuid4()),'key':secrets.token_hex(32),
        'created_filetime':time.time_ns()//100+116444736000000000,
        'sources':{str(path):p.common.sha(path) for path in collect_window.source_paths()}}
    t.CONTROL.mkdir()
    t.save(t.CONTROL/'config.json',value)
    sources=collect_window.source_paths()+[p.HERE/'launch_observer.ps1',p.HERE/'prepare_observer.py']
    t.save(binding,{'run':t.RUN,'revision':t.REVISION,'control_root':str(t.CONTROL),
        'config_sha256':p.common.sha(t.CONTROL/'config.json'),'snapshot':p.identity(p.common.SNAPSHOT),
        'sources':{str(path):p.common.sha(path) for path in sources},'model_calls':0,'trace_starts':0})
    print(json.dumps({'prepared':True,'binding':str(binding),'config_sha256':p.common.sha(t.CONTROL/'config.json'),
        'next':'One-shot launch_observer.ps1 when Randy is at the desktop; no automatic elevation here'}))


if __name__=='__main__':main()
