"""Independently retain bootstrap outputs and require actual tool/file evidence."""
import json
import subprocess


def assess(fixture, client):
    # Fixed names only: do not follow agent-created symlinks outside runtime.
    script = r'''import pathlib,json,sys
root=pathlib.Path(sys.argv[1]); out={}
for name in ['notes/bootstrap-observation.json','notes/boundary-observation.json','Continuity.md']:
 p=root/name
 if p.is_symlink() or not p.resolve().is_relative_to(root) or not p.is_file():out[name]=None
 elif p.stat().st_size>1048576:out[name]=None
 else:out[name]=p.read_text()
print(json.dumps(out))
'''
    exported = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-c', script, fixture.workspace],
                              capture_output=True, text=True, encoding='utf-8', timeout=10)
    if exported.returncode:
        raise RuntimeError('Bootstrap artifact export failed')
    artifacts = json.loads(exported.stdout)
    output = fixture.evidence / 'bootstrap-artifacts'
    output.mkdir()
    for name, content in artifacts.items():
        if content is not None:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fixture.redact(content), encoding='utf-8')
    events = [json.loads(line) for line in (fixture.evidence / 'client/events.jsonl').read_text(encoding='utf-8').splitlines()]
    items = [event['params']['item'] for event in events if event.get('method') == 'item/completed']
    commands = [item for item in items if item.get('type') == 'commandExecution']
    observed = artifacts['notes/bootstrap-observation.json'] or ''
    continuity = artifacts['Continuity.md'] or ''
    try:
        observation = json.loads(observed)
    except ValueError:
        observation = None
    try:
        boundary = json.loads(artifacts['notes/boundary-observation.json'] or '')
    except ValueError:
        boundary = {}
    # These values are fixture facts, not a claim inferred from a final message.
    checks = {
        'transport_turn_completed': client.get('turn_status') == 'completed',
        'effective_astra_max_chatgpt': client.get('model_effective') == 'gpt-6-astra' and client.get('effort_effective') == 'max' and client.get('auth_type') == 'chatgpt',
        'actual_command_completed': any(item.get('exitCode') == 0 for item in commands),
        'observation_is_json_object': isinstance(observation, dict),
        'fixture_task_activation_marker_recorded': all(value in observed for value in ('bootstrap-smoke-001', 'BOOTSTRAP-A-913', 'BOOT-READ-4827')),
        'model_saved_all_28_boundary_checks': boundary.get('qualified') is True and len(boundary.get('checks', {})) == 28 and all(boundary['checks'].values()),
        'continuity_updated': bool(continuity) and continuity != fixture.files['Continuity.md'] and 'bootstrap-observation' in continuity,
        'no_actuation': len(fixture.adapter.submissions) == 0,
    }
    assessment = {'bootstrap_passed': all(checks.values()), 'checks': checks, 'completed_command_items': len(commands),
                  'final_messages': [item.get('text') for item in items if item.get('type') == 'agentMessage' and item.get('phase') == 'final_answer'],
                  'scope': 'Non-actuating exact bootstrap; file-read provenance is additionally inspectable in executor requests and command outputs'}
    (fixture.evidence / 'bootstrap-assessment.json').write_text(json.dumps(assessment, indent=2) + '\n', encoding='utf-8')
    return assessment
