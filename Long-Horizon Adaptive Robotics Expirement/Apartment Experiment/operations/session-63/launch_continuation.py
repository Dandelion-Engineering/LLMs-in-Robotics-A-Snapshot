"""One submission of the accepted continuation; never retries a submission."""
from common63 import *
from register_attempt import append,base,mapref

def main():
    for name in ('qualification','audit','preparation'):
        assert_manifest(name)
        q=queue('status',read(HERE/(name+'-queue.json'))['id'])
        r=read(HERE/(name+'-result.json'))
        assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
        assert r['passed'] and all(v is True for v in r['checks'].values())
    route=read(HERE/'continuation-route.json')
    assert Path(route['active_root']).resolve()==DEST.resolve()
    for key in ('source_manifest','certificate','parent_run','run','claim','readiness','checkpoint','state','schedule','configuration','prior_lineage','prior_c_storage_route','qualification','audit','authority'):
        record=route[key];assert sha(record['uri'])==record['sha256'],key
    assert Path(read(PAIR/'maps-lineage.json')['active_root']).resolve()==DEST.resolve()
    from run import verify_run
    verify_run(DEST,True)
    from prepare_branch import verify_branch
    proof=verify_branch(DEST)
    state=quiet();assert state['passed']
    margin=capacity();assert margin['c_headroom_pass'] and margin['d_headroom_pass']
    operator=BASE/'launch';operator.mkdir(exist_ok=False)
    argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(FROZEN),'--',
        sys.executable,'-X','utf8','-B',str(CODE/'run.py'),'launch','--root',str(DEST),'--resume','--official']
    intent=dict(created_utc=now(),argv=argv,route=ref(HERE/'continuation-route.json'),actual_branch_readback=proof,
        quiescence=state,capacity=margin,automatic_resubmission=False,parent_abandoned_model_calls=1,
        expected_first_new_native_session=6,operator_launcher=ref(__file__))
    save(operator/'intent.json',intent);save(HERE/'launch-intent.json',intent)
    original=json.loads(invoke_map('lookup','--kind','run','--id','APARTMENT-v4-maps','--json'))['records'][0]['record']
    record=dict(original)
    record.update(base(),id='APARTMENT-v4-maps-checkpoint5-continuation-session63',started_at=None,rerun_of_run_id='APARTMENT-v4-maps')
    record['tags']=['apartment','official','maps','checkpoint-recovery','documented-interruption']
    record['condition_details']=dict(original['condition_details'],recovery_parent='APARTMENT-v4-maps',accepted_prefix_sessions=5,
        abandoned_parent_native_calls=1,checkpoint_manifest_sha256=EXPECTED_CP,operator_route=str(HERE/'continuation-route.json'),
        uninterrupted=False,scientific_source_changes=0,continuation_not_new_pair=True)
    record['evidence']=[*original['evidence'],mapref('Authenticated continuation route',HERE/'continuation-route.json'),mapref('Once-only launch intent',HERE/'launch-intent.json')]
    append('run',record)
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    response=dict(exit_status=p.returncode,stdout=p.stdout,stderr=p.stderr)
    save(operator/'submission-response.json',response)
    assert p.returncode==0,'Submission uncertain or failed: preserve, no resubmission'
    job=json.loads(p.stdout);save(operator/'queue.json',job);save(HERE/'official-queue-submission.json',job)
    print(json.dumps(dict(job=job['id'],state=job['state'],root=str(DEST))),flush=True)

def invoke_map(*args):
    return output(sys.executable,'-X','utf8','-B',str(REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'),*args)

if __name__=='__main__':main()
