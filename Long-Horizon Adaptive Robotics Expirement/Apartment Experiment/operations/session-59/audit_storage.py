"""Independent raw-evidence readback; never creates a guest or calls a model."""
import copy
import traceback
from support import *


def initial(path):
    with Path(path).open('rb') as f:return json.loads(f.readline())['state']


def main():
    out=DATA/'audit001';out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,checks={},started_utc=now(),model_calls=0,official_invocations=0)
    try:
        for name,row in read(HERE/'audit-manifest.json')['files'].items():assert sha(HERE/name)==row['sha256'],name
        q=queue('status',read(HERE/'qualification-queue.json')['id'])
        assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
        result['qualification_queue']=q
        proof=read(QUAL/'result.json');assert proof['passed'] and all(v is True for v in proof['checks'].values())
        for name,row in read(HERE/'qualification-manifest.json')['files'].items():assert sha(HERE/name)==row['sha256'],name
        result['checks']['terminal_attempt_identity']=True
        prepared=read(PAIR/'prepared.json');cert=read(CODE/'commissioning.json')
        assert sha(CODE/'commissioning.json')==prepared['certificate_sha256']=='49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f'
        src=inventory(FROZEN);src.pop('source-manifest.json')
        assert src==read(FROZEN/'source-manifest.json')
        assert sha(FROZEN/'source-manifest.json')==prepared['source_manifest_sha256']=='ee865baf93b83dafb8fc3daa49c22c7718527ef5a6774e99c8124e1eadac85b0'
        result['checks']['unchanged_original_certificate_and_full_source']=True
        assert inventory(PAIR/'baseline')==read(QUAL/'baseline-before.json')
        original=read(QUAL/'maps-before.json');host=read(QUAL/'maps-host-namespace-before.json')
        assert inventory(PAIR/'maps')==inventory(RUN)==original
        assert namespace(PAIR/'maps')==namespace(RUN)==host
        run=read(RUN/'run.json');baseline=read(PAIR/'baseline/run.json')
        assert run['condition']=='maps' and run['run_id']=='APARTMENT-v4-maps' and not run['launched'] and 'recovery' not in run
        assert Path(run['official_pair_root']).resolve()==PAIR.resolve()
        assert all(run[k]==baseline[k] for k in ('source_identity','schedule_sha256','config_sha256'))
        assert inventory(RUN/'filesystem')==run['template']==prepared['initial']['maps'] and len(run['template'])==19
        assert not output('git','ls-files','--','Local Experiment Data/apartment-v4-maps',cwd=REPO).strip()
        result['checks']['complete_baseline_preservation_and_exact_same_pair_copy']=True
        sys.path.insert(0,str(CODE))
        from run import verify_run
        from environment import identity
        from recording import verify_checkpoint,verify_prefix
        import journal_reader
        verify_run(RUN,True);assert identity()==cert['environment']
        result['checks']['unchanged_official_gates_admit_c_instance']=True
        journal_rows=[]
        for scope in (QUAL,DQUAL):
            for journal in sorted(scope.rglob('mutations.jsonl')):
                location=read(journal.parent.parent/'location.json')
                r=journal_reader.verify(journal.parent,location['run_id'])
                assert r['passed']
                assert r['state']==read(journal.parent.parent/'final-namespace.json')
                native_exit=read(journal.parent/'native-exit.json')
                journal_rows.append(dict(path=str(journal),sha256=sha(journal),records=r['records'],mutations=r['mutations'],
                    verified_versions=r['verified_content_versions'],final_state_sha256=r['final_state_sha256'],native_exit=native_exit))
        assert len(journal_rows)>=6
        def normalized(state):
            state=copy.deepcopy(state)
            for node in state['nodes'].values():
                for key in ('atime_ns','mtime_ns','ctime_ns'):node.pop(key,None)
            return state
        assert normalized(initial(DQUAL/'pristine/workspace/journal/mutations.jsonl'))==normalized(initial(QUAL/'pristine/workspace/journal/mutations.jsonl'))
        before=read(QUAL/'lifecycle/namespace/sessions/session-00001/workspace/final-namespace.json')
        restored=initial(QUAL/'lifecycle/namespace/sessions/session-00002/workspace/journal/mutations.jsonl')
        assert before==restored
        result['checks']['raw_c_d_guest_equivalence_and_exact_inode_restore']=True
        result['journals']=journal_rows
        for condition in ('baseline','maps'):
            root=QUAL/'native-preflight'/condition
            client=read(root/'native/client/result.json')
            assert client['success'] and client['preflight_passed'] and not client.get('model_started')
            for mode in ('canary','codehost-canary'):
                r=read(root/'native'/(mode+'.json'));assert r['exit_status']==0 and json.loads(r['stdout'])['qualified']
        result['checks']['actual_namespace_canaries_native_transport_no_model']=True
        continuation=QUAL/'lifecycle/continuation'
        checkpoints=[]
        for p in sorted((continuation/'checkpoints').iterdir()):
            if not p.is_dir():continue
            a=verify_checkpoint(p);b=verify_prefix(continuation,p);assert a['passed'] and b['passed']
            checkpoints.append(dict(path=str(p),manifest_sha256=sha(p/'manifest.json'),state_sha256=sha(p/'state.json')))
        assert len(checkpoints)>=21
        corrupt_rejected=False
        try:verify_checkpoint(QUAL/'lifecycle/corrupt-checkpoint')
        except (ValueError,AssertionError):corrupt_rejected=True
        assert corrupt_rejected
        lifecycle=read(QUAL/'lifecycle/result.json');assert lifecycle['passed'] and all(v is True for v in lifecycle['checks'].values())
        result['checkpoints']=checkpoints
        result['checks']['raw_checkpoint_prefix_replay_and_corrupt_copy_rejection']=True
        result['quiescence']=quiescence();assert result['quiescence']['passed']
        census=read(QUAL/'baseline-allocation.json')
        result['capacity']=capacity(census);assert result['capacity']['c_headroom_pass'] and result['capacity']['d_headroom_pass']
        result['checks']['current_capacity_and_runtime_retirement']=True
        result['route']=dict(original_pair=str(PAIR),original_start=str(PAIR/'maps'),active_storage_root=str(RUN),
            run_id=run['run_id'],branch_id=run['branch_id'],run_json_sha256=sha(RUN/'run.json'),
            source_manifest=ref(FROZEN/'source-manifest.json'),certificate=ref(CODE/'commissioning.json'),
            original_pair_manifest=ref(PAIR/'prepared.json'),initial_manifest=ref(RUN/'initial-filesystem.json'),
            recovery='Frozen recovery remains fail-closed for this relocated root; no recovery or retry authorized',
            source_and_run_metadata_byte_unchanged=True)
        save(out/'qualified-evidence-manifest.json',dict(created_utc=now(),roots={str(QUAL):inventory(QUAL),str(DQUAL):inventory(DQUAL)}))
        result['qualified_evidence_manifest']=ref(out/'qualified-evidence-manifest.json')
        result['passed']=True
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    result['finished_utc']=now();save(out/'result.json',result);save(HERE/'audit-result.json',result)
    print(json.dumps({k:result.get(k) for k in ('passed','checks','error','traceback','capacity')}),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
