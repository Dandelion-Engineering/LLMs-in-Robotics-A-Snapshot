"""Read-only source/archive comparison, retained once before the first launch."""
import hashlib
import json
from pathlib import Path
import zipfile
import control

c=control.c
HERE=Path(__file__).resolve().parent
PREFIX=control.C.relative_to(c.REPO).as_posix()+'/'
CHANGED={
    'harness/codehost_bridge_v3.py','harness/native_quiescence.py','harness/runtime.py',
    'harness/raw_event_preflight_v2.py','harness/test_native_shutdown_order.py','harness/test_native_owner_bootstrap.py',
    'assessment/canary_readback_proof.py','assessment/initial_read_composition.py','assessment/literal_read_segments.py',
    'assessment/raw_tool_result_reads.py','assessment/transport_integrity_v3.py',
    'qualification/prepare_native.py','qualification/test_prepare_native.py','qualification/host_probe.py',
    'qualification/boundary_suite_v3.py'}
ADDED={'harness/native_exit_drain.py','harness/test_native_exit_drain.py','assessment/pre_exit_integrity.py',
    'assessment/test_pre_exit_integrity.py','assessment/test_pre_exit_source_contract.py',
    'qualification/prepare_model_v21.py','qualification/test_prepare_model_v21.py',
    'io-repair/native-pre-exit-drain-001/DECLARATION.md'}

def binding(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    control.submission_gate()
    old_path=c.MAP/'releases/RCI001-C02-dev-092/snapshot.json'
    baseline_path=c.MAP/'releases/RCI001-wsl-010d/snapshot.json'
    old,new,baseline=c.read(old_path),c.read(control.SNAP),c.read(baseline_path)
    a,b=old['sources'],new['sources']
    c.require(len(baseline['sources'])==624,'Original source count changed')
    c.require(all(a.get(n)==b.get(n)==v==binding((c.REPO/n).read_bytes())
                  for n,v in baseline['sources'].items()),'Protected original624 changed')
    changed={n:{'before':a[n],'after':b[n]} for n in sorted(a.keys()&b.keys()) if a[n]!=b[n]}
    added={n:b[n] for n in sorted(b.keys()-a.keys())}
    c.require(set(changed)=={PREFIX+n for n in CHANGED},'Unexpected shared source change')
    c.require(set(added)=={PREFIX+n for n in ADDED},'Unexpected additional source')
    archives=[]
    for path,value,live in ((old_path,old,False),(control.SNAP,new,True)):
        with zipfile.ZipFile(path.with_name('code.zip')) as archive:
            names=archive.namelist()
            c.require(len(names)==len(set(names))==len({n.casefold() for n in names})
                      and set(names)==set(value['sources']),'Source archive membership differs')
            for name,expected in value['sources'].items():
                c.require(binding(archive.read(name))==expected,'Archived source differs')
                if live:c.require(binding((c.REPO/name).read_bytes())==expected,'Live source differs')
        archives.append(c.identity(path.with_name('code.zip')))
    omitted={n:{'historical':a[n],'current':binding((c.REPO/n).read_bytes())}
             for n in sorted(a.keys()-b.keys())}
    updated={n for n,v in omitted.items() if v['historical']!=v['current']}
    c.require(updated=={PREFIX+'admission/prepare_certificate.py',PREFIX+'admission/test_prepare_admission.py'},
              'Unexpected omitted source change')
    lineage=c.read(control.LINEAGE_CHECKS)
    c.require(all(omitted[n]['current']==lineage['source_bindings'][n[len(PREFIX):]] for n in updated),
              'Admission update lacks passing source-bound checks')
    c.save(HERE/'source-change-inventory-001.json',{'schema':'campaign002-pre-exit-source-inventory-1',
        'old_snapshot':c.identity(old_path),'new_snapshot':c.identity(control.SNAP),'archives':archives,
        'protected624_verified':True,'counts':{'old':len(a),'new':len(b),'changed':len(changed),
        'added':len(added),'omitted':len(omitted)},'changed':changed,'added':added,'omitted':omitted,
        'scope':'Source-only verification. Omitted diagnostic/operator inputs remain retained; two updated admission files are bound by separate passing lineage checks. This is not qualification.'})
    print(json.dumps({'source_count':len(b),'changed':len(changed),'added':len(added),'omitted':len(omitted),
                      'protected624_verified':True}))

if __name__=='__main__':main()
