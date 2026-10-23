"""Read-only assessment of one unretried completed development recovery pilot."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import zipfile
from assess_bootstrap import read_json, sha, startup_read_evidence
from assess_smoke import (continuity_commits, empty_continuity_read_evidence,
                          inspect_stage, jsonl, live_read_evidence)


def source_integrity(frozen, archive_path):
    problems = []
    with zipfile.ZipFile(archive_path) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            problems.append('duplicate archive entries')
        if set(archive.namelist()) != set(frozen['sources']):
            problems.append('archive/source inventory differs')
        for name, record in frozen['sources'].items():
            if name not in archive.namelist():
                continue
            raw = archive.read(name)
            if len(raw) != record['bytes'] or sha(raw) != record['sha256']:
                problems.append(name)
    return problems


def public_support(record, history):
    """Recheck only the host's stated public effect, never hidden task success."""
    verification = record.get('verification', {})
    if verification.get('state') != 'public_observation_support':
        return {'state':verification.get('state', 'unknown'), 'independently_matched':None}
    action = record.get('envelope', {}).get('action', {})
    matches = []
    for event in history:
        packet = event.get('payload', {})
        if (event.get('type') != 'observation'
            or packet.get('sequence') != verification.get('observation_sequence')
            or packet.get('capture_sim_time_s') != verification.get('capture_sim_time_s')
            or packet.get('capture_sim_time_s', -1) <= record.get('terminal_sim_time_s', float('inf'))):
            continue
        op = action.get('operation')
        matched = ((op == 'transport' and any(d.get('id') == action.get('part_id') and d.get('zone') == action.get('destination') for d in packet.get('detections', [])))
                   or (op == 'setup' and packet.get('station', {}).get('fixture_insert') == action.get('family'))
                   or (op == 'inspect' and (packet.get('inspection') or {}).get('inspection_id') == record.get('request_id'))
                   or (op == 'cycle' and record.get('feedback', {}).get('cycle_id') is not None and packet.get('station', {}).get('completed_cycle_id') == record['feedback']['cycle_id']))
        if matched:
            matches.append(event['event_id'])
    return {'state':'public_observation_support', 'independently_matched':bool(matches), 'observation_event_ids':matches}


def classify_outcome(host_result, registry, history):
    """Keep accepted resumption distinct from actual conventional work and success."""
    handbacks = [r for r in registry.values() if r.get('actor') == 'robot' and r.get('kind') == 'handback']
    accepted = [r for r in handbacks if r.get('phase') == 'terminal' and r.get('status') == 'completed'
                and r.get('verification', {}).get('state') == 'public_resumption_conditions'
                and r.get('verification', {}).get('next_operation') in ('transport','setup','cycle','inspect','done')]
    transfers = [e for e in history if e.get('type') == 'control_owner_changed'
                 and e.get('owner') == 'conventional'
                 and any(e.get('payload', {}).get('request_id') == r['request_id']
                         and e.get('authority_epoch') == r.get('envelope', {}).get('authority_epoch', -2)+1
                         and e.get('payload', {}).get('supported_next_action', {}).get('operation') == r['verification']['next_operation'] for r in accepted)]
    conventional = []
    if transfers:
        first_event = min(e['event_id'] for e in transfers)
        dispatched_ids = {e.get('payload', {}).get('request_id') for e in history
                          if e.get('type') == 'command_dispatched' and e.get('event_id', -1) > first_event}
        conventional = [r for r in registry.values() if r.get('actor') == 'conventional'
                        and r.get('kind') == 'command' and r.get('request_id') in dispatched_ids
                        and r.get('envelope', {}).get('action', {}).get('operation') in ('transport','setup','cycle','inspect')
                        and r.get('request_event_id', -1) > first_event
                        and r.get('envelope', {}).get('authority_epoch') in {e['authority_epoch'] for e in transfers}]
    independent = host_result.get('independent_outcome')
    native_success = independent.get('success') if isinstance(independent, dict) else None
    outcome_problems = []
    if not isinstance(independent, dict) or independent.get('schema_version') != 'robot-independent-outcome-1.0' or type(native_success) is not bool:
        outcome_problems.append('missing or malformed independent evaluator outcome')
    elif native_success:
        settling, first = independent.get('settling', {}), independent.get('first_success')
        if independent.get('immediate_ready') is not True or independent.get('violations') != []:
            outcome_problems.append('success lacks readiness or has violations')
        if not isinstance(settling.get('observed_s'), (int,float)) or not isinstance(settling.get('required_s'), (int,float)) or settling.get('observed_s', -1) < settling.get('required_s', float('inf')) - 1e-9:
            outcome_problems.append('success lacks required settling dwell')
        if (not isinstance(first, dict) or first.get('order_version') != independent.get('order_version')
            or not isinstance(first.get('snapshot_sha256'), str) or len(first['snapshot_sha256']) != 64
            or first.get('sim_time_s', float('inf')) > independent.get('sim_time', -1)
            or first.get('required_dwell_s') != settling.get('required_s')):
            outcome_problems.append('success lacks coherent protected first-success record')
    terminal_consistent = ((host_result.get('terminal') == 'task_success') == (native_success is True))
    if type(native_success) is bool and not terminal_consistent:
        outcome_problems.append('host terminal conflicts with final independent evaluator success')
    if host_result.get('execution_completed') is not True or host_result.get('error') or outcome_problems:
        task_outcome = 'unknown'
    else:
        task_outcome = 'success' if native_success else 'failure'
    return {
        'handback_requests':[{'request_id':r['request_id'], 'status':r.get('status'), 'phase':r.get('phase'),
                              'error':r.get('error'), 'verification':r.get('verification')} for r in handbacks],
        'protected_handback_accepted':bool(accepted),
        'accepted_handback_corresponds_to_owner_transfer':bool(accepted) and len(transfers) == len(accepted) and host_result.get('handbacks') == len(accepted),
        'owner_transfer_event_ids':[e['event_id'] for e in transfers],
        'conventional_work_resumed':bool(conventional),
        'conventional_requests_after_handback':[r['request_id'] for r in conventional],
        'conventional_admitted_requests':[r['request_id'] for r in conventional if r.get('admission', {}).get('status') == 'accepted'],
        'conventional_completed_requests':[r['request_id'] for r in conventional if r.get('phase') == 'terminal' and r.get('status') == 'completed'],
        'conventional_public_effects':{r['request_id']:public_support(r, history) for r in conventional},
        'independent_task_outcome':task_outcome,
        'independent_outcome':independent,
        'independent_outcome_evidence_problems':outcome_problems,
        'host_terminal':host_result.get('terminal'),
        'task_success_terminal_consistent':terminal_consistent and not outcome_problems,
        'recovery_outcome':'handback_accepted' if accepted else ('no_accepted_handback' if host_result.get('execution_completed') else 'unknown'),
    }


def assess(evidence, host_evidence, queue_receipt, frozen_snapshot, expected_job_id=None):
    receipt = read_json(queue_receipt)
    job = receipt.get('job', receipt)
    if job.get('state') != 'succeeded' or job.get('exit_status') != 0:
        raise ValueError('Queue must be succeeded/exit0 before reading pilot outputs')
    if expected_job_id is not None and job.get('id') != expected_job_id:
        raise ValueError('Unexpected queue job ID')
    root, host, frozen_path = Path(evidence), Path(host_evidence), Path(frozen_snapshot)
    frozen, manifest = read_json(frozen_path), read_json(frozen_path.with_name('manifest.json'))
    archive = frozen_path.with_name('code.zip')
    source_problems = source_integrity(frozen, archive)
    sequence = read_json(root/'sequence-result.json')
    stage = inspect_stage(root/'pilot')
    registry, history = read_json(host/'command-registry.json'), jsonl(host/'public-history.jsonl')
    host_result = read_json(host/'result.json')
    outcome = classify_outcome(host_result, registry, history)
    initial, codehost = read_json(root/'pilot/canary-stdout.json'), read_json(root/'pilot/codehost-canary-stdout.json')
    location = read_json(root/'pilot/runtime-location.json')
    code_checks = codehost.get('checks', {})
    hashes = read_json(root/'pilot/runtime-input-hashes.json')
    all_reads = startup_read_evidence(stage['commands'], hashes, stage['contents'], archive)
    stable_reads = {name:all_reads[name] for name in ('RobotAgentPrompt.md','Tasks.md','Robot.md','Tools.md','Continuity.md')}
    note_read = stable_reads['Continuity.md']
    if not note_read['verified']:
        note_read['evidence'].extend(empty_continuity_read_evidence(stage['commands'], note_read['expected_sha256']))
        note_read['verified'] = bool(note_read['evidence'])
    starts = [e for e in history if e.get('type') == 'invocation_start-invocation']
    retires = [e for e in history if e.get('type') == 'invocation_retire-invocation']
    live_reads = live_read_evidence(stage, history, host_result['public_episode_id'], starts[0]['authority_epoch'] if len(starts) == 1 else -1)
    notes = continuity_commits(stage, host)
    robot = [r for r in registry.values() if r.get('actor') == 'robot']
    actions = [r for r in robot if r.get('kind') == 'command']
    observations = [r for r in robot if r.get('kind') == 'observe']
    summaries = []
    for record in actions:
        rid = record['request_id']
        dispatch = [e for e in history if e.get('type') == 'command_dispatched' and e.get('payload', {}).get('request_id') == rid]
        terminals = [e for e in history if e.get('type') == 'command_terminal' and e.get('payload', {}).get('request_id') == rid]
        summaries.append({'request_id':rid,'action':record.get('envelope', {}).get('action'),
                          'status':record.get('status'),'phase':record.get('phase'),
                          'admission':record.get('admission'), 'error':record.get('error'),
                          'dispatch_event_ids':[e['event_id'] for e in dispatch],
                          'terminal_event_ids':[e['event_id'] for e in terminals],
                          'feedback':record.get('feedback'), 'public_effect':public_support(record, history)})
    checks = {name:value for name,value in stage['checks'].items() if name != 'all_45_model_canaries_saved'}
    checks.update({
        'official_queue_succeeded_exit0':True,
        'frozen_archive_all_source_bytes_match':not source_problems,
        'manifest_one_development_pilot':manifest.get('stage') == 'development-only' and manifest.get('model_turns_max') == 1 and manifest.get('qualification_stage') == 'single-development-recovery-pilot' and manifest.get('mode') == 'serve' and manifest.get('prior_attempt') is None,
        'frozen_manifest_hash_and_run_match':sha(frozen_path.with_name('manifest.json').read_bytes()) == frozen['manifest_sha256'] and manifest['run_id'] == frozen['run_id'] == host_result.get('run_id'),
        'one_orchestrated_invocation_no_injected_interruption':sequence.get('mode') == 'pilot' and sequence.get('orchestrator_completed') is True and len(sequence.get('stages', [])) == 1 and stage['result'].get('injected_interruption') is False and host_result.get('robot_invocations') == 1,
        'host_completed_cleanly':sequence.get('host_exit_code') == 0 and host_result.get('execution_completed') is True and not host_result.get('error') and not sequence.get('forced_host_exit'),
        'actual_client_completed_native_exit0':stage['client'].get('success') is True and stage['client'].get('turn_status') == 'completed' and stage['native_exit_code'] == 0,
        'all_45_outer_boundary_canaries':initial.get('qualified') is True and len(initial.get('checks', {})) == 45 and all(v is True for v in initial.get('checks', {}).values()),
        'protected_canary_positive_controls_and_durable_backing':len(location.get('setup', {}).get('protected_exist', {})) == 4 and all(location['setup']['protected_exist'].values()) and location['setup'].get('outside_loopback_control') is True and location.get('durable_backing') is True and location.get('run', '').startswith('/var/tmp/robot-codex-session10/'),
        'codehost_ambient_capabilities_denied':codehost.get('host_qualified') is True and code_checks.get('all_tools_count') == 0 and code_checks.get('tools') == [] and all(v == 'undefined' for v in code_checks.get('apis', {}).values()) and all(v == 'denied' for v in code_checks.get('imports', {}).values()),
        'one_host_invocation_started_and_retired':len(starts) == 1 and len(retires) == 1 and starts[0]['event_id'] < retires[0]['event_id'],
        'no_repeated_dispatch_per_stable_robot_request':all(len(r['dispatch_event_ids']) <= 1 for r in summaries),
        'admitted_requests_within_host_budgets':sum(r.get('admission', {}).get('status') == 'accepted' for r in actions) <= manifest['action_request_budget'] and sum(r.get('status') in ('accepted','completed') for r in observations) <= manifest['observation_request_budget'],
        'claimed_robot_public_effects_match_protected_observations':all(r['public_effect']['independently_matched'] is not False for r in summaries),
        'claimed_conventional_public_effects_match_protected_observations':all(r['independently_matched'] is not False for r in outcome['conventional_public_effects'].values()),
        'continuity_receipts_match_protected_content_when_present':not notes['problems'] and (not notes['commits'] or notes['final_local_matches_last_commit']),
        'independent_success_label_consistent_with_terminal':outcome['task_success_terminal_consistent'],
        'protected_independent_evaluator_outcome_well_formed':not outcome['independent_outcome_evidence_problems'],
    })
    inputs = [Path(queue_receipt), frozen_path, frozen_path.with_name('manifest.json'), archive,
              root/'sequence-result.json', host/'command-registry.json', host/'public-history.jsonl', host/'result.json']
    inputs += [path for path in (root/'pilot').rglob('*') if path.is_file() and path.suffix in ('.json','.jsonl')]
    inputs += [Path(__file__), Path(__file__).with_name('assess_smoke.py'), Path(__file__).with_name('assess_bootstrap.py')]
    clean = all(bool(value) for value in checks.values())
    return {'schema':'robot-codex-development-pilot-assessment-1', 'run_id':manifest['run_id'],
            'queue_job_id':job.get('id'), 'infrastructure_and_evidence_checks_passed':clean,
            'checks':checks, 'source_integrity_problems':source_problems,
            'recovery_and_task_outcome':outcome, 'robot_commands':summaries,
            'robot_observation_request_count':len(observations), 'startup_read_evidence':stable_reads,
            'fixed_startup_reads_proven':all(r['verified'] for r in stable_reads.values()),
            'evolving_live_read_evidence':live_reads,
            'all_evolving_live_reads_proven':all(live_reads.values()),
            'actual_model_canary':{'observed_and_retained':stage['checks']['all_45_model_canaries_saved'], 'matches':stage['canary_matches'], 'required_for_this_pilot':False},
            'native_client':{'success':stage['client'].get('success'),'turn_status':stage['client'].get('turn_status'),'exit_code':stage['native_exit_code'],'error':stage['client'].get('error')},
            'continuity':notes,'retained_program_record_names':list(stage['programs']),
            'readiness_limitations':['One development fixture and one actual model invocation; no success rate or performance generalization.', 'Accepted handback establishes public resumption conditions; subsequent conventional work and independent task outcome are separate.', 'No full supervisor or computer restart tested; startup public files evolve during physics.', 'Model canary repetition is recorded when performed; ordinary pilot task did not require saving a new canary.', 'Program note records are agent-writable corroborating artifacts, not independent authority.'],
            'evidence_sha256':{str(path):sha(path.read_bytes()) for path in inputs},
            'model_calls_in_assessment':0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','host-evidence','queue-receipt','snapshot','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--job-id')
    args=parser.parse_args(argv)
    result=assess(args.evidence,args.host_evidence,args.queue_receipt,args.snapshot,args.job_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'infrastructure_and_evidence_checks_passed':result['infrastructure_and_evidence_checks_passed'],
                      'task_outcome':result['recovery_and_task_outcome']['independent_task_outcome'],
                      'failed_checks':[k for k,v in result['checks'].items() if not v], 'output':str(args.output)}))
    return 0 if result['infrastructure_and_evidence_checks_passed'] else 1


if __name__=='__main__':raise SystemExit(main())
