"""Declare absent V32 identities after authentic full regression success."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import build
import control

c=control.c;HERE=Path(__file__).resolve().parent

def main():
    submitted=c.read(HERE/'checks-submit-001.json');job_id=submitted['id']
    job=c.admission.base.queue_gate(c.official(job_id),job_id)
    c.require(job['argv']==submitted['argv'],'Official check command differs')
    c.save_exact(HERE/'checks-terminal-001.json',job)
    c.require(c.read(control.LINEAGE_CHECKS)['passed'] is True,'Full lineage failed')
    previous=control.IO/'complete-reader-qualification-001'
    old=c.read(previous/'allocation-absence-001.json')
    paths=[Path(build.changed(p).replace('complete-reader-qualification-001','boundary-import-qualification-001')) for p in old['absent_paths']]
    revisions=['RCI001-C02-dev-'+str(n).zfill(3) for n in (107,108,109,110)]
    runs=['RCI001-C02-'+name for name in ('raw-preflight-022','transport-probe-025','host-probe-032',
        'native-031','boundary-032','smoke-030','pilot-stock-029','pilot-home-029')]
    for base in {Path(os.environ['LOCALAPPDATA']),Path.home()/'AppData/Local'}:
        paths += [base/'RobotCodex/Campaign002/qualification'/name for name in runs]
    paths=sorted(set(p.resolve() for p in paths))
    existing=[str(p) for p in paths if p.exists()]
    c.require(not existing,'Prospective path already exists: '+str(existing))
    ids=set();stores={}
    for name in ('architectures','revisions','runs','results','notes'):
        p=c.MAP/(name+'.jsonl');stores[name]=c.identity(p)
        ids.update(json.loads(line)['id'] for line in p.read_text(encoding='utf-8').splitlines() if line.strip())
    c.require(not ids.intersection([*revisions,*runs]),'Prospective identity already registered')
    c.save(HERE/'allocation-absence-001.json',{'schema':'campaign002-prospective-allocation-absence-1',
        'checked_at':datetime.now(timezone.utc).isoformat(),'absent_paths':[str(p) for p in paths],
        'absent_ids':[*revisions,*runs],'canonical_stores':stores})
    value=c.read(previous/'qualification-declaration.json')
    value.update(created_at=datetime.now(timezone.utc).isoformat(),
        purpose='Qualify the standalone boundary assessment import fix; all protocol, reader, drainage, model, recovery, timing, evidence, isolation and retirement requirements remain unchanged.',
        anchor_revision=control.REV,repair_checks=control.CHECKS.name,
        coordinator=c.identity(control.Q/'run_final_qualification_v32.py'),
        development_checks=c.identity(control.CHECKS/'test-execution.json'),lineage_checks=c.identity(control.LINEAGE_CHECKS),
        development_source_state=c.identity(control.SOURCE_STATE),allocation_absence=c.identity(HERE/'allocation-absence-001.json'),
        prerequisites=runs[:3],stages=[[name,kind,rev,seed] for (name,kind,seed),rev in zip(c.STAGE_IDENTITIES,[revisions[1],revisions[2],revisions[3],revisions[3],revisions[3]])],
        development_official_queue=c.identity(HERE/'checks-terminal-001.json'),
        boundary_import_diagnosis=c.identity(control.IO/'boundary031-diagnosis-001/terminal-result.json'),
        boundary_import_cold_before=c.identity(HERE/'cold-before.json'),
        boundary_import_cold_after=c.identity(HERE/'cold-after.json'))
    value['preservation'] += (' V31 is permanently stopped after Native03066/66 and Boundary031 failed/int1 invalid/unknown from missing sibling import. Smoke029 and bothPilot028 unstarted. V32 must pass every fresh stage; prior successes cannot substitute. No scored registration/start exists.')
    c.save(control.DECLARATION,value);control.bound_declaration()
    print(json.dumps({'declared':c.identity(control.DECLARATION),'absent_paths':len(paths),'absent_ids':len(revisions)+len(runs)}))

if __name__=='__main__':main()
