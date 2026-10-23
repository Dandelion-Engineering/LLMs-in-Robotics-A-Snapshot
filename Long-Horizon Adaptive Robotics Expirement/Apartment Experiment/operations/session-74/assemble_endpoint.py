"""Assemble only a successfully audited endpoint with verified paused monitoring."""
from pathlib import Path
import json
import sys

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS.parent/'session-63'))
import common63 as c


def mapref(label, path):
    return dict(label=label, uri=str(Path(path).resolve()), sha256=c.sha(path), state='available', access='operator', locator=None)


def main():
    audit_path = c.BASE/'endpoint-session74/completion001/result.json'
    r = c.read(audit_path)
    q = c.read(OPS/'audit-terminal.json')
    assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
    assert r['passed'] and all(v is True for v in r['checks'].values()) and len(r['checks'])==9
    monitor = c.read(OPS/'monitoring-paused.json')
    assert monitor['passed'] and monitor['dedicated_paused'] and monitor['five_older_unchanged_paused']
    a = r['accounting']; assert [a[k] for k in ('accepted_closed','total_calls','advancements','household_latches','timed_throwing_advancements')]==[34,35,21,14,7]
    native = r['native']['sessions']
    journal_counts = dict(accepted_sessions=len(native), reads=sum(x['reads'] for x in native), mutations=sum(x['mutations'] for x in native))
    sources = dict(audit=audit_path,audit_queue=OPS/'audit-terminal.json',scientific_queue=OPS/'scientific-terminal.json',
        audit_manifest=OPS/'audit-completion-manifest.json',audit_submission=OPS/'audit-completion-queue-submission.json',
        first_audit_failure=OPS/'audit001-terminal.json',reader_diagnosis=OPS/'audit-reader-diagnosis.json',window15=OPS/'session15-window-readback.json',
        observation=OPS/'observation-summary.json',viewer=OPS/'viewer-verification.json',timing=OPS/'timing-provenance.json',
        monitoring_before=OPS/'monitoring-before.json',monitoring_paused=OPS/'monitoring-paused.json',capacity_final=OPS/'capacity-final.json',
        route=c.HERE/'continuation-route.json',protocol=c.HERE/'MONITORING-PROTOCOL.md',
        original_failure=c.read(c.PARENT/'latest-execution.json')['path'],
        final_checkpoint=c.DEST/'checkpoints/session-00034/manifest.json',
        final_state=c.DEST/'checkpoints/session-00034/state.json',
        execution=c.read(c.DEST/'latest-execution.json')['path'],
        baseline_endpoint=OPS.parent/'session-57/endpoint.json',reader=Path(__file__))
    evidence={name:mapref(name.replace('_',' '),p) for name,p in sources.items()}
    endpoint=dict(schema='apartment-v4-maps-recovered-endpoint-1',recorded_utc=c.now(),development_session=74,
        root=str(c.DEST),failed_parent=str(c.PARENT),run_id='APARTMENT-v4-maps-checkpoint5-continuation-session63',
        conclusion='Completed under the unchanged endpoint/latch/closeout rules, with timing and snapshot caveats and one explicitly preserved recovery interruption: 34 accepted sessions plus one abandoned original native invocation. Fourteen household latches and seven timed throwing advancements.',
        execution_status='completed',validity='valid',outcome='success',endpoint_independently_accepted=True,
        accounting=a,audit_checks=r['checks'],scientific_queue=r['scientific_queue'],audit_queue=q,
        checkpoint=r['checkpoints'][-1],replay=r['replay'],original_parent_replay=r['original_parent_replay'],
        recordings=r['recordings'],journals=journal_counts,physical_corroboration=r['physical_corroboration'],
        physical_snapshots=r['physical_household_readback'],
        physical_snapshot_exceptions=[x for x in r['physical_household_readback'] if not(x['near_event']['passed'] and x['boundary']['passed'])],
        native_model=dict(name='gpt-6-astra',reasoning_effort='max',distinct_threads=35,original_accepted=5,abandoned_original=1,continuation=29),
        retirement=dict(windows_owner_records=len(r['retirement']['windows']),windows_states=dict(__import__('collections').Counter(x['observation']['state'] for x in r['retirement']['windows'])),
            linux_identity_checks=len(r['retirement']['linux']['identities']),linux_process_matches=r['retirement']['linux']['process_matches'],
            linux_mounts=r['retirement']['linux']['mounts'],linux_unreadable_cmdlines=r['retirement']['linux']['unreadable_cmdlines'],
            hosts=r['retirement']['hosts'],normal_receipts=len(r['retirement']['normal_receipts']),
            interpretation='Fresh process identity and mount census proves retirement; authenticated normal exit receipts prove orderly completion. No resource was terminated by this observer.'),
        full_inventory_preservation=r['preservation_before'],preservation_after=r['preservation_after'],frozen_source_files=r['frozen_files'],
        audit_history=dict(first_stage_failure=r['first_stage_failure'],completion_queue=q,restored_terminal_reemission=r['restored_terminal_reemission']),
        session15_window_readback=c.read(OPS/'session15-window-readback.json'),
        capacity_before=r['capacity_before'],capacity_after=r['capacity_after'],capacity_final=c.read(OPS/'capacity-final.json'),
        monitoring=dict(dedicated_paused=True,five_older_unchanged_paused=True),
        timing=c.read(OPS/'timing-provenance.json'),
        interruption_disclosed=True,comparison_performed=False,scientific_writes=0,new_model_calls=0,
        limits=r['limitations']+[
            'Session15 release was requested 3.812 s and completed 4.412 s after its work deadline; the unchanged controller admitted it and that session did not advance. Acceptance under frozen latch/closeout rules is not a claim of perfect timing-instruction compliance. Earlier blocked navigation and incomplete attempts remain visible; this is not a complete secondary-episode census.',
            'Session34 had sustained all-four feedback, with green occluded and no single unobstructed final image of all four. Later success does not retroactively supply missing views from sessions32-33.',
            'The old viewer tab retains session34 with a visible fetch error after the server retired; it is not a live display.'
        ],evidence=evidence)
    c.save(OPS/'endpoint.json',endpoint)
    c.save(c.BASE/'endpoint-session74/verified-endpoint.json',endpoint)
    eref=mapref('Session 74 independently audited recovered Maps endpoint',OPS/'endpoint.json')
    def metric(name,value,unit,denominator,description,missing=None):
        return dict(name=name,value=value,unit=unit,denominator=denominator,denominator_description=description,missing_reason=missing,evidence=[eref])
    metrics=[
        metric('total_native_invocations_including_abandoned',35,'calls',None,'Five accepted original calls, one abandoned original session-6 call and twenty-nine continuation calls; one recovered history.'),
        metric('accepted_closed_sessions',34,'sessions',35,'All native calls, including the separately abandoned original call.'),
        metric('abandoned_original_invocations',1,'calls',35,'All native calls across original and continuation roots.'),
        metric('continuation_invocations',29,'calls',None,'Calls made after restoration of checkpoint5.'),
        metric('assignment_advancements',21,'assignments',21,'Frozen 21-assignment schedule.'),
        metric('household_success_latches',14,'assignments',14,'Seven bedroom and seven kitchen household assignments.'),
        metric('timed_throwing_advancements',7,'windows',7,'Seven fixed working windows; not a mastery measure.'),
        metric('nonadvancing_accepted_sessions',len(a['nonadvancing_sessions']),'sessions',34,'Normally closed accepted sessions without advancement.'),
        metric('recovery_branches',1,'branches',None,'One explicitly authorized checkpoint5 continuation; not uninterrupted.'),
        metric('throwing_mastery',None,'score',None,'No mastery scoring was performed in this endpoint audit.','Timed advancement does not establish mastery.')]
    for key in ('first_retained_sample_passes','close_boundary_passes','corroborated_at_either_observed_time','exact_event_sample_count'):
        metrics.append(metric('household_'+key,r['physical_corroboration'][key],'snapshots',14,'Independent reconstruction at retained sample or checkpoint; offsets are preserved in the endpoint evidence.'))
    record=dict(schema_version='architecture-map-1.0',id='APARTMENT-v4-maps-recovered-result-session74',recorded_at=c.now(),author='Codex session 74',
        tags=['apartment','maps','verified-endpoint','checkpoint-recovery','documented-interruption','retired'],
        run_id=endpoint['run_id'],supersedes_result_id=None,execution_status='completed',validity='valid',
        validity_reason='Scientific queue and audit completion queue succeeded with integer exit0. The first audit queue failed on a globally unique docking-terminal assumption after passing five gates; its failure is preserved and the correction authenticates the sole restored terminal re-emission. The two-stage audit passes nine gates that authenticate all accepted checkpoints, original abandoned work, frozen source/environment, complete journals/sensors/replay/transports and actual retirement. Physical snapshot offsets and exceptions remain explicit under the unchanged latched success rule. The session15 late release remains an explicit instruction-timing deviation; validity is scoped to the unchanged endpoint/latch/closeout rules. No condition comparison or throwing mastery claim.',
        outcome='success',ended_at=r['scientific_queue']['ended_at'],termination_reason='Fixed 21-assignment endpoint reached at accepted checkpoint34; resources retired normally and the dedicated read-only monitor paused after independent audit.',
        metrics=metrics,evidence=[eref],details=dict(accounting=a,physical_corroboration=r['physical_corroboration'],physical_snapshot_exceptions=endpoint['physical_snapshot_exceptions'],
            interruption_disclosed=True,original_failure_preserved=True,source_changes=0,scientific_comparison=False,limits=endpoint['limits']))
    c.save(OPS/'map-result.json',record)
    note=dict(schema_version='architecture-map-1.0',id='APARTMENT-v4-maps-recovered-endpoint-session74',recorded_at=c.now(),author='Codex session 74',
        tags=['apartment','maps','checkpoint-recovery','endpoint','handoff'],details=dict(accepted_closed=34,total_calls=35,household_successes=14,timed_throwing_advancements=7,monitor_paused=True),
        target_ids=[endpoint['run_id'],record['id']],claim_type='event',supersedes_note_id=None,
        body='Recovered Maps reached the fixed 21-assignment endpoint with 34 accepted closed sessions plus one abandoned original session-6 native invocation. Five original accepted calls and twenty-nine continuation calls remain distinct. All nine independent read-only audit gates passed across the preserved first stage and successful completion queue. The first queue failed on a globally unique terminal-receipt assumption; a separately recorded correction scopes dock completion to the originating session and authenticates the restored checkpoint5 re-emission. Coverage includes all checkpoints, complete recordings/journals/transports, full accepted/original/Baseline/pristine-start byte preservation and actual retirement. Fourteen household latches remain separate from seven timed throwing advancements. Final bedroom success resolves prior containment uncertainty without erasing incomplete attempts. Dedicated monitor paused; five older monitors unchanged/paused. Viewer is retired, with a retained tab and fetch error. Preserve physical snapshot offsets, recovery interruption, C:/D: and host timing, session15 late release (request +3.812 s, completion +4.412 s after its work deadline), earlier blocked navigation and Baseline drawer-persistence/+16-ms caveats. No scientific comparison, scientific retry, further recovery or model call occurred in this audit.',evidence=[eref])
    c.save(OPS/'map-note.json',note)
    print(json.dumps(dict(endpoint=c.ref(OPS/'endpoint.json'),map_result=c.ref(OPS/'map-result.json'),map_note=c.ref(OPS/'map-note.json'),accounting=a,physical=r['physical_corroboration']),indent=2))


if __name__=='__main__':main()
