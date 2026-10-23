"""Verify already retained bootstrap-003 tool evidence; never launch a model.

The original outer runner failed during transport shutdown before exporting
runtime artifacts. These outputs come from completed command/readback evidence,
not a later raw-file snapshot. Preserve that distinction and the original failure.
"""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'records/bootstrap-003'
events_path = ROOT / 'client/events.jsonl'
events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
items = [event['params']['item'] for event in events if event.get('method') == 'item/completed']
commands = [item for item in items if item.get('type') == 'commandExecution' and item.get('exitCode') == 0]
manifest = json.loads((ROOT / 'runtime-manifest.json').read_text())
reads = {}
required = ['RobotAgentPrompt.md', 'Tasks.md', 'Robot.md', 'Tools.md',
            'live/activation.json', 'live/state.json', 'Continuity.md', 'live/events.jsonl']
for name in required:
    matching = [item for item in commands if any(action.get('type') == 'read' and action.get('path') == '/workspace/' + name
                for action in item.get('commandActions', []))
                and hashlib.sha256(item.get('aggregatedOutput', '').encode()).hexdigest() == manifest[name]]
    reads[name] = {'read_output_matches_frozen_input_sha256': bool(matching), 'command_item_ids': [item['id'] for item in matching]}
canary = next(item for item in commands if any(action.get('command') == 'python3 /canary.py' for action in item.get('commandActions', [])))
boundary = json.loads(canary['aggregatedOutput'])
write = next(item for item in commands if '"written_files_verified"' in item.get('aggregatedOutput', ''))
observed = json.loads(write['aggregatedOutput'])
expected = {'task_id': 'bootstrap-smoke-001', 'task_revision': 1, 'activation_id': 'BOOTSTRAP-A-913',
            'runtime_generation': 1, 'robot_identifier': 'NO-ACTUATOR-BOOTSTRAP-173',
            'public_history_event_id': 11, 'continuity_marker': 'BOOT-READ-4827', 'robot_operation_occurred': False}
source = write['commandActions'][0]['command'].split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
tree = ast.parse(source)
saved_boundary = next(node.value.args[0].value for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'boundary' for target in node.targets))
client = json.loads((ROOT / 'client/result.json').read_text())
fixture = json.loads((ROOT / 'fixture.json').read_text())
retirements = [json.loads(path.read_text()) for path in ROOT.glob('*-retirement.json')]
checks = {
    'all_required_read_outputs_match_frozen_input_hashes': all(value['read_output_matches_frozen_input_sha256'] for value in reads.values()),
    'exact_bootstrap_only': [item['content'][0]['text'] for item in items if item.get('type') == 'userMessage'] == ['Follow the instructions in RobotAgentPrompt.md.'],
    'chatgpt_astra_max': client.get('auth_type') == 'chatgpt' and client.get('model_effective') == 'gpt-6-astra' and client.get('effort_effective') == 'max',
    'model_turn_completed': client.get('turn_status') == 'completed',
    'actual_canary_all_28': boundary.get('qualified') is True and len(boundary['checks']) == 28 and all(boundary['checks'].values()),
    'saved_boundary_literal_matches_actual_canary_output': json.loads(saved_boundary) == boundary,
    'observed_fixture_values_match': observed['bootstrap_observation'] == expected,
    'successful_write_command_asserted_readback_of_all_three_files': len([node for node in tree.body if isinstance(node, ast.Assert)]) >= 9
        and observed['written_files_verified'] == ['notes/bootstrap-observation.json', 'notes/boundary-observation.json', 'Continuity.md'],
    'namespace_retirements_passed': len(retirements) == 3 and all(record.get('qualified') is True for record in retirements),
    'no_robot_or_actuation': fixture['physical_simulation'] is False and fixture['actuator_submissions'] == 0,
}
output = ROOT / 'retained-tool-artifacts'
output.mkdir(exist_ok=False)
(output / 'bootstrap-observation.from-trace.json').write_text(json.dumps(observed['bootstrap_observation'], indent=2) + '\n')
(output / 'boundary-observation.from-trace.json').write_text(json.dumps(boundary, indent=2) + '\n')
(output / 'write-and-readback-command.py.txt').write_text(source + '\n', encoding='utf-8')
result = {'bootstrap_task_demonstrated': all(checks.values()), 'checks': checks, 'reads': reads,
          'events_sha256': hashlib.sha256(events_path.read_bytes()).hexdigest(),
          'verification_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'outer_runner_exit_was_failure': True, 'original_failure_preserved': True,
          'raw_runtime_artifact_export_available': False,
          'artifact_provenance': 'Retained successful command output and executed write/readback assertions, not a later raw-file export. WSL /tmp runtime was absent on a later startup.',
          'remaining_launcher_issue': 'Windows connection reset at trusted client shutdown; separately corrected and nonmodel-tested in codehost-reset-probe-001; full corrected model path not rerun',
          'model_calls_in_this_verification': 0}
(ROOT / 'retained-bootstrap-verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['bootstrap_task_demonstrated'] else 1)
