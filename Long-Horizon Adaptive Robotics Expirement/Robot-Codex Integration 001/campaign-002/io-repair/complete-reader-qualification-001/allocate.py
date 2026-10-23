"""Declare absent V31 identities only after fresh official full-check success."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import build
import control

c=control.c;HERE=Path(__file__).resolve().parent

def main():
    submitted=c.read(HERE/'checks-submit-002.json');job_id=submitted['id']
    job=c.admission.base.queue_gate(c.official(job_id),job_id)
    c.require(job['argv']==submitted['argv'],'Official check command differs')
    c.save_exact(HERE/'checks-terminal-002.json',job)
    receipt=c.read(control.LINEAGE_CHECKS);c.require(receipt['passed'] is True,'Full lineage failed')
    old=c.read(control.IO/'graceful-process-qualification-001/allocation-absence-001.json')
    paths=[Path(build.changed(p).replace('graceful-process-qualification-001','complete-reader-qualification-001')) for p in old['absent_paths']]
    revisions=['RCI001-C02-dev-'+str(n).zfill(3) for n in (103,104,105,106)]
    runs=['RCI001-C02-'+name for name in ('raw-preflight-021','transport-probe-024','host-probe-031',
        'native-030','boundary-031','smoke-029','pilot-stock-028','pilot-home-028')]
    # Include both app-virtualized and physical conventional LOCALAPPDATA paths.
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
    value=c.read(control.IO/'graceful-process-qualification-001/qualification-declaration.json')
    value.update(created_at=datetime.now(timezone.utc).isoformat(),
        purpose='Qualify complete native process notifications and finite literal read recognition while preserving the graceful process-drain method and all unchanged model, recovery, timing, evidence, isolation and retirement requirements.',
        anchor_revision=control.REV,repair_checks=control.CHECKS.name,
        coordinator=c.identity(control.Q/'run_final_qualification_v31.py'),
        development_checks=c.identity(control.CHECKS/'test-execution.json'),lineage_checks=c.identity(control.LINEAGE_CHECKS),
        development_source_state=c.identity(control.SOURCE_STATE),allocation_absence=c.identity(HERE/'allocation-absence-001.json'),
        prerequisites=runs[:3],stages=[[name,kind,rev,seed] for (name,kind,seed),rev in zip(c.STAGE_IDENTITIES,[revisions[1],revisions[2],revisions[3],revisions[3],revisions[3]])],
        complete_reader_method=c.identity(control.IO/'COMPLETE_PROCESS_AND_LITERAL_READS_V1.md'),
        complete_reader_diagnostic=c.identity(control.IO/'complete-process-readers-001/diagnostic-replay-001.json'),
        development_official_queue=c.identity(HERE/'checks-terminal-002.json'))
    value['preservation'] += (' V30 is permanently stopped at original Smoke028/dev10259/62 invalid/unknown despite official succeeded/int0. Both Pilot027 were unstarted. The later three-gap diagnostic reader replay does not promote that result. New V31 must pass all fresh prerequisites and five final stages before scoring; zero Campaign002 scored starts/registrations exist at declaration.')
    c.save(control.DECLARATION,value);control.bound_declaration()
    print(json.dumps({'declared':c.identity(control.DECLARATION),'absent_paths':len(paths),'absent_ids':len(revisions)+len(runs)}))

if __name__=='__main__':main()
