"""Independent reading of protected native lifecycle receipts; no native calls.

Cleanup input hashes describe source-bound parser observations. They are not
reconstructed native payloads, model outputs, or proof of remote tool success.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

import cleanup_transport

REPO = Path(__file__).resolve().parents[4]
INTEGRATION = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/'
CAMPAIGN = INTEGRATION + 'campaign-002/'
SOURCE_NAMES = tuple(CAMPAIGN + name for name in (
    'harness/bootstrap_client_v4.py', 'harness/native_quiescence.py',
    'harness/transport_stderr.py', 'assessment/client_quiescence.py',
    'io-repair/NATIVE_THREAD_QUIESCENCE_V1.md',
    'io-repair/NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md',
    'io-repair/codehost-channel-source-001/codex-rs__core__src__config__mod.rs',
    'io-repair/native-output-source-002/codex-rs__app-server__src__request_processors__thread_lifecycle.rs',
    'io-repair/native-output-source-002/codex-rs__app-server__src__thread_state.rs',
)) + tuple(INTEGRATION + 'isolation-session-9/native/app-server-schema/v2/' + name + '.json'
           for name in ('ThreadUnsubscribeResponse', 'TurnInterruptResponse', 'ThreadClosedNotification',
                        'TurnInterruptParams', 'ThreadUnsubscribeParams', 'ThreadStartResponse',
                        'TurnStartResponse', 'TurnCompletedNotification'))
SOURCE_NAMES += tuple(CAMPAIGN + 'io-repair/native-unsubscribe-source-001/' + name for name in (
    'codex-rs__app-server__src__lib.rs', 'codex-rs__app-server__src__outgoing_message.rs',
    'codex-rs__app-server__src__request_processors__thread_processor.rs',
    'codex-rs__app-server__src__transport.rs', 'codex-rs__config__src__config_toml.rs',
    'source-evidence.json', 'analysis.json', 'analysis.md'))
UNLOAD_KEY = 'thread_unload_delay_secs'
SCHEMA = 'campaign002-native-quiescence-1'
SCHEMA2 = 'campaign002-native-quiescence-2'
EVENT_SCHEMA = 'campaign002-native-quiescence-event-1'
TERMINAL = frozenset(('completed', 'interrupted', 'failed'))
BASE = {'kind', 'schema', 'sequence', 'phase', 'wall_unix_s', 'monotonic_s'}


def require(value, message):
    if value is not True:
        raise ValueError('Native quiescence: ' + message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,256}', value) is not None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, 'duplicate JSON key')
        value[key] = item
    return value


def decode(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def read(root, name, bindings, maximum):
    path = root / name
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum,
            'missing, linked or oversized ' + name)
    raw = path.read_bytes()
    require(0 < len(raw) <= maximum and raw.endswith(b'\n'), 'incomplete or oversized ' + name)
    bindings[name] = {'bytes': len(raw), 'sha256': digest(raw)}
    return raw


def source_bindings(frozen, repo):
    require(isinstance(frozen, dict) and isinstance(frozen.get('sources'), dict), 'snapshot missing')
    result = {}
    names = SOURCE_NAMES
    if cleanup_transport.METHOD in frozen['sources']:
        names = tuple(dict.fromkeys(names + cleanup_transport.SOURCE_NAMES))
    for name in names:
        path = repo / name
        require(path.is_file() and not path.is_symlink(), 'source missing: ' + name)
        raw = path.read_bytes()
        value = {'bytes': len(raw), 'sha256': digest(raw)}
        expected = frozen['sources'].get(name)
        require(isinstance(expected, dict) and type(expected.get('bytes')) is int and expected == value,
                'source differs from snapshot: ' + name)
        result[name] = value
    return result


def original_lifecycle(rows, start_index, receipt):
    """Bind retained identities to original, earlier successful native responses."""
    ordinary = [(i, r) for i, r in enumerate(rows) if r.get('kind') in ('request', 'response')]
    require(all(i < start_index for i, _ in ordinary), 'ordinary native control after cleanup started')
    requests = [(i, r) for i, r in ordinary if r['kind'] == 'request']
    ids = [r.get('id') for _, r in requests]
    require(all(type(x) is int and x > 0 for x in ids) and ids == sorted(set(ids)),
            'ordinary request IDs missing, duplicated or reordered')
    require(not any(r.get('method') in ('turn/interrupt', 'thread/unsubscribe') for _, r in requests),
            'uncontrolled lifecycle request')
    responses = [(i, r) for i, r in ordinary if r['kind'] == 'response']
    response_ids = [r.get('id') for _, r in responses]
    require(all(type(x) is int and x in ids for x in response_ids)
            and len(response_ids) == len(set(response_ids)), 'original response identity differs')
    entry = receipt['entry']
    for field, method in (('thread', 'thread/start'), ('turn', 'turn/start')):
        req = [(i, r) for i, r in requests if r.get('method') == method]
        res = [(i, r) for i, r in responses if r.get('method') == method]
        wanted = receipt[field + '_id']
        require(len(req) <= 1 and len(res) <= 1 and entry[field + '_start_requested'] == bool(req),
                'original ' + field + ' creation cardinality differs')
        if not req:
            require(not res and wanted is None, 'unrequested native ' + field + ' identity')
            continue
        require(wanted is not None and len(res) == 1, 'partial native ' + field + ' creation')
        i, request = req[0]; j, response = res[0]
        require(i < j < start_index and request['id'] == response.get('id')
                and 'error' not in response and isinstance(response.get('result'), dict)
                and isinstance(response['result'].get(field), dict)
                and response['result'][field].get('id') == wanted,
                'original ' + field + ' response correlation differs')
        if field == 'turn':
            require(isinstance(request.get('params'), dict)
                    and request['params'].get('threadId') == receipt['thread_id'],
                    'original turn targets a different thread')
            thread_res = next(j for j, r in responses if r.get('method') == 'thread/start')
            require(thread_res < i, 'turn precedes established thread')
    lifecycle = [(i, r) for i, r in enumerate(rows) if r.get('kind') == 'notification'
                 and r.get('method') in ('turn/completed', 'thread/closed')]
    require(all(i < start_index for i, _ in lifecycle), 'unjoined native lifecycle notification during cleanup')
    require(not any(r['method'] == 'thread/closed' for _, r in lifecycle), 'thread closed before controlled unsubscribe')
    terminal = [r for _, r in lifecycle if r['method'] == 'turn/completed']
    require(len(terminal) <= 1, 'duplicate original terminal notification')
    for row in terminal:
        params = row.get('params'); turn = params.get('turn') if isinstance(params, dict) else None
        require(isinstance(turn, dict) and params.get('threadId') == receipt['thread_id']
                and turn.get('id') == receipt['turn_id'] and turn.get('status') in TERMINAL,
                'original terminal identity or status differs')
    status = entry['turn_terminal_status']
    if status is not None:
        require(len(terminal) == 1 and terminal[0]['params']['turn']['status'] == status,
                'entry terminal state lacks matching original notification')
    # A queued terminal already logged by ordinary receive cannot be silently
    # claimed as a new cleanup input or ignored in a qualifying proof.
    else:
        require(not terminal, 'unreconciled original terminal notification')
    return max(ids, default=0)


def _verify_client_quiescence(stage_root, frozen, *, repo=None):
    """Return a bound successful proof or raise ValueError. No fallback proof."""
    root = Path(stage_root); bindings = {}
    sources = source_bindings(frozen, Path(repo) if repo is not None else REPO)
    receipt = decode(read(root, 'client/native-quiescence.json', bindings, 128 * 1024))
    events_raw = read(root, 'client/events.jsonl', bindings, 32 * 1024 * 1024)
    rows = [decode(line) for line in events_raw.splitlines()]
    require(all(isinstance(row, dict) for row in rows), 'nonobject native event')
    result = decode(read(root, 'client/result.json', bindings, 4 * 1024 * 1024))
    require(isinstance(result, dict) and result.get('native_quiescence') == receipt,
            'ordinary result does not preserve exact cleanup receipt')
    launch = decode(read(root, 'client/launch.json', bindings, 4 * 1024 * 1024))
    preflight = decode(read(root, 'client/preflight.json', bindings, 4 * 1024 * 1024))
    # These fixed protected projections are emitted by the source-bound bootstrap;
    # they are not reconstructed config/read payloads or a shutdown acknowledgment.
    for label, document, field in (('launch', launch, 'config_overrides'),
                                    ('preflight', preflight, 'effective_config'),
                                    ('result', result, 'effective_config')):
        config = document.get(field) if isinstance(document, dict) else None
        value = config.get(UNLOAD_KEY) if isinstance(config, dict) else None
        require(type(value) is int and value == 0,
                label + ' unload scheduling must be exact integer zero')
    expected_keys = {'schema','thread_id','turn_id','entry','start_monotonic_s',
        'graceful_deadline_monotonic_s','hard_deadline_monotonic_s','controls','terminal_turn',
        'thread_closed','handshake_qualified','finishing_recorded','stdin_closed','forced_job_close',
        'native_exit_code','native_exit_monotonic_s','completed_monotonic_s','qualified',
        'ignored_notifications','failures','events'}
    phase_enabled = cleanup_transport.METHOD in sources
    if phase_enabled:
        expected_keys.add('cleanup_barrier')
    require(isinstance(receipt, dict) and set(receipt) == expected_keys
            and receipt['schema'] == (SCHEMA2 if phase_enabled else SCHEMA),
            'receipt schema differs')
    require(all(receipt[x] is True for x in ('qualified','handshake_qualified','finishing_recorded','stdin_closed'))
            and receipt['forced_job_close'] is False and receipt['failures'] == []
            and type(receipt['native_exit_code']) is int and receipt['native_exit_code'] == 0,
            'failed, forced, incomplete or nonzero cleanup')
    require(type(receipt['ignored_notifications']) is int and 0 <= receipt['ignored_notifications'] <= 32*1024*1024,
            'notification count malformed')
    for field in ('thread_id', 'turn_id'):
        require(receipt[field] is None or identifier(receipt[field]), 'native identity malformed')
    entry = receipt['entry']
    require(isinstance(entry, dict) and set(entry) == {'thread_start_requested','turn_start_requested','turn_terminal_status'}
            and all(type(entry[x]) is bool for x in ('thread_start_requested','turn_start_requested'))
            and (entry['turn_terminal_status'] is None or entry['turn_terminal_status'] in TERMINAL),
            'entry state malformed')
    require(receipt['turn_id'] is None or receipt['thread_id'] is not None, 'turn lacks thread')
    if receipt['turn_id'] is None:
        require(entry['turn_terminal_status'] is None, 'terminal state without turn')
    start, grace, hard = (receipt[k] for k in ('start_monotonic_s','graceful_deadline_monotonic_s','hard_deadline_monotonic_s'))
    require(all(finite(x) for x in (start, grace, hard)) and grace == start+5 and hard == start+10,
            'absolute cleanup budgets differ')
    selected = [(i, row) for i, row in enumerate(rows) if row.get('kind') == 'native_quiescence']
    events = receipt['events']
    require(isinstance(events, list) and 6 <= len(events) <= 24
            and [r for _, r in selected] == events, 'event receipt projection differs or exceeds bounds')
    prev = start
    fields = {
        'start': {'thread_id','turn_id','entry','start_monotonic_s','graceful_deadline_monotonic_s','hard_deadline_monotonic_s'},
        'request': {'method','request_id','thread_id','turn_id','wire_bytes','wire_sha256'},
        'request_sent': {'method','request_id'},
        'response': {'method','request_id','status','input_bytes','input_sha256'},
        'turn_terminal': {'thread_id','turn_id','status','source','input_bytes','input_sha256'},
        'thread_closed': {'thread_id','input_bytes','input_sha256'},
        'handshake_complete': {'qualified'}, 'finishing': {'recorded'}, 'stdin_closed': set(),
        'native_exit': {'exit_code','observed_monotonic_s'}, 'completed': {'qualified'},
    }
    if phase_enabled:
        fields['cleanup_barrier_complete'] = {'receipt'}
    for n, event in enumerate(events, 1):
        phase = event.get('phase')
        require(phase in fields and set(event) == BASE | fields[phase]
                and event['schema'] == EVENT_SCHEMA and type(event['sequence']) is int and event['sequence'] == n
                and finite(event['wall_unix_s']) and finite(event['monotonic_s'])
                and prev <= event['monotonic_s'] <= hard, 'event shape, sequence or time differs')
        prev = event['monotonic_s']
        if 'input_bytes' in event:
            require(type(event['input_bytes']) is int and 0 < event['input_bytes'] <= 32*1024*1024
                    and isinstance(event['input_sha256'], str)
                    and re.fullmatch('[0-9a-f]{64}',event['input_sha256']) is not None,
                    'protected cleanup input identity malformed')
    require(events[0]['phase'] == 'start' and all(events[0][key] == receipt[key] for key in
            ('thread_id','turn_id','entry','start_monotonic_s','graceful_deadline_monotonic_s','hard_deadline_monotonic_s')),
            'start event differs from receipt')
    last_id = original_lifecycle(rows, selected[0][0], receipt)
    expected_methods = []
    if receipt['thread_id'] is not None:
        if receipt['turn_id'] is not None and entry['turn_terminal_status'] is None:
            expected_methods.append('turn/interrupt')
        expected_methods.append('thread/unsubscribe')
    controls = receipt['controls']
    require(isinstance(controls, list) and all(isinstance(c, dict) for c in controls)
            and [c.get('method') for c in controls] == expected_methods,
            'control sequence differs from established entry state')
    barrier_needed = phase_enabled and bool(controls)
    require(len(events) == 6 + 4*len(controls) + int(barrier_needed), 'cleanup event cardinality differs')
    if phase_enabled and not controls:
        require(receipt['cleanup_barrier'] is None, 'no-thread cleanup invented a barrier')
    pos = 1; terminal = None; closed = None
    if entry['turn_terminal_status'] is not None:
        terminal = {'thread_id':receipt['thread_id'],'turn_id':receipt['turn_id'],
                    'status':entry['turn_terminal_status'],'source':'entry','monotonic_s':start}
    for offset, control in enumerate(controls,1):
        method = control['method']; request_id = last_id+offset
        require(set(control) == {'method','request_id','sent_monotonic_s','response_monotonic_s','response_status'}
                and type(control['request_id']) is int and control['request_id'] == request_id,
                'control request ID or shape differs')
        request = events[pos]
        if barrier_needed and offset == 1:
            barrier_event = events[pos+1]
            require(barrier_event['phase'] == 'cleanup_barrier_complete'
                    and barrier_event['receipt'] == receipt['cleanup_barrier'], 'barrier event projection differs')
            cleanup_transport.completion(receipt['cleanup_barrier'], receipt, request,
                                         barrier_event, control['sent_monotonic_s'])
            pos += 1
        sent = events[pos+1]
        require(request['phase']=='request' and sent['phase']=='request_sent'
                and request['method']==sent['method']==method
                and type(request['request_id']) is int and type(sent['request_id']) is int
                and request['request_id']==sent['request_id']==request_id
                and request['thread_id']==receipt['thread_id']
                and request['turn_id']==(receipt['turn_id'] if method=='turn/interrupt' else None),
                'cleanup request correlation differs')
        params={'threadId':receipt['thread_id']}
        if method=='turn/interrupt':params['turnId']=receipt['turn_id']
        wire=(json.dumps({'id':request_id,'method':method,'params':params})+'\n').encode()
        require(type(request['wire_bytes']) is int and request['wire_bytes']==len(wire)
                and request['wire_sha256']==digest(wire) and finite(control['sent_monotonic_s'])
                and request['monotonic_s']<=control['sent_monotonic_s']<=sent['monotonic_s'],
                'control wire identity or successful-send observation differs')
        replies=events[pos+2:pos+4]; notification='turn_terminal' if method=='turn/interrupt' else 'thread_closed'
        require(len(replies)==2 and {r['phase'] for r in replies}=={'response',notification},
                'missing, duplicate or unexpected cleanup acknowledgment')
        response=next(r for r in replies if r['phase']=='response'); note=next(r for r in replies if r['phase']==notification)
        status='empty' if method=='turn/interrupt' else 'unsubscribed'
        require(type(response['request_id']) is int and response['request_id']==request_id
                and response['method']==method and response['status']==control['response_status']==status
                and response['monotonic_s']==control['response_monotonic_s']
                and note['thread_id']==receipt['thread_id'], 'response or notification correlation differs')
        if method=='turn/interrupt':
            require(note['turn_id']==receipt['turn_id'] and note['status'] in TERMINAL and note['source']=='cleanup',
                    'terminal turn correlation differs')
            terminal={k:note[k] for k in ('thread_id','turn_id','status','source','monotonic_s')}
        else:
            closed={k:note[k] for k in ('thread_id','monotonic_s')}
        pos += 4
    require(receipt['terminal_turn']==terminal and receipt['thread_closed']==closed,
            'terminal or thread-closed receipt differs')
    tail=events[pos:]
    require([e['phase'] for e in tail]==['handshake_complete','finishing','stdin_closed','native_exit','completed']
            and tail[0]['qualified'] is True and tail[1]['recorded'] is True
            and type(tail[3]['exit_code']) is int and tail[3]['exit_code']==0 and tail[4]['qualified'] is True,
            'cleanup terminal phase order differs')
    require(tail[0]['monotonic_s'] <= grace and tail[2]['monotonic_s'] <= grace
            and finite(receipt['native_exit_monotonic_s'])
            and tail[2]['monotonic_s']<=receipt['native_exit_monotonic_s']<=grace
            and receipt['native_exit_monotonic_s']<=tail[3]['monotonic_s']
            and finite(tail[3]['observed_monotonic_s'])
            and tail[3]['observed_monotonic_s']==receipt['native_exit_monotonic_s']
            and finite(receipt['completed_monotonic_s'])
            and tail[3]['monotonic_s']<=receipt['completed_monotonic_s']<=tail[4]['monotonic_s']<=hard,
            'cleanup absolute phase deadlines differ')
    markers=[(i,r) for i,r in enumerate(rows) if r.get('kind')=='client_finishing_before_close']
    ends=[(i,r) for i,r in enumerate(rows) if r.get('kind')=='client_shutdown']
    require(len(markers)==len(ends)==1 and ends[0][0]==len(rows)-1
            and set(ends[0][1])=={'kind','exit_code'} and type(ends[0][1]['exit_code']) is int
            and ends[0][1]['exit_code']==0, 'ordinary final shutdown missing or differs')
    i,marker=markers[0]; positions={e['sequence']:index for index,e in selected}
    require(set(marker)=={'kind','schema','wall_unix_s','monotonic_s'}
            and marker['schema']=='campaign002-client-finishing-1'
            and finite(marker['wall_unix_s']) and finite(marker['monotonic_s'])
            and positions[tail[0]['sequence']] < i < positions[tail[1]['sequence']]
            and tail[0]['monotonic_s'] <= marker['monotonic_s'] <= tail[1]['monotonic_s']
            and positions[tail[-1]['sequence']] < ends[0][0],
            'durable finishing marker is outside handshake/stdin order')
    after=rows[selected[0][0]:]
    require(all(r.get('kind') in ('native_quiescence','client_finishing_before_close','client_shutdown','stderr')
                for r in after), 'unknown control or record during cleanup')
    proof = {'schema':'campaign002-client-quiescence-proof-1','passed':True,
            'thread_id':receipt['thread_id'],'turn_id':receipt['turn_id'],
            'entry':entry,'controls':expected_methods,'terminal_turn':terminal,'thread_closed':closed,
            'start_monotonic_s':start,'graceful_deadline_monotonic_s':grace,
            'hard_deadline_monotonic_s':hard,'completed_monotonic_s':receipt['completed_monotonic_s'],
            'events':len(events),'source_bindings':sources,'input_bindings':bindings,
            'unload_scheduling':{'requested_seconds':0,'verified_effective_seconds':0,
                                 'scope':'Fixed source-bound bootstrap projection; native config payload not retained.'},
            'scope':'Source-bound lifecycle acknowledgment and bounded native exit; remote cleanup and transport success require their independent gates.'}
    if phase_enabled:
        proof['cleanup_barrier'] = receipt['cleanup_barrier']
        proof['cleanup_transport'] = cleanup_transport.verify_client_barrier(
            root, receipt['cleanup_barrier'], bindings)
    return proof


def verify_client_quiescence(stage_root, frozen, *, repo=None):
    """Return a bound successful proof; malformed or failed evidence raises ValueError."""
    try:
        return _verify_client_quiescence(stage_root, frozen, repo=repo)
    except (KeyError, IndexError, TypeError, AttributeError, UnicodeError) as error:
        raise ValueError('Native quiescence: malformed evidence') from error
