"""Record the observed handoff and append its evidence note, without run writes."""
import importlib.util
from common63 import *

def main():
    observation=BASE/'observations/session63-handoff-7acb4b0e8c5e44eb8c5b0948295e4460.json'
    observed=read(observation);boundary=read(HERE/'first-boundary-result.json')
    assert observed['passed'] and observed['queue']['state']=='running' and boundary['passed']
    assert observed['progress']['accepted_sessions']==6 and observed['progress']['closed_advancements']==3
    assert observed['new_model_calls_started']==2 and observed['total_model_calls_including_abandoned_parent']==8
    monitoring=read(HERE/'monitoring.json')
    for row in [dict(record=monitoring['automation_file'],status='ACTIVE')]+monitoring['older_unchanged_paused']:
        source=row['record'];assert sha(source['uri'])==source['sha256']
        assert tomllib.loads(Path(source['uri']).read_text(encoding='utf-8'))['status']==row['status']
    gates={}
    for name in ('qualification','audit','preparation'):
        result=read(HERE/(name+'-result.json'));terminal=read(HERE/(name+'-terminal.json'))
        assert result['passed'] and all(v is True for v in result['checks'].values())
        assert terminal['state']=='succeeded' and type(terminal['exit_status']) is int and terminal['exit_status']==0
        gates[name]=dict(gates=len(result['checks']),job=terminal['id'],result=ref(HERE/(name+'-result.json')),terminal=ref(HERE/(name+'-terminal.json')))
    rendered=dict(observed_utc='2026-10-10T19:08:52.792Z',url='http://127.0.0.1:57835/',tab_id='1',
        browser='Codex in-app browser',session=7,phase='active',battery_percent=98.9,
        geometry_visible=True,filesystem_reads_visible=True,fetch_error_visible=False,marked_deliverable=True,
        verification='Actual accessibility tree and rendered screenshot via cua_repl; screenshot retained in this conversation, not claimed as a saved local file.',
        earlier_rendered_observations=ref(HERE/'viewer-verification.json'))
    save(HERE/'viewer-handoff-verification.json',rendered)
    handoff=dict(recorded_utc=now(),observation_utc=observed['observed_utc'],status='continuation-running',
        accepted_root=str(DEST),failed_parent=str(PARENT),scientific_queue=observed['queue'],
        scientific_source_changes=0,official_continuation_submissions=1,engineering_gates=gates,
        original_accepted_sessions=5,accepted_sessions=6,new_accepted_sessions=1,closed_advancements=3,
        advancement_kinds=observed['progress']['completed_by_kind'],abandoned_original_model_calls=1,
        continuation_calls_started=2,total_model_calls_including_abandoned_parent=8,active_session=7,
        latest_checkpoint=observed['latest_checkpoint'],capacity=observed['capacity'],
        monitor_id=monitoring['automation']['id'],monitor_status='ACTIVE',older_monitors_unchanged_paused=5,
        endpoint_accepted=False,physical_endpoint_rescoring_performed=False,comparison_performed=False,
        interruption_disclosed=True,
        evidence={name:ref(path) for name,path in dict(route=HERE/'continuation-route.json',
            observation=observation,first_boundary=HERE/'first-boundary-result.json',
            viewer=HERE/'viewer-handoff-verification.json',monitoring=HERE/'monitoring.json',
            monitoring_protocol=HERE/'MONITORING-PROTOCOL.md',
            registration_correction=HERE/'operator-registration-correction.json',reader=Path(__file__)).items()})
    save(HERE/'handoff.json',handoff)
    # Explicit path loading avoids the retained historical launcher attribution error.
    spec=importlib.util.spec_from_file_location('session63_register',HERE/'register_attempt.py')
    register=importlib.util.module_from_spec(spec);spec.loader.exec_module(register)
    register.append('note',register.base()|dict(id='APARTMENT-v4-maps-checkpoint5-continuation-handoff-session63',
        target_ids=['APARTMENT-v4-maps-checkpoint5-continuation-session63'],claim_type='note',supersedes_note_id=None,
        body='The separately qualified operator-side C: checkpoint-5 branch launched once under the byte-unchanged official apparatus. Qualification, independent audit and production preparation passed 11, 9 and 5 gates with succeeded/integer-zero receipts. At 12:08 PDT the continuation remained running: checkpoint 6 passed independent report/journal/prefix and actual retirement checks, preserving six accepted sessions and three assignment advancements (one timed throwing window, bedroom, kitchen). Session 7 was active with a fresh native thread and visibly rendered viewer. One abandoned original session-6 call remains immutable and separately counted; two continuation calls had started, eight calls total including five original accepted calls. The dedicated 30-minute read-only monitor is active and all five older monitors remain unchanged/paused. This is an interrupted ongoing history, not an endpoint or a Baseline-versus-Maps comparison. The frozen recovery D: guard remains unchanged and still rejects C:; normal official runner checks accept this explicitly bound operator-prepared branch.',
        evidence=[register.mapref('Authenticated ongoing continuation handoff',HERE/'handoff.json')],
        details=dict(queue_id=observed['queue']['id'],accepted_sessions=6,closed_advancements=3,
            abandoned_original_model_calls=1,continuation_calls_started=2,endpoint_accepted=False)))
    print(json.dumps(dict(handoff=ref(HERE/'handoff.json'),gates={k:v['gates'] for k,v in gates.items()},monitor='ACTIVE')),flush=True)

if __name__=='__main__':main()
