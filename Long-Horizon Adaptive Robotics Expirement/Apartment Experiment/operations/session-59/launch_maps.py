"""Exclusive submission of the existing Maps condition after storage audit."""
from support import *
from register_attempt import append,base,mapref


def main():
    audit=read(HERE/'audit-result.json')
    assert audit['passed'] and all(v is True for v in audit['checks'].values())
    assert sha(HERE/'audit-result.json')==sha(DATA/'audit001/result.json')
    terminal=queue('status',read(HERE/'audit-queue.json')['id'])
    assert terminal['state']=='succeeded' and type(terminal['exit_status']) is int and terminal['exit_status']==0
    for attempt in ('qualification','audit'):
        for name,row in read(HERE/(attempt+'-manifest.json'))['files'].items():assert sha(HERE/name)==row['sha256'],name
    assert inventory(PAIR/'maps')==inventory(RUN)==read(QUAL/'maps-before.json')
    assert not read(RUN/'run.json')['launched']
    assert set(p.name for p in RUN.iterdir())=={'filesystem','run.json','config.json','schedule.json','initial-filesystem.json'}
    margin=capacity(read(QUAL/'baseline-allocation.json'));assert margin['c_headroom_pass'] and margin['d_headroom_pass']
    quiet=quiescence();assert quiet['passed'], 'Duplicate runtime, queue, mount or monitor'
    verification=output(sys.executable,'-X','utf8','-B','-c',
        'from run import verify_run;import sys;verify_run(sys.argv[1],True);print("verified")',str(RUN),cwd=CODE)
    assert verification.strip()=='verified'
    operator=DATA/'operator/launch';operator.mkdir(parents=True,exist_ok=False)
    route=dict(schema='apartment-same-pair-storage-route-1',created_utc=now(),**audit['route'],
        sole_runnable_instance=str(RUN),original_d_start_disposition='Immutable prepared-start archive; do not launch this duplicate',
        qualification_result=ref(QUAL/'result.json'),independent_audit=ref(DATA/'audit001/result.json'),
        audit_queue=terminal['id'],authority=ref(HERE/'authority-original.md'),source_byte_changes=0,run_metadata_byte_changes=0)
    save(operator/'storage-route.json',route)
    save(PAIR/'operator/maps-storage-route-session59.json',route)
    save(HERE/'storage-route.json',route)
    append('note',base()|dict(id='APARTMENT-v4-maps-c-storage-qualified-session59',target_ids=['APARTMENT-v4-maps','APARTMENT-s59-audit-result'],
        claim_type='decision',supersedes_note_id=None,
        body='The existing pristine v4 Maps condition has one byte-faithful active storage instance on project-local C:. Frozen source, certificate, run metadata, branch ID, schedule and original pair reference are unchanged. Independent queued qualification/readback passed before launch. Original D: start and all Baseline files remain intact. Storage timing/location differs and remains an explicit limitation. No recovery, replacement or scientific comparison is authorized.',
        evidence=[mapref('Sole active storage binding',HERE/'storage-route.json')],details=dict(active_root=str(RUN),original_root=str(PAIR/'maps'))))
    argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(FROZEN),'--',
          sys.executable,'-X','utf8','-B',str(CODE/'run.py'),'launch','--root',str(RUN),'--official']
    save(operator/'intent.json',dict(argv=argv,created_utc=now(),capacity=margin,quiescence=quiet,route=ref(operator/'storage-route.json'),
        authority=ref(HERE/'authority-original.md'),source_manifest=ref(FROZEN/'source-manifest.json'),automatic_resubmission=False))
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    save(operator/'submission-response.json',dict(exit_status=p.returncode,stdout=p.stdout,stderr=p.stderr))
    assert p.returncode==0,'Submission failed or uncertain; preserve and investigate, never resubmit automatically'
    q=json.loads(p.stdout);save(operator/'queue.json',q);save(HERE/'official-queue-submission.json',q)
    print(json.dumps(dict(job=q['id'],state=q['state'],root=str(RUN))),flush=True)


if __name__=='__main__':main()
