"""One actual branch preparation after qualification/audit; no model launch."""
import traceback
from common63 import *
from prepare_branch import prepare,verify_branch

def main():
    out=BASE/'preparation001';out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,checks={},started_utc=now(),model_calls=0,official_launches=0)
    try:
        assert_manifest('preparation')
        for name,folder in [('qualification',QUAL),('audit',AUDIT)]:
            assert_manifest(name)
            q=queue('status',read(HERE/(name+'-queue.json'))['id'])
            assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
            r=read(folder/'result.json');assert r['passed'] and all(v is True for v in r['checks'].values())
            assert sha(folder/'result.json')==sha(HERE/(name+'-result.json'))
        result['quiescence_before']=quiet();assert result['quiescence_before']['passed']
        result['capacity_before']=capacity();assert result['capacity_before']['c_headroom_pass'] and result['capacity_before']['d_headroom_pass']
        result['source']=frozen_identity();result['checkpoint']=parent_checkpoint()
        assert inventory(PARENT)==read(QUAL/'parent-before.json')
        assert inventory(PAIR/'baseline')==read(QUAL/'baseline-before.json')
        result['checks']['current_qualification_identity_capacity_exclusivity_and_preservation']=True
        claim=PAIR/'recovery-claims'/read(PARENT/'run.json')['branch_id']
        assert not claim.exists() and not DEST.exists()
        # Preserve the historical lineage verbatim, before any pointer update.
        prior=(PAIR/'maps-lineage.json').read_bytes()
        with (out/'maps-lineage-before.json').open('xb') as stream:stream.write(prior);stream.flush();os.fsync(stream.fileno())
        result['preparer_readback']=prepare(DEST,claim)
        assert read(claim/'operator-authority.json')['prior_lineage']['sha256']==sha(out/'maps-lineage-before.json')
        result['checks']['single_exclusive_c_branch_prepared']=True
        # Independently use the audited candidate as a data-byte oracle. Only
        # explicit operator metadata may differ; no checkpoint pointer enters a
        # robot filesystem and all scientific/configuration bytes must match.
        candidate=inventory(QUAL/'candidate');actual=inventory(DEST)
        changed={'run.json','recovery-ready.json','latest-checkpoint.json'}
        assert set(actual)==set(candidate)
        assert {n:v for n,v in actual.items() if n not in changed}=={n:v for n,v in candidate.items() if n not in changed}
        run=read(DEST/'run.json');source=read(PARENT/'run.json');binding=run['recovery']
        assert run==dict(source,branch_id=run['branch_id'],recovery=binding) and run['branch_id']!=source['branch_id']
        assert Path(binding['claim']).resolve()==(claim/'claim.json').resolve()
        assert read(claim/'claim.json')['destination']==str(DEST.resolve())
        ready=read(DEST/'recovery-ready.json')
        assert not ready['qualification_fixture'] and ready['claim_sha256']==sha(claim/'claim.json')
        assert ready['parent_inventory_sha256']==hashlib.sha256(canonical(read(QUAL/'parent-before.json'))).hexdigest()
        assert Path(read(DEST/'latest-checkpoint.json')['path']).resolve()==(DEST/'checkpoints/session-00005').resolve()
        from run import verify_run
        verify_run(DEST,True)
        result['checks']['actual_branch_independently_matches_audited_bytes_and_normal_official_checks']=True
        assert inventory(PARENT)==read(QUAL/'parent-before.json')
        assert inventory(PAIR/'baseline')==read(QUAL/'baseline-before.json')
        assert inventory(PAIR/'maps')==read(QUAL/'maps-before.json')
        assert (PAIR/'maps-lineage.json').read_bytes()==prior
        result['quiescence_after']=quiet();assert result['quiescence_after']['passed']
        result['capacity_after']=capacity();assert result['capacity_after']['c_headroom_pass'] and result['capacity_after']['d_headroom_pass']
        result['checks']['post_preparation_preservation_retirement_and_headroom']=True
        binding_record=dict(schema='apartment-operator-c-checkpoint5-route-1',created_utc=now(),active_root=str(DEST),failed_parent=str(PARENT),
            original_pristine_start=str(PAIR/'maps'),official_pair=str(PAIR),source_manifest=ref(FROZEN/'source-manifest.json'),
            certificate=ref(CODE/'commissioning.json'),parent_run=ref(PARENT/'run.json'),run=ref(DEST/'run.json'),claim=ref(claim/'claim.json'),
            readiness=ref(DEST/'recovery-ready.json'),checkpoint=ref(DEST/'checkpoints/session-00005/manifest.json'),
            state=ref(DEST/'checkpoints/session-00005/state.json'),schedule=ref(DEST/'schedule.json'),configuration=ref(DEST/'config.json'),
            prior_lineage=ref(out/'maps-lineage-before.json'),prior_c_storage_route=ref(legacy.HERE/'storage-route.json'),
            qualification=ref(QUAL/'result.json'),audit=ref(AUDIT/'result.json'),authority=ref(HERE/'authority-original.md'),
            accepted_sessions=5,advancements=2,abandoned_parent_model_calls=1,interruption_disclosed=True,comparison_authorized=False)
        save(out/'continuation-route.json',binding_record)
        save(HERE/'continuation-route.json',binding_record)
        save(claim/'accepted-route.json',dict(route=ref(out/'continuation-route.json'),created_utc=now()))
        lineage=json.loads(prior)
        lineage['history'].append(dict(source=str(PARENT),destination=str(DEST),receipt_sha256=sha(DEST/'recovery-ready.json'),
            prior_active_root=lineage['active_root'],storage_route=ref(legacy.HERE/'storage-route.json'),operator_route=ref(out/'continuation-route.json')))
        lineage['active_root']=str(DEST)
        from common import save as atomic_save
        atomic_save(PAIR/'maps-lineage.json',lineage)
        assert read(PAIR/'maps-lineage.json')==lineage
        save(claim/'lineage-committed.json',dict(lineage=ref(PAIR/'maps-lineage.json'),before=ref(out/'maps-lineage-before.json'),created_utc=now()))
        result['lineage']=ref(PAIR/'maps-lineage.json');result['route']=ref(HERE/'continuation-route.json')
        result['checks']['append_only_claim_and_explicit_original_pair_lineage_binding']=True
        result['passed']=True
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    result['finished_utc']=now();save(out/'result.json',result);save(HERE/'preparation-result.json',result)
    print(json.dumps({k:result.get(k) for k in ('passed','checks','error','traceback','route')}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
