"""Once-only, no-model qualification of a byte-faithful storage relocation."""
import copy
import time
import traceback
from support import *


def main():
    QUAL.mkdir(parents=True, exist_ok=False)
    result=dict(passed=False, checks={}, started_utc=now(), official_model_calls=0, engineering_model_calls=0)
    workspace=None
    try:
        manifest=read(HERE/'qualification-manifest.json')
        for name,row in manifest['files'].items(): assert sha(HERE/name)==row['sha256'], name
        result['quiescence_before']=quiescence(); assert result['quiescence_before']['passed'], 'Conflicting runtime, monitor or queue'
        prepared=read(PAIR/'prepared.json')
        source=inventory(FROZEN); source.pop('source-manifest.json')
        assert source==read(FROZEN/'source-manifest.json')
        assert sha(FROZEN/'source-manifest.json')==prepared['source_manifest_sha256']
        cert=read(CODE/'commissioning.json'); assert cert['passed'] and sha(CODE/'commissioning.json')==prepared['certificate_sha256']
        for name,digest in cert['protocol_sha256'].items(): assert sha(CODE/name)==digest, name
        result['checks']['exact_certified_frozen_source']=True
        sys.path.insert(0,str(CODE))
        from run import verify_run
        from environment import identity
        result['current_environment']=identity(); assert result['current_environment']==cert['environment']
        verify_run(PAIR/'maps',True)
        result['checks']['unchanged_runner_admits_original_pair_and_current_environment']=True
        endpoint=read(HERE.parent/'session-57/endpoint.json')
        result['baseline_endpoint_refs']={}
        for name,r in endpoint['evidence'].items():
            assert sha(r['uri'])==r['sha256'],name
            result['baseline_endpoint_refs'][name]=ref(r['uri'])
        for name in ('official_queue','full_audit_queue','supplement_queue'):
            old=read(endpoint['evidence'][name]['uri']); current=queue('status',old['id'])
            assert current==old and current['state']=='succeeded' and type(current['exit_status']) is int and current['exit_status']==0
        for name in ('full_audit','supplement'):
            audit=read(endpoint['evidence'][name]['uri']); assert audit['passed'] and all(v is True for v in audit['checks'].values())
        result['checks']['accepted_baseline_endpoint_and_audits_authenticated']=True
        print('Baseline and certificate admitted; measuring full preserved Baseline.',flush=True)
        protected=inventory(PAIR/'baseline'); save(QUAL/'baseline-before.json',protected)
        original=inventory(PAIR/'maps'); meta=namespace(PAIR/'maps')
        assert len(inventory(PAIR/'maps/filesystem'))==19
        assert set(p.name for p in (PAIR/'maps').iterdir())=={'filesystem','run.json','config.json','schedule.json','initial-filesystem.json'}
        assert not read(PAIR/'maps/run.json')['launched']
        assert inventory(PAIR/'maps/filesystem')==read(PAIR/'maps/initial-filesystem.json')==prepared['initial']['maps']
        save(QUAL/'maps-before.json',original);save(QUAL/'maps-host-namespace-before.json',meta)
        census=allocation_census(PAIR/'baseline',volume('D:\\')['allocation_unit_bytes'])
        save(QUAL/'baseline-allocation.json',census)
        result['baseline_allocation']={k:v for k,v in census.items() if k!='files_detail'}
        result['capacity_before']=capacity(census)
        assert result['capacity_before']['c_headroom_pass'] and result['capacity_before']['d_headroom_pass'], 'Full-run capacity gate failed'
        assert REPO.resolve()==Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics').resolve()
        assert RUN.resolve().is_relative_to(REPO.resolve()) and RUN.drive.upper()=='C:' and not RUN.exists()
        assert not any(p.is_junction() or p.is_symlink() for p in (REPO,DATA,DATA.parent))
        ignored=output('git','check-ignore','--',str(RUN/'run.json'),cwd=REPO).strip();assert ignored
        result['checks']['safe_ignored_c_path_and_conservative_capacity']=True
        shutil.copytree(PAIR/'maps',RUN,copy_function=shutil.copy2)
        assert inventory(RUN)==original and namespace(RUN)==meta
        assert read(RUN/'run.json')['official_pair_root']==str(PAIR)
        verify_run(RUN,True)
        result['checks']['byte_and_host_mode_mtime_path_equivalent_copy_admitted']=True
        result['copy']=dict(source=str(PAIR/'maps'),destination=str(RUN),files=len(original),guest_files=19,
            run_json_sha256=sha(RUN/'run.json'),branch_id=read(RUN/'run.json')['branch_id'],
            original_unchanged=True,source_code_changes=[],run_metadata_changes=[],
            host_metadata_scope='Relative entries, file/directory modes and mtimes copied exactly. Host volume, creation time, inode IDs and ACL inheritance necessarily differ. Pristine Workspace initialization consumes only sorted relative paths, directory kinds and file bytes, generating native inode metadata independently for each fresh condition.')
        # Compare equivalent no-model pristine namespace starts on the actual
        # two evidence volumes; use private fixture paths, never the run itself.
        from native_runtime import Workspace
        import journal_reader
        def semantic(state):
            state=copy.deepcopy(state)
            for node in state['nodes'].values():
                for key in ('atime_ns','mtime_ns','ctime_ns'):node.pop(key,None)
            return state
        initial_states=[];timings=[]
        for label,evidence,fs in [('D',DQUAL/'pristine/workspace',PAIR/'maps/filesystem'),('C',QUAL/'pristine/workspace',RUN/'filesystem')]:
            start=time.perf_counter(); workspace=Workspace(evidence,fs,'storage-'+label)
            first=read_first(evidence/'journal/mutations.jsonl')['state']
            startup=time.perf_counter()-start; final,proof=workspace.close()
            assert proof['passed'] and inventory(final)==inventory(fs)
            reread=journal_reader.verify(evidence/'journal',workspace.run_id)
            assert reread['passed'] and not workspace.process.poll()
            initial_states.append(semantic(first))
            timings.append(dict(volume=label,evidence=str(evidence),startup_s=startup,complete_cycle_s=time.perf_counter()-start,retired=workspace.closed))
            workspace=None
        assert initial_states[0]==initial_states[1]
        result['checks']['c_d_pristine_guest_namespace_equivalence_and_journal_retirement']=True
        result['timings']=timings
        save(QUAL/'namespace-equivalence.json',dict(passed=True,timings=timings,
            normalized_only=['atime_ns','mtime_ns','ctime_ns'],state=initial_states[0],
            limitation='One D then C engineering cycle; descriptive measurements, not a controlled latency estimate or scientific equivalence claim. Fresh native timestamps differ normally.'))
        print('Relocation equivalent; running frozen C-volume native and lifecycle fixtures.',flush=True)
        import integration_engineering,lifecycle_engineering
        assert integration_engineering.run(QUAL/'native-preflight'), 'C storage native isolation/transport preflight failed'
        result['checks']['frozen_two_template_native_preflight_no_provider_call']=True
        assert lifecycle_engineering.run(QUAL/'lifecycle'), 'C storage checkpoint/replay/inode lifecycle failed'
        result['checks']['frozen_checkpoint_replay_namespace_restore_on_c']=True
        assert inventory(PAIR/'baseline')==protected, 'Protected Baseline bytes changed'
        assert inventory(PAIR/'maps')==original==inventory(RUN), 'Pristine official copy changed'
        assert namespace(PAIR/'maps')==meta==namespace(RUN), 'Pristine host namespace changed'
        assert source=={k:v for k,v in inventory(FROZEN).items() if k!='source-manifest.json'}
        result['checks']['baseline_original_maps_source_and_c_copy_preserved']=True
        result['quiescence_after']=quiescence();assert result['quiescence_after']['passed']
        result['capacity_after']=capacity(census)
        assert result['capacity_after']['c_headroom_pass'] and result['capacity_after']['d_headroom_pass']
        result['checks']['post_fixture_capacity_and_retirement']=True
        result['passed']=True
    except BaseException as e:
        result.update(error=repr(e),traceback=traceback.format_exc())
    finally:
        if workspace:
            try: workspace.abort();result['abnormal_cleanup_retired']=workspace.closed
            except BaseException as e:result['cleanup_error']=repr(e)
    result['finished_utc']=now();save(QUAL/'result.json',result);save(HERE/'qualification-result.json',result)
    print(json.dumps({k:result.get(k) for k in ('passed','checks','error','traceback','capacity_after')}),flush=True)
    return 0 if result['passed'] else 1


def read_first(path):
    with Path(path).open('rb') as f:return json.loads(f.readline())


if __name__=='__main__':raise SystemExit(main())
