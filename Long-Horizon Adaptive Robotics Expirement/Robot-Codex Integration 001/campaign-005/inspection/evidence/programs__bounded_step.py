"""One protected command, queried to terminal, followed by an explicit capture.

No command retries, no automatic next motion, and no grasp/placement claims.
Caller must review returned evidence before invoking another motion. Terminal
manual commands can retain unknown host verification despite fresh observations.
Invoke from the workspace: python3 -B programs/bounded_step.py ID '{...action...}'
Read-only summary: python3 -B programs/bounded_step.py status
Capture only: python3 -B programs/bounded_step.py capture NEW_CAPTURE_ID
Evidence is appended to notes/bounded-step-epoch-EPOCH.jsonl. Reconcile any
interrupted ID. Older first-invocation evidence remains in notes/c1-evidence.jsonl.
"""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robot import Client, ClientError

LOG_PATH = ROOT / 'notes/bounded-step-client-errors.jsonl'


def record(kind, value):
    with LOG_PATH.open('a') as stream:
        stream.write(json.dumps({'kind': kind, 'value': value}) + '\n')


def summary(s):
    p = s.get('packet', {})
    return {**{k: s.get(k) for k in ('owner', 'authority_epoch', 'order_version', 'observation_sequence', 'observation_age_s', 'active_command', 'unresolved_commands', 'history_high_water', 'robot_action_budget')},
            'unresolved_commands': [{k: x.get(k) for k in ('request_id', 'phase', 'status', 'verification')} for x in s.get('unresolved_commands', []) if x.get('envelope', {}).get('authority_epoch') == s.get('authority_epoch') or x.get('phase') != 'terminal'],
            **{k: p.get(k) for k in ('sim_time', 'capture_sim_time_s', 'order', 'tcp_position_m', 'joints', 'joint_velocities', 'gripper', 'detections', 'station', 'last_feedback')}}


def terminal(c, rid, seconds=12):
    until = time.monotonic() + seconds
    while True:
        reply = c.query(rid)
        if reply.get('command', {}).get('phase') == 'terminal':
            record('terminal', reply)
            return reply
        if time.monotonic() >= until:
            record('unresolved_query', reply)
            raise RuntimeError('Request still unresolved: ' + rid + '; query before any subsequent action')
        time.sleep(.15)


def main():
    global LOG_PATH
    c = Client(ROOT)
    LOG_PATH = ROOT / ('notes/bounded-step-epoch-' + str(c.fence.authority_epoch) + '.jsonl')
    s = c.status()
    record('status_before', s)
    if sys.argv[1] == 'status':
        print(json.dumps(summary(s)))
        return
    if sys.argv[1] == 'capture':
        rid = sys.argv[2]
        record('observe_request', c.observe(rid))
        view = terminal(c, rid)
        print(json.dumps({'capture': view}), flush=True)
        s = c.status()
        record('status_after', s)
        print(json.dumps({'status_after': summary(s)}))
        return
    rid, action = sys.argv[1], json.loads(sys.argv[2])
    if s.get('owner') != 'robot' or s.get('active_command') or any(x.get('phase') != 'terminal' or x.get('status') not in ('completed', 'rejected') for x in s.get('unresolved_commands', [])):
        raise RuntimeError('Authority or unresolved-command precondition failed')
    if s['packet']['station']['busy']:
        raise RuntimeError('Station is busy')
    record('intended_action', {'request_id': rid, 'action': action, 'authority_epoch': s['authority_epoch'], 'order_version': s['order_version']})
    reply = c.command(rid, action)
    record('dispatch_reply', reply)
    print(json.dumps({'dispatch': reply}), flush=True)
    done = terminal(c, rid)
    print(json.dumps({'terminal': done}), flush=True)
    if done.get('command', {}).get('status') != 'completed':
        print(json.dumps({'status_after': summary(c.status())}))
        sys.exit(3)
    observe_id = rid + '-view'
    record('observe_request', c.observe(observe_id))
    view = terminal(c, observe_id)
    print(json.dumps({'capture': view}), flush=True)
    s = c.status()
    record('status_after', s)
    print(json.dumps({'status_after': summary(s)}))


if __name__ == '__main__':
    try:
        main()
    except ClientError as exc:
        record('client_error', exc.document())
        print(json.dumps(exc.document()))
        sys.exit(4 if exc.unknown else 3)
