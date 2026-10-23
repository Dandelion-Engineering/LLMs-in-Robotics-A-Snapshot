"""Read-only intervening checkpoint and native/recording inspection for Session 43."""
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import sys
import tomllib
import uuid

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
ROOT = PAIR / 'baseline'
PREVIOUS = Path(__file__).resolve().parents[1] / 'session-42/capture_health.py'
helpers = runpy.run_path(str(PREVIOUS))
receipt, prefix, ref, identity = (helpers[k] for k in ('receipt', 'prefix', 'ref', 'windows_identity'))
CODE = PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0, str(CODE))
from common import sha
from recording import verify_checkpoint, verify_prefix


def main():
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), observational_only=True,
                  development_session=43, checkpoints=[], sessions=[], errors=[])
    for number in (3, 4):
        item = dict(session=number, passed=False)
        try:
            executions = list(ROOT.glob(f'execution-*-{number:05}.json'))
            assert len(executions) == 1
            execution = receipt(executions[0])
            pointer = execution['value']['sessions'][-1]['ending']['checkpoint']
            checkpoint = ROOT / 'checkpoints' / f'session-{number:05}'
            assert Path(pointer['path']).resolve() == checkpoint.resolve()
            assert sha(checkpoint / 'manifest.json') == pointer['manifest_sha256']
            item.update(pointer=pointer, execution_reference=ref(executions[0], 'Retained boundary execution'),
                        checkpoint_readback=verify_checkpoint(checkpoint),
                        prefix_readback=verify_prefix(ROOT, checkpoint))
            state = json.loads((checkpoint / 'state.json').read_text(encoding='utf-8'))
            item.update(assignments_advanced=state['position'], normal_closed_sessions=state['sessions'],
                        simulation_time=state['world']['sim_time'], passed=True)
        except Exception as error:
            item['error'] = repr(error)
            result['errors'].append(dict(checkpoint=number, error=repr(error)))
        result['checkpoints'].append(item)
    result['events'], events = prefix(ROOT / 'events.jsonl')
    result['lifecycle'] = [row for row in events if row['kind'] in
        ('session_started', 'session_closed', 'boundary_checkpoint', 'task_success', 'resumed')]
    for number in (3, 4, 5, 6):
        session = ROOT / 'sessions' / f'session-{number:05}'
        item = dict(session=number, receipts={}, prefixes={})
        for name in ('native/client/preflight.json', 'native/client/result.json',
                     'native/canary.json', 'native/codehost-canary.json',
                     'native/codehost-native-owner-v3.json', 'native/executor-1-exit.json',
                     'native/codehost-owner-retirement-v3.json', 'workspace/cleanup-001.json',
                     'workspace/journal/native-exit.json'):
            path = session / name
            if path.exists():
                item['receipts'][name] = receipt(path)
        owner = item['receipts']['native/codehost-native-owner-v3.json']['value']
        item['windows_owner'] = identity(owner)
        if (session / 'closeout.json').exists():
            closeout = receipt(session / 'closeout.json')
            item['closeout'] = dict(reference=ref(session / 'closeout.json', 'Filesystem closeout'),
                                    passed=closeout['value']['passed'], report=closeout['value']['report'])
        for name in ('native/executor-1-capture.jsonl', 'native/broker-events.jsonl',
                     'workspace/journal/mutations.jsonl'):
            item['prefixes'][name] = prefix(session / name, include_last=False)[0]
        result['sessions'].append(item)
    index = receipt(ROOT / 'replay/index.json')
    last = index['value'][-1]
    result['replay'] = dict(index_sha256=index['sha256'], chunks=len(index['value']), last=last,
                            last_chunk_matches=sha(ROOT / 'replay' / last['file']) == last['sha256'])
    delivered = [row for row in events if row['kind'] == 'image_delivered'][-1]
    image = ref(ROOT / 'sensors' / f"frame-{delivered['payload']['sequence']:07}.png", 'Latest delivered sensor frame')
    result['sensor'] = dict(event=delivered, reference=image,
                            hash_matches=image['sha256'] == delivered['payload']['sha256'])
    result['monitoring'] = []
    for aid in ('apartment-v4-baseline-observations', 'apartment-v2-baseline-observations',
                'apartment-v2-maps-observations', 'apartment-v3-baseline-observations'):
        path = Path('C:/Users/cresp/.codex/automations') / aid / 'automation.toml'
        data = path.read_bytes()
        value = tomllib.loads(data.decode('utf-8'))
        result['monitoring'].append(dict(reference=ref(path, 'Monitor configuration'),
            **{k: value.get(k) for k in ('id', 'kind', 'status', 'rrule', 'target_thread_id')}))
    result['latest_checkpoint'] = receipt(ROOT / 'latest-checkpoint.json')
    result['completed_assignments'] = receipt(ROOT / 'checkpoints/session-00005/state.json')['value']['completed']
    result['sources'] = [ref(path, label) for path, label in (
        (Path(__file__), 'Read-only inspector'), (PREVIOUS, 'Read-only receipt and identity helpers'),
        (CODE / 'recording.py', 'Frozen checkpoint reader'),
        (PAIR / 'frozen_repository/source-manifest.json', 'Frozen source manifest'),
        (CODE / 'commissioning.json', 'Release certificate'))]
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    out = PAIR / 'operator/observations' / ('session43-progress-' + uuid.uuid4().hex + '.json')
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(evidence=str(out), sha256=sha(out), checkpoints=result['checkpoints'],
        windows=[item['windows_owner'] for item in result['sessions']], replay=result['replay'],
        sensor_hash_matches=result['sensor']['hash_matches'], errors=result['errors'])))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
