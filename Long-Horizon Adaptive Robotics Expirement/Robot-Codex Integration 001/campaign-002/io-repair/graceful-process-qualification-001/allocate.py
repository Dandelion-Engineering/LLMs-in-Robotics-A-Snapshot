"""Authenticate development results and allocate absent fresh identities once."""
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import control

c=control.c
HERE=Path(__file__).resolve().parent

def main():
    job_id='20260930T181434414677Z-da8cdef5'
    job=c.admission.base.queue_gate(c.official(job_id),job_id)
    c.save_exact(HERE/'lineage-terminal-002.json',job)
    receipt=c.read(control.LINEAGE_CHECKS)
    c.require(receipt['passed'] is True,'Lineage checks failed')
    pairs={'dev-093':'dev-099','dev-094':'dev-100','dev-095':'dev-101','dev-096':'dev-102',
        'raw-preflight-019':'raw-preflight-020','transport-probe-022':'transport-probe-023',
        'host-probe-029':'host-probe-030','native-028':'native-029','boundary-029':'boundary-030',
        'smoke-027':'smoke-028','pilot-stock-026':'pilot-stock-027','pilot-home-026':'pilot-home-027',
        'final-qualification-029':'final-qualification-030'}
    def changed(value):return re.sub('|'.join(re.escape(k) for k in pairs),lambda m:pairs[m.group()],value)
    old=c.read(control.IO/'v29-allocation-absence-001.json')
    bookkeeping={'v29-readiness-preflight-001.json':HERE/'readiness-preflight-001.json',
                 'v29-qualification-declaration.json':control.DECLARATION}
    paths=[bookkeeping.get(Path(p).name,Path(changed(p))) for p in old['absent_paths']]
    paths += [control.IO/'raw-preflight-020',control.IO/'transport-probe-023',control.Q/'final-qualification-030-readiness.json']
    paths=sorted(set(paths))
    c.require(not any(p.exists() for p in paths),'Prospective allocation path already exists')
    revisions=['RCI001-C02-dev-'+str(n).zfill(3) for n in (99,100,101,102)]
    runs=['RCI001-C02-'+name for name in ('raw-preflight-020','transport-probe-023','host-probe-030',
          'native-029','boundary-030','smoke-028','pilot-stock-027','pilot-home-027')]
    ids=set()
    stores={}
    for name in ('architectures','revisions','runs','results','notes'):
        path=c.MAP/(name+'.jsonl')
        stores[name]=c.identity(path)
        ids.update(json.loads(line)['id'] for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
    c.require(not ids.intersection([*revisions,*runs]),'Prospective identity already registered')
    absence={'schema':'campaign002-prospective-allocation-absence-1','checked_at':datetime.now(timezone.utc).isoformat(),
        'absent_paths':[str(p.resolve()) for p in paths],'absent_ids':[*revisions,*runs],'canonical_stores':stores}
    c.save(HERE/'allocation-absence-001.json',absence)
    value=c.read(control.IO/'v29-qualification-declaration.json')
    value.update(created_at=datetime.now(timezone.utc).isoformat(),
        purpose='Qualify prospective protocol-quiescence, ordinary process stdin closure and genuine complete transport drainage with normal native exit within the original deadline and all existing policy, timing, isolation, byte and retirement gates.',
        anchor_revision=control.REV,repair_checks=control.CHECKS.name,
        coordinator=c.identity(control.Q/'run_final_qualification_v30.py'),
        development_checks=c.identity(control.CHECKS/'test-execution.json'),lineage_checks=c.identity(control.LINEAGE_CHECKS),
        development_source_state=c.identity(control.SOURCE_STATE),allocation_absence=c.identity(HERE/'allocation-absence-001.json'),
        prerequisites=runs[:3],stages=[[name,kind,rev,seed] for (name,kind,seed),rev in zip(c.STAGE_IDENTITIES,[revisions[1],revisions[2],revisions[3],revisions[3],revisions[3]])],
        graceful_process_method=c.identity(control.IO/'GRACEFUL_PROCESS_DRAIN_V1.md'),
        graceful_process_diagnostic=c.identity(control.IO/'graceful-process-assessment-001/transport-proof.json'),
        graceful_process_diagnostic_terminal=c.identity(control.IO/'graceful-process-assessment-001/terminal-result.json'),
        development_official_queue=c.identity(HERE/'lineage-terminal-002.json'))
    value['preservation'] += (' V29 is permanently stopped at Smoke027/dev096. Diagnostic005 remains failed/invalid and original Smoke02710053 causality remains unknown. Diagnostic006 is one valid bounded infrastructure test with unknown task outcome. New V30 alone may qualify the promoted method. No earlier passing qualifier is substituted; Campaign001 remains frozen and Campaign002 has zero scored starts at declaration.')
    c.save(control.DECLARATION,value)
    control.bound_declaration()
    print(json.dumps({'declared':c.identity(control.DECLARATION),'absent_paths':len(paths),'absent_ids':len(revisions)+len(runs),'lineage_passed':receipt['passed']}))

if __name__=='__main__':main()
