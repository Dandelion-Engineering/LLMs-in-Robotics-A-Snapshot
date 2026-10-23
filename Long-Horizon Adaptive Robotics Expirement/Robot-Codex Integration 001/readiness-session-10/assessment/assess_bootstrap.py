"""Independent retained-file/bootstrap assessment; no model, simulator or WSL calls."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import zipfile

BOOTSTRAP = 'Follow the instructions in RobotAgentPrompt.md.'
REQUIRED_READS = ('RobotAgentPrompt.md', 'Tasks.md', 'Robot.md', 'Tools.md',
                  'live/activation.json', 'live/state.json', 'Continuity.md', 'live/events.jsonl')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def snapshot(raw):
    """Validate actual retained bytes, retaining the distinction from raw hashes."""
    contents, failures = {}, []
    for name, item in raw.get('files', {}).items():
        try:
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('invalid relative file name')
            data = base64.b64decode(item['base64'], validate=True)
            if sha(data) != item['retained_sha256']:
                raise ValueError('retained bytes do not match retained hash')
            if item['sha256'] == item['retained_sha256'] and len(data) != item['bytes']:
                raise ValueError('raw byte count mismatch')
            contents[name] = data
        except (KeyError, TypeError, ValueError) as error:
            failures.append({'file': name, 'error': str(error)})
    if not contents:
        failures.append({'error': 'no retained files'})
    if sum(item.get('bytes', -1) for item in raw.get('files', {}).values()) != raw.get('total_bytes'):
        failures.append({'error': 'total raw bytes do not match file inventory'})
    return contents, failures


def parsed_objects(text):
    try:
        value = json.loads(text)
        return [value] if isinstance(value, dict) else []
    except ValueError:
        result = []
        for line in text.splitlines():
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    result.append(value)
            except ValueError:
                pass
        return result


def startup_read_evidence(commands, hashes, contents, source_zip):
    expected = dict(contents)
    with zipfile.ZipFile(source_zip) as archive:
        candidates = [name for name in archive.namelist() if name.endswith('/smoke-template/Continuity.md')]
        if len(candidates) == 1:
            raw = archive.read(candidates[0]).decode('utf-8').replace('\r\n', '\n').encode()
            if sha(raw) == hashes.get('Continuity.md'):
                expected['Continuity.md'] = raw
    reads = {}
    for name in REQUIRED_READS:
        matches = []
        target_hash = hashes.get(name)
        for item in commands:
            actions = item.get('commandActions', [])
            explicit_read = any(a.get('type') == 'read' and a.get('path') in ('/workspace/' + name, name) for a in actions)
            command = item.get('command', '') + '\n' + '\n'.join(a.get('command', '') for a in actions)
            if not explicit_read and name not in command:
                continue
            output = item.get('aggregatedOutput', '').encode()
            if target_hash and sha(output) == target_hash:
                matches.append({'item_id': item['id'], 'match': 'complete_output_sha256'})
            elif (name in expected and sha(expected[name]) == target_hash
                  and expected[name] and expected[name] in output):
                matches.append({'item_id': item['id'], 'match': 'exact_input_bytes_within_combined_output',
                                'input_sha256': target_hash})
        reads[name] = {'verified': bool(matches), 'evidence': matches, 'expected_sha256': target_hash}
    return reads


def check_retirement(record):
    observations = record.get('observations', [])
    final = observations[-1] if observations else {}
    return (record.get('qualified') is True and final.get('retired') is True
            and final.get('namespace_evidence_available') is True
            and bool(final.get('namespace_ids')) and final.get('namespace_members') == []
            and final.get('outer_same_process') is False)


def assess(evidence, queue_receipt, frozen_snapshot, expected_job_id=None):
    receipt = read_json(queue_receipt)
    job = receipt.get('job', receipt)
    # This check deliberately precedes every attempted-result read.
    if job.get('state') != 'succeeded' or job.get('exit_status') != 0:
        raise ValueError('Actual queue receipt must be succeeded with exit_status 0 before assessment')
    if expected_job_id is not None and job.get('id') != expected_job_id:
        raise ValueError('Queue ID does not match the declared attempt')
    root = Path(evidence)
    frozen = read_json(frozen_snapshot)
    source_zip = Path(frozen_snapshot).with_name('code.zip')
    manifest_path = Path(frozen_snapshot).with_name('manifest.json')
    manifest = read_json(manifest_path)
    before = read_json(root / 'runtime-before-close.json')
    after = read_json(root / 'runtime-after-close.json')
    contents, before_problems = snapshot(before)
    after_contents, after_problems = snapshot(after)
    hashes = read_json(root / 'runtime-input-hashes.json')
    client = read_json(root / 'client/result.json')
    launch = read_json(root / 'client/launch.json')
    outer = read_json(root / 'orchestration-result.json')
    location = read_json(root / 'runtime-location.json')
    events = [json.loads(line) for line in (root / 'client/events.jsonl').read_text(encoding='utf-8').splitlines()]
    items = [event['params']['item'] for event in events if event.get('method') == 'item/completed']
    commands = [item for item in items if item.get('type') == 'commandExecution' and item.get('exitCode') == 0]
    reads = startup_read_evidence(commands, hashes, contents, source_zip)
    initial_canary = read_json(root / 'canary-stdout.json')
    codehost = read_json(root / 'codehost-canary-stdout.json')
    saved_boundary = json.loads(contents.get('notes/boundary-observation.json', b'{}'))
    observed = json.loads(contents.get('notes/bootstrap-observation.json', b'{}'))
    actual_canaries = []
    for command in commands:
        for obj in parsed_objects(command.get('aggregatedOutput', '')):
            if obj.get('qualified') is True and isinstance(obj.get('checks'), dict):
                actual_canaries.append({'item_id': command['id'], 'result': obj})
    expected_fields = {'task_id': 'bootstrap-smoke-001', 'activation_id': 'BOOTSTRAP-A-913',
                       'runtime_generation': 1, 'robot_identifier': 'NO-ACTUATOR-BOOTSTRAP-173',
                       'public_history_event_id': 11, 'continuity_marker': 'BOOT-READ-4827'}
    observation_checks = {name: observed.get(name) == value for name, value in expected_fields.items()}
    continuity = contents.get('.continuity/Continuity.md', b'')
    retirements = {path.name: read_json(path) for path in root.glob('*-retirement.json')}
    retirement_checks = {name: check_retirement(value) for name, value in retirements.items()}
    bridge_files = list(root.glob('codehost-*-bridge.json'))
    bridges = {p.name: read_json(p) for p in bridge_files}
    turn_requests = [event for event in events if event.get('kind') == 'request' and event.get('method') == 'turn/start']
    shutdowns = [event for event in events if event.get('kind') == 'client_shutdown']
    broker = [json.loads(line) for line in (root / 'broker-events.jsonl').read_text(encoding='utf-8').splitlines()]
    command_registry = read_json(root / 'control/protected/command-registry.json')
    immutable_names = [name for name in REQUIRED_READS if name != 'Continuity.md']
    codehost_checks = codehost.get('checks', {})
    checks = {
        'queue_succeeded_exit0': True,
        'manifest_matches_frozen_hash_and_run': sha(manifest_path.read_bytes()) == frozen['manifest_sha256'] and manifest['run_id'] == frozen['run_id'],
        'manifest_one_nonactuating_development_turn': manifest.get('physical_simulation') is False and manifest.get('model_turns_max') == 1 and manifest.get('stage') == 'development-only',
        'exact_sole_turn_bootstrap': len(turn_requests) == 1 and turn_requests[0]['params'].get('input') == [{'type':'text','text':BOOTSTRAP,'text_elements':[]}],
        'launch_exact_bootstrap_workspace': launch.get('bootstrap') == BOOTSTRAP and launch.get('bootstrap_requested') is True and launch.get('remote_cwd') == 'file:///workspace',
        'effective_chatgpt_astra_max': client.get('auth_type') == 'chatgpt' and client.get('model_effective') == 'gpt-6-astra' and client.get('effort_effective') == 'max',
        'actual_model_turn_completed': client.get('success') is True and client.get('model_started') is True and client.get('turn_status') == 'completed',
        'client_shutdown_exit0': len(shutdowns) == 1 and shutdowns[0].get('exit_code') == 0,
        'outer_launcher_completed_cleanly': outer.get('success') is True and not any(name in outer for name in ('error','export_error','post_close_export_error')),
        'ambient_context_disabled': client.get('instruction_sources') == [] and client.get('mcp_active_servers') == [] and client.get('effective_config', {}).get('web_search') == 'disabled',
        'all_eight_startup_reads_proven_by_tool_output': all(value['verified'] for value in reads.values()),
        'immutable_startup_files_unchanged': all(name in contents and sha(contents[name]) == hashes[name] for name in immutable_names),
        'positive_protected_controls_exist': all(location['setup']['protected_exist'].values()) and len(location['setup']['protected_exist']) == 4 and location['setup'].get('outside_loopback_control') is True,
        'outer_canary_all_45': initial_canary.get('qualified') is True and len(initial_canary.get('checks', {})) == 45 and all(v is True for v in initial_canary['checks'].values()),
        'model_canary_output_saved_exactly': any(item['result'] == saved_boundary for item in actual_canaries),
        'model_canary_same_45_checks_pass': set(saved_boundary.get('checks', {})) == set(initial_canary.get('checks', {})) and saved_boundary.get('qualified') is True and all(v is True for v in saved_boundary.get('checks', {}).values()),
        'codehost_has_no_ambient_apis_or_tools': codehost.get('host_qualified') is True and codehost_checks.get('all_tools_count') == 0 and codehost_checks.get('tools') == [] and all(v == 'undefined' for v in codehost_checks.get('apis', {}).values()) and all(v == 'denied' for v in codehost_checks.get('imports', {}).values()),
        'observed_fixture_fields_correct': all(observation_checks.values()),
        'continuity_updated_from_initial': bool(continuity) and sha(continuity) != hashes.get('Continuity.md') and b'bootstrap-observation' in continuity,
        'raw_file_exports_self_consistent': not before_problems and not after_problems,
        'all_retained_file_bytes_survive_teardown': before == after and contents == after_contents,
        'persistent_runtime_backing': location.get('durable_backing') is True and location.get('run', '').startswith('/var/tmp/robot-codex-session10/'),
        'both_executor_and_codehost_namespaces_retired': len(retirements) >= 3 and any(name.startswith('executor-') for name in retirements) and any(name.startswith('codehost-') for name in retirements) and all(retirement_checks.values()),
        'codehost_shutdown_transport_clean': bool(bridges) and all(value.get('pump_errors') == [] for value in bridges.values()),
        'no_actuator_commands_or_mutating_broker_requests': command_registry == {} and bool(broker) and all(event.get('method') == 'GET' for event in broker),
    }
    relevant = [root / 'client/events.jsonl', root / 'client/result.json', root / 'orchestration-result.json',
                root / 'runtime-before-close.json', root / 'runtime-after-close.json', root / 'runtime-input-hashes.json',
                Path(queue_receipt), Path(frozen_snapshot), source_zip, manifest_path]
    return {'schema': 'robot-codex-bootstrap-assessment-1', 'run_id': manifest['run_id'],
            'queue_job_id': job.get('id'), 'bootstrap_passed': all(checks.values()), 'checks': checks,
            'startup_reads': reads, 'observed_fixture_checks': observation_checks,
            'observed_fixture': observed, 'retirement_checks': retirement_checks,
            'snapshot_integrity_problems': {'before': before_problems, 'after': after_problems},
            'retained_files': len(contents), 'raw_total_bytes': before.get('total_bytes'),
            'model_canary_item_ids': [item['item_id'] for item in actual_canaries],
            'evidence_sha256': {str(path): sha(path.read_bytes()) for path in relevant},
            'assessment_code_sha256': sha(Path(__file__).read_bytes()), 'model_calls_in_assessment': 0,
            'scope': 'Actual nonactuating bootstrap and normal-shutdown retention; does not qualify physical recovery, client-failure retention, full-host restart or scored performance.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--queue-receipt', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--job-id')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    result = assess(args.evidence, args.queue_receipt, args.snapshot, args.job_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'bootstrap_passed': result['bootstrap_passed'], 'failed_checks': [name for name, passed in result['checks'].items() if not passed], 'output': str(args.output)}))
    return 0 if result['bootstrap_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
