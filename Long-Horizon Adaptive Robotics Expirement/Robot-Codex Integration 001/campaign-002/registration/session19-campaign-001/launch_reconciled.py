"""Launch only the exact sealed coordinator after successful metadata reconciliation."""
from datetime import datetime,timezone
from pathlib import Path
import json
import subprocess
import control as base

HERE=Path(__file__).resolve().parent
OUT=HERE/'reconciled-launch-001'

def main():
    official=base.successful('20260930T213830123415Z-7c2c1e26')
    proof=base.read(HERE/'registration-reconciliation-001/verified.json')
    assert proof['registered']==20 and proof['existing_certificate_and_registration_verifiers_passed']is True
    assert proof['sources_unchanged']is True and proof['registration']==base.identity(base.REG)
    assert proof['certificate']==base.identity(base.CERT) and base.identity(base.CERT)['sha256']==base.DIGEST
    certificate=base.read(base.CERT)
    coordinator=base.C/'run_campaign.py'
    assert certificate['artifacts']['campaign_coordinator']==base.identity(coordinator)
    assert not OUT.exists()
    assert all(not (base.C/'execution'/a['run_id']).exists() and not any(Path(a[k]).exists() for k in ['workspace','evidence','host_evidence']) for a in certificate['attempts'])
    OUT.mkdir()
    argv=base.py(coordinator,'--registration',base.REG)
    base.save(OUT/'launch-intent.json',{'argv':argv,'cwd':str(base.REPO),'runner':base.identity(__file__),
        'coordinator':base.identity(coordinator),'certificate':base.identity(base.CERT),'registration':base.identity(base.REG),
        'reconciliation_job':official,'reconciliation_proof':base.identity(HERE/'registration-reconciliation-001/verified.json'),
        'created_at':datetime.now(timezone.utc).isoformat(),'scope':'Existing authorized fixed twenty-slot campaign; unchanged sealed operator and stopping rules.'})
    with (OUT/'coordinator.stdout').open('x',encoding='utf-8') as out,(OUT/'coordinator.stderr').open('x',encoding='utf-8') as err:
        process=subprocess.Popen(argv,cwd=base.REPO,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        base.save(OUT/'process.json',{'pid':process.pid,'argv':argv,'launched_at':datetime.now(timezone.utc).isoformat(),'launch_intent':base.identity(OUT/'launch-intent.json')})
        print(json.dumps({'coordinator_pid':process.pid,'state':'running'}),flush=True)
        code=process.wait()
    base.save(OUT/'completion.json',{'exit_code':code,'ended_at':datetime.now(timezone.utc).isoformat(),
        'stdout':base.identity(OUT/'coordinator.stdout'),'stderr':base.identity(OUT/'coordinator.stderr'),
        'launch_intent':base.identity(OUT/'launch-intent.json')})
    print(json.dumps({'state':'completed','exit_code':code}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
