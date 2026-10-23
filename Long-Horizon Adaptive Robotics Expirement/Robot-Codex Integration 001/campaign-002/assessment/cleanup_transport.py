"""Independent metadata checks for the declared native cleanup phase.

Wire trace hashes are source-witnessed observations. This reader does not
reconstruct unretained payloads or attribute an HTTP/2 reset to an RPC.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

CAMPAIGN = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/'
METHOD = CAMPAIGN + 'io-repair/NATIVE_CLEANUP_CANCELLATION_V1.md'
SOURCE_NAMES = tuple(CAMPAIGN + name for name in (
    'io-repair/NATIVE_CLEANUP_CANCELLATION_V1.md',
    'assessment/cleanup_transport.py', 'assessment/client_quiescence.py',
    'assessment/transport_integrity_v3.py', 'harness/native_cleanup_protocol.py',
    'harness/native_quiescence.py', 'harness/codehost_bridge_v3.py',
    'harness/codehost_inside_v3.py', 'harness/codehost_mux_protocol.py',
    'harness/codehost_owner.py', 'harness/codehost_entry_v3.py',
))


def require(value, message):
    if value is not True:
        raise ValueError('Native cleanup transport: ' + message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def nonce(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{32}', value) is not None


def completion(value, receipt, request_event, event, sent_monotonic_s):
    """Check the controller's exact request/completion, without claiming a ledger join."""
    keys = {'schema', 'request', 'request_sha256', 'parent_barrier_record_sha256',
            'namespace_barrier_record_sha256', 'begin_payload_sha256', 'ack_payload_sha256',
            'parent_ack_record_sha256', 'parent_ack_sequence', 'completed_monotonic_s'}
    require(isinstance(value, dict) and set(value) == keys
            and value['schema'] == 'campaign002-native-cleanup-complete-1', 'completion schema')
    request = value['request']
    require(isinstance(request, dict) and set(request) == {'schema', 'nonce', 'thread_id', 'turn_id',
            'control_event', 'start_monotonic_s', 'graceful_deadline_monotonic_s', 'owner_receipt_sha256'}
            and request['schema'] == 'campaign002-native-cleanup-request-1'
            and nonce(request['nonce']) and digest(request['owner_receipt_sha256']), 'request schema')
    require(request['thread_id'] == receipt['thread_id'] and request['turn_id'] == receipt['turn_id']
            and request['control_event'] == request_event
            and request['start_monotonic_s'] == receipt['start_monotonic_s']
            and request['graceful_deadline_monotonic_s'] == receipt['graceful_deadline_monotonic_s'],
            'request does not bind the original first control and absolute budget')
    require(all(digest(value[k]) for k in keys if k.endswith('_sha256'))
            and value['request_sha256'] == sha(canonical(request))
            and integer(value['parent_ack_sequence'], 1), 'completion hashes or sequence')
    require(finite(value['completed_monotonic_s'])
            and request_event['monotonic_s'] <= value['completed_monotonic_s']
            <= event['monotonic_s'] <= sent_monotonic_s
            <= receipt['graceful_deadline_monotonic_s'], 'late or reordered cleanup barrier')
    return value


def position(value, h2, direction, *, start=False, nullable=False):
    if value is None and nullable:
        return
    fields = {'frame', 'end_byte'} | ({'start_byte'} if start else set())
    require(isinstance(value, dict) and set(value) == fields
            and integer(value['frame'], 1) and integer(value['end_byte'], 1)
            and value['frame'] <= h2['frames'][direction]
            and value['end_byte'] <= h2['bytes'][direction]
            and value['end_byte'] >= 9 * value['frame'] + (24 if direction == 'upload' else 0),
            'frame position outside observed wire')
    if start:
        require(integer(value['start_byte']) and value['start_byte'] + 9 <= value['end_byte']
                and value['start_byte'] >= 9 * (value['frame']-1) + (24 if direction == 'upload' else 0),
                'frame start outside observed wire')


def records(h2):
    """Validate every endpoint-local cleanup record and exact legacy-row index."""
    phase = h2.get('cleanup_phase_nonce')
    values = h2.get('cleanup_cancel_records', [])
    require(phase is None or nonce(phase), 'phase nonce')
    require(isinstance(values, list) and len(values) <= 64 and (phase is not None or not values),
            'cleanup record bound or phase')
    seen, resets, terminals = set(), set(), set()
    previous_frame = previous_byte = 0
    for row in values:
        require(isinstance(row, dict) and set(row) == {'schema', 'phase_nonce', 'stream_id', 'cancel',
                'opened_upload', 'opening_headers_complete', 'upload_end_stream', 'upload_headers_complete',
                'download_end_stream', 'download_headers_complete', 'wire', 'local'}
                and row['schema'] == 'campaign002-h2-cleanup-cancel-1'
                and row['phase_nonce'] == phase and integer(row['stream_id'], 1)
                and row['stream_id'] % 2 == 1 and row['stream_id'] <= h2['last_stream_id']
                and row['stream_id'] not in seen and row['stream_id'] not in h2['active_stream_ids'],
                'cleanup record identity, fields or live stream')
        sid = row['stream_id']; seen.add(sid); cancel = row['cancel']
        require(isinstance(cancel, dict) and set(cancel) == {'direction', 'type', 'flags', 'payload_length',
                'error_code', 'frame', 'start_byte', 'end_byte', 'sha256'}
                and cancel['direction'] == 'upload'
                and all(type(cancel[k]) is int and cancel[k] == v for k, v in (
                    ('type', 3), ('flags', 0), ('payload_length', 4), ('error_code', 8))), 'cancel syntax')
        position({k:cancel[k] for k in ('frame','start_byte','end_byte')}, h2, 'upload', start=True)
        rst = b'\x00\x00\x04\x03\x00' + sid.to_bytes(4, 'big') + b'\x00\x00\x00\x08'
        require(cancel['end_byte']-cancel['start_byte'] == 13 and cancel['sha256'] == sha(rst)
                and cancel['frame'] > previous_frame and cancel['start_byte'] >= previous_byte,
                'cancel wire identity/order')
        previous_frame, previous_byte = cancel['frame'], cancel['end_byte']
        opened = row['opened_upload']; opening = row['opening_headers_complete']
        position(opened, h2, 'upload', start=True); position(opening, h2, 'upload')
        require(opened['frame'] <= opening['frame'] < cancel['frame']
                and opened['end_byte'] <= opening['end_byte'] <= cancel['start_byte']
                and (opened['frame'] != opening['frame'] or opened['end_byte'] == opening['end_byte']),
                'opening incomplete or after cancellation')
        for direction in ('upload', 'download'):
            end, headers = row[direction+'_end_stream'], row[direction+'_headers_complete']
            position(end, h2, direction, nullable=True); position(headers, h2, direction, nullable=True)
            require(end is not None or headers is None, 'header completion without END_STREAM')
            if headers is not None:
                require(headers['frame'] >= end['frame'] and headers['end_byte'] >= end['end_byte']
                        and (headers['frame'] != end['frame'] or headers['end_byte'] == end['end_byte']),
                        'END_STREAM header completion reversed')
            if direction == 'upload' and end is not None:
                require(opened['frame'] <= end['frame'] < cancel['frame']
                        and opened['end_byte'] <= end['end_byte'] <= cancel['start_byte'],
                        'upload work after cancellation')
        wire = row['wire']
        require(isinstance(wire, dict) and set(wire) == {'upload','download'}, 'wire trace directions')
        for direction, trace in wire.items():
            require(isinstance(trace, dict) and set(trace) == {'frames','bytes','sha256'}
                    and integer(trace['frames']) and trace['frames'] <= h2['frames'][direction]
                    and integer(trace['bytes']) and trace['bytes'] <= h2['bytes'][direction]
                    and trace['bytes'] >= 9*trace['frames'] and digest(trace['sha256'])
                    and (trace['frames'] > 0 or trace == {'frames':0,'bytes':0,'sha256':sha(b'')}),
                    'wire trace identity/bound')
            anchors=[row[direction+'_end_stream'],row[direction+'_headers_complete']]
            if direction=='upload':anchors += [opened,opening,cancel]
            require(trace['frames'] >= len({a['frame'] for a in anchors if a is not None}),
                    'wire trace omits an observed opening, cancellation or closure frame')
        require(wire['upload']['frames'] >= 2 and wire['upload']['bytes'] >= 22, 'trace lacks opening and cancel')
        local = row['local']
        require(isinstance(local, dict) and set(local) == {'classification','reset_record_index',
                'terminal_control_index','eligibility','opposite_observed','phase_frontier'}, 'local fields')
        frontier = local['phase_frontier']
        require(isinstance(frontier, dict) and set(frontier) == {'upload_frames','upload_wire_bytes',
                'download_frames','download_wire_bytes','last_stream_id'}
                and all(integer(v) for v in frontier.values())
                and frontier['last_stream_id'] <= h2['last_stream_id'], 'local phase frontier')
        for direction in ('upload','download'):
            require(frontier[direction+'_frames'] <= h2['frames'][direction]
                    and frontier[direction+'_wire_bytes'] <= h2['bytes'][direction], 'phase frontier exceeds wire')
        require(cancel['frame'] > frontier['upload_frames']
                and cancel['start_byte'] >= frontier['upload_wire_bytes'], 'reset started before phase')
        opposite = local['opposite_observed']
        require(isinstance(opposite, dict) and set(opposite) == {'frames','wire_bytes','partial_frame','pending_headers_stream'}
                and integer(opposite['frames']) and opposite['frames'] <= h2['frames']['download']
                and integer(opposite['wire_bytes']) and opposite['wire_bytes'] <= h2['bytes']['download']
                and type(opposite['partial_frame']) is bool
                and (opposite['pending_headers_stream'] is None or integer(opposite['pending_headers_stream'],1)
                     and opposite['pending_headers_stream'] % 2 == 1
                     and opposite['pending_headers_stream'] <= h2['last_stream_id']), 'opposite-direction cursor')
        ri, ti = local['reset_record_index'], local['terminal_control_index']
        if local['classification'] == 'active':
            require(integer(ri) and ri < len(h2['reset_records']) and ri not in resets and ti is None
                    and h2['reset_records'][ri] == {'direction':'upload','stream_id':sid,'error_code':8},
                    'active cancellation raw index')
            resets.add(ri)
            require(local['eligibility'] in ('frontier_active','opened_during_phase'), 'active eligibility')
            if local['eligibility'] == 'frontier_active':
                require(sid <= frontier['last_stream_id'] and opening['end_byte'] <= frontier['upload_wire_bytes'],
                        'original active opening exceeds phase frontier')
            else:
                require(sid > frontier['last_stream_id'] and opened['frame'] > frontier['upload_frames']
                        and opened['start_byte'] >= frontier['upload_wire_bytes'], 'phase opening began too early')
        else:
            require(local['classification'] == 'normal_closed' and local['eligibility'] == 'proved_normal_close'
                    and integer(ti) and ti < len(h2['terminal_control_records']) and ti not in terminals and ri is None,
                    'normal cancellation raw index')
            terminals.add(ti); old = h2['terminal_control_records'][ti]
            require(old['stream_id'] == sid and old['frame'] == cancel['frame'] and old['end_byte'] == cancel['end_byte']
                    and all(row[d+'_headers_complete'] is not None for d in ('upload','download'))
                    and old['normal_close'] == {
                        'opened_upload':{k:opened[k] for k in ('frame','end_byte')},
                        'upload_closed':row['upload_headers_complete'],
                        'download_closed':row['download_headers_complete']}
                    and old['opposite_observed_frames'] == opposite['frames'], 'normal closure proof differs')
        require(len(resets) <= h2['reset_streams'] and len(terminals) <= h2['closed_streams'], 'counter underflow')
    return resets, terminals


def facts(value):
    """Explicit one-for-one reconciliation; original artifacts remain unchanged."""
    ri, ti = records(value)
    result = copy.deepcopy(value)
    result.pop('retiring', None)
    result['reset_streams'] -= len(ri); result['closed_streams'] -= len(ti)
    result['reset_records'] = [r for i,r in enumerate(value['reset_records']) if i not in ri]
    result['terminal_control_records'] = [{k:v for k,v in row.items() if k != 'opposite_observed_frames'}
                                          for i,row in enumerate(value['terminal_control_records']) if i not in ti]
    if 'cleanup_cancel_records' in result:
        result['cleanup_cancel_records'] = [{k:v for k,v in row.items() if k != 'local'}
                                            for row in value['cleanup_cancel_records']]
    return result


def progress(value, earlier):
    records(value); records(earlier)
    require(value.get('cleanup_phase_nonce') == earlier.get('cleanup_phase_nonce'), 'phase changed')
    old, new = earlier.get('cleanup_cancel_records', []), value.get('cleanup_cancel_records', [])
    require(len(new) >= len(old), 'cleanup evidence disappeared')
    mutable = {'upload_end_stream','upload_headers_complete','download_end_stream','download_headers_complete','wire'}
    for a,b in zip(old,new):
        require({k:v for k,v in a.items() if k not in mutable} == {k:v for k,v in b.items() if k not in mutable},
                'immutable cleanup authorization changed')
        for k in mutable - {'wire'}:
            require(a[k] is None or a[k] == b[k], 'observed closure changed or disappeared')
        for d in ('upload','download'):
            x,y = a['wire'][d], b['wire'][d]
            require(y['frames'] >= x['frames'] and y['bytes'] >= x['bytes']
                    and (y['frames'] != x['frames'] or y == x)
                    and (y['bytes'] != x['bytes'] or y == x), 'source-witnessed trace reversed or changed at equal length')


def explained_resets(value):
    return len(records(value)[0]) == value['reset_streams']


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite cleanup JSON')))


def _read(root, name, bindings, maximum):
    path = root / name
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum, 'missing/bounded '+name)
    raw = path.read_bytes()
    require(0 < len(raw) <= maximum and raw.endswith(b'\n'), 'partial/bounded '+name)
    identity = {'sha256':sha(raw),'bytes':len(raw)}
    require(name not in bindings or bindings[name] == identity, 'input changed: '+name)
    bindings[name] = identity
    return raw


def _one(rows, kind):
    found = [r for r in rows if r.get('kind') == kind]
    require(len(found) == 1, 'missing/duplicate '+kind)
    return found[0]


def _sequence(rows, namespace=False):
    previous = None; last = -1
    for n,row in enumerate(rows,1):
        require(isinstance(row,dict) and row.get('schema') == ('campaign002-codehost-namespace-3' if namespace
                else 'campaign002-codehost-transport-3') and type(row.get('sequence')) is int and row['sequence']==n
                and finite(row.get('monotonic_s')) and row['monotonic_s'] >= last
                and finite(row.get('wall_unix_s')), 'endpoint sequence/clock')
        last = row['monotonic_s']
        if not namespace:
            require(row.get('previous_sha256') == previous and row.get('record_sha256')
                    == sha(canonical({k:v for k,v in row.items() if k!='record_sha256'})), 'parent hash chain')
            previous = row['record_sha256']


def verify_client_barrier(root, complete, bindings):
    """Join controller completion to actual bounded owner/endpoint records.

    The caller has authenticated prospective source identities and the native
    lifecycle. Full transport qualification still checks every ordinary gate.
    """
    rows = [_decode(line) for line in _read(root,'codehost-transport-v3.jsonl',bindings,1024*1024).splitlines()]
    _sequence(rows)
    raw = _read(root,'codehost-owner-stderr-v3.txt',bindings,1024*1024)
    prefix = b'RCI_CODEHOST_V3 '
    require(all(line.startswith(prefix) for line in raw.splitlines()), 'namespace metadata framing')
    namespace = [_decode(line[len(prefix):]) for line in raw.splitlines()]
    _sequence(namespace, True)
    receipt_raw = _read(root,'codehost-owner-bridge-v3.json',bindings,8*1024*1024)
    receipt = _decode(receipt_raw)
    end = _one(rows,'closed'); bound = end.get('receipt',{})
    require(bound == {'path':'codehost-owner-bridge-v3.json', 'sha256':sha(receipt_raw),'bytes':len(receipt_raw)}
            and receipt.get('namespace_records') == namespace and receipt.get('cleanup_barrier') == complete,
            'protected bridge or namespace projection differs')
    if complete is None:
        require(not any(r.get('kind') in ('native_cleanup_begin','native_cleanup_ack','native_cleanup_channel')
                        or r.get('kind')=='frame' and r.get('frame_type') in (12,13) for r in rows+namespace)
                and namespace[-1].get('cleanup_barrier') is None, 'no-thread cleanup invented endpoint barrier')
        return {'schema':'campaign002-cleanup-barrier-proof-1','applicable':False}
    owner_raw = _read(root,'codehost-native-owner-v3.json',bindings,1024*1024)
    owner = _decode(owner_raw)
    client_owner = _decode(_read(root,'client/native-owner.json',bindings,1024*1024))
    owner_binding = {'path':'codehost-native-owner-v3.json','sha256':sha(owner_raw),'bytes':len(owner_raw)}
    registered = _one(rows,'owner_registered')
    require(owner == client_owner == receipt.get('owner') == registered.get('owner')
            and registered.get('receipt') == receipt.get('owner_receipt') == owner_binding
            and complete['request']['owner_receipt_sha256'] == owner_binding['sha256'], 'authenticated owner join')
    return barrier_records(rows, namespace, receipt, complete)


def barrier_records(rows, namespace, receipt, complete):
    # Independent assessor import only; no producer/runtime is imported.
    from transport_integrity_v3 import h2_summary, h2_progress
    request = complete['request']; request_hash = sha(canonical(request)); phase = request['nonce']
    parent = _one(rows,'native_cleanup_begin'); ack = _one(rows,'native_cleanup_ack')
    local = _one(namespace,'native_cleanup_begin')
    registered = _one(rows,'owner_registered'); final_drain = _one(rows,'owner_drain_begin')
    base = {'schema','kind','sequence','wall_unix_s','monotonic_s'}
    pbase = base | {'previous_sha256','record_sha256'}
    require(set(parent) == pbase | {'request','request_sha256','channels'}
            and parent['request']==request and parent['request_sha256']==request_hash
            and parent['record_sha256']==complete['parent_barrier_record_sha256']
            and registered['sequence'] < parent['sequence'] < ack['sequence'] < final_drain['sequence']
            and request['control_event']['monotonic_s'] <= parent['monotonic_s']
            <= ack['monotonic_s'] <= complete['completed_monotonic_s']
            <= request['graceful_deadline_monotonic_s'], 'parent barrier identity/order/deadline')
    require(set(local) == base | {'nonce','request_sha256','parent_record_sha256','child_pid','channels'}
            and local['nonce']==phase and local['request_sha256']==request_hash
            and local['parent_record_sha256']==parent['record_sha256']
            and type(local['child_pid']) is int
            and local['child_pid']==receipt['ready']['child_pid']==receipt['finished']['child_pid'],
            'namespace barrier owner/identity')
    local_hash = sha(canonical(local))
    begin = {'schema':'campaign002-native-cleanup-begin-1','request':request,
             'parent_record_sha256':parent['record_sha256']}
    ack_payload = {'schema':'campaign002-native-cleanup-ack-1','nonce':phase,'request_sha256':request_hash,
                   'parent_record_sha256':parent['record_sha256'],'namespace_record':local}
    bh, ah = sha(canonical(begin)), sha(canonical(ack_payload))
    require(set(ack)==pbase | {'request_sha256','namespace_record_sha256','begin_payload_sha256',
                              'ack_payload_sha256','namespace_record'}
            and ack['request_sha256']==request_hash and ack['namespace_record']==local
            and ack['namespace_record_sha256']==local_hash==complete['namespace_barrier_record_sha256']
            and ack['begin_payload_sha256']==bh==complete['begin_payload_sha256']
            and ack['ack_payload_sha256']==ah==complete['ack_payload_sha256']
            and ack['record_sha256']==complete['parent_ack_record_sha256']
            and ack['sequence']==complete['parent_ack_sequence'], 'ACK exact record/payload join')
    def frame(events, kind, direction, payload):
        matches=[r for r in events if r.get('kind')=='frame' and r.get('frame_type')==kind]
        require(len(matches)==1, 'missing/duplicate cleanup frame')
        row=matches[0]
        require(row.get('direction')==direction and type(row.get('channel_id')) is int and row['channel_id']==0
                and type(row.get('payload_bytes')) is int and row['payload_bytes']==len(canonical(payload))<=65536
                and row.get('payload_sha256')==sha(canonical(payload)), 'cleanup frame payload/direction')
        return row
    pb=frame(rows,12,'outgoing',begin); pa=frame(rows,13,'incoming',ack_payload)
    nb=frame(namespace,12,'incoming',begin); na=frame(namespace,13,'outgoing',ack_payload)
    require(parent['sequence']<pb['sequence']<pa['sequence']<ack['sequence']
            and nb['sequence']<local['sequence']<na['sequence']
            and local['sequence']<_one(namespace,'owner_drain_begin')['sequence'], 'ordered BEGIN/ACK')
    summary={'nonce':phase,'request_sha256':request_hash,'parent_record_sha256':parent['record_sha256'],
             'namespace_record_sha256':local_hash,'begin_payload_sha256':bh,'ack_payload_sha256':ah}
    require(namespace[-1].get('cleanup_barrier')==summary and receipt.get('cleanup_barrier')==complete,
            'final barrier summaries differ')
    channels={c['channel_id']:c for c in receipt['channels']}
    auths={r['channel_id']:r for r in rows if r.get('kind')=='channel_authenticated'}
    snapshots={}; historical_closed={}; upload_ended={}
    for endpoint, event, events, opening_kind in (('parent',parent,rows,'channel_authenticated'),
                                                 ('namespace',local,namespace,'channel_open')):
        frontiers=event['channels']
        existing=[r['channel_id'] for r in events if r.get('kind')==opening_kind and r['sequence']<event['sequence']]
        require(isinstance(frontiers,list) and [r.get('channel_id') for r in frontiers]==existing,
                'barrier channel set differs from actual admissions')
        selected={}; closed_ids=set(); ended_ids=set()
        for item in frontiers:
            fields={'channel_id','already_closed','upload_eof','h2'} | ({'authentication_sha256'} if endpoint=='parent' else set())
            require(set(item)==fields and type(item['channel_id']) is int and item['channel_id'] in channels
                    and type(item['already_closed']) is bool and type(item['upload_eof']) is bool,
                    'barrier channel fields')
            cid=item['channel_id']; h=h2_summary(item['h2'],complete=False)
            require(h.get('cleanup_phase_nonce') is None and h.get('cleanup_cancel_records')==[], 'reused phase snapshot')
            if endpoint=='parent':
                require(item['authentication_sha256']==sha(canonical(channels[cid]['authentication'])), 'barrier channel owner')
            capture_sequence=nb['sequence'] if endpoint=='namespace' else event['sequence']
            closed=[r for r in events if r.get('kind')=='channel_closed'
                    and (r.get('channel_id') if endpoint=='parent' else r.get('receipt',{}).get('channel_id'))==cid
                    and r['sequence']<capture_sequence]
            require(not closed or item['already_closed'], 'barrier closed-channel observation')
            eof=[r for r in events if (r.get('kind')=='client_eof' if endpoint=='parent' else
                    r.get('kind')=='channel_eof' and r.get('direction')=='upload')
                    and r.get('channel_id')==cid and r['sequence']<capture_sequence]
            half=[r for r in events if r.get('kind')=='frame' and r.get('frame_type')==4
                  and r.get('channel_id')==cid and r.get('direction')==('outgoing' if endpoint=='parent' else 'incoming')
                  and r['sequence']<(pb['sequence'] if endpoint=='parent' else nb['sequence'])]
            require(len(eof)<=1 and len(half)<=1 and item['upload_eof']==bool(eof)==bool(half)
                    and (not item['already_closed'] or item['upload_eof']), 'barrier genuine upload EOF enrollment')
            if item['upload_eof']:ended_ids.add(cid)
            if item['already_closed']:
                closed_ids.add(cid)
            for direction, framed in (('upload','outgoing' if endpoint=='parent' else 'incoming'),
                                       ('download','incoming' if endpoint=='parent' else 'outgoing')):
                data=[r for r in events if r.get('kind')=='frame' and r.get('channel_id')==cid
                      and r.get('frame_type')==3 and r.get('direction')==framed]
                count=0; prefixes={0}
                for frame_row in data:
                    require(integer(frame_row.get('payload_bytes'),1), 'barrier DATA size')
                    count+=frame_row['payload_bytes'];prefixes.add(count)
                # The namespace freezes its witness synchronously on BEGIN,
                # then awaits queued uploads before emitting its barrier row.
                # Downloads may advance during that await.
                capture_sequence=nb['sequence'] if endpoint=='namespace' else event['sequence']
                before=sum(r['payload_bytes'] for r in data if r['sequence']<capture_sequence)
                observed=h['bytes'][direction]
                require(observed in prefixes, 'barrier is not an exact directional DATA prefix')
                if (endpoint,direction) in (('parent','download'),('namespace','upload')):
                    require(observed==before, 'barrier received DATA prefix differs')
                else:
                    require(before<=observed<=count, 'barrier observed prefix precedes drained DATA')
            selected[cid]=h
        born=[r for r in events if r.get('kind')=='native_cleanup_channel']
        later=[r['channel_id'] for r in events if r.get('kind')==opening_kind and r['sequence']>event['sequence']]
        require([r.get('channel_id') for r in born]==later, 'phase-born channel identity/order')
        for item in born:
            fields=base | {'channel_id','nonce','request_sha256','h2'}
            if endpoint=='parent':fields |= {'previous_sha256','record_sha256','authentication_sha256'}
            require(set(item)==fields and item['nonce']==phase and item['request_sha256']==request_hash,
                    'phase-born record shape/identity')
            cid=item['channel_id']; h=h2_summary(item['h2'],complete=False)
            require(h.get('cleanup_phase_nonce') is None and h.get('cleanup_cancel_records')==[]
                    and h['last_stream_id']==h['open_streams']==h['closed_streams']==h['reset_streams']==0
                    and h['bytes']==h['frames']=={'upload':0,'download':0}, 'phase-born frontier not empty')
            opened=[r for r in events if r.get('kind')=='frame' and r.get('channel_id')==cid
                    and r.get('frame_type')==(1 if endpoint=='parent' else 2)]
            require(len(opened)==1 and event['sequence']<item['sequence']<opened[0]['sequence'], 'phase birth after OPEN/DATA')
            if endpoint=='parent':
                require(auths[cid]['sequence']<item['sequence']
                        and item['authentication_sha256']==sha(canonical(channels[cid]['authentication'])), 'phase-born owner join')
            selected[cid]=h
        snapshots[endpoint]=selected
        historical_closed[endpoint]=closed_ids
        upload_ended[endpoint]=ended_ids
    require(set(snapshots['parent'])==set(snapshots['namespace'])==set(channels), 'endpoint phase coverage')
    require(upload_ended['parent']==upload_ended['namespace'], 'endpoint upload EOF enrollment differs')
    for cid,channel in channels.items():
        for endpoint, final in (('parent',channel['h2']),('namespace',channel['namespace_closed']['h2'])):
            frontier=snapshots[endpoint][cid]
            expected_phase=None if cid in upload_ended[endpoint] else phase
            require(final.get('cleanup_phase_nonce')==expected_phase, 'foreign endpoint phase')
            if expected_phase is None:
                h2_progress(final,frontier)
                require(not final.get('cleanup_cancel_records')
                        and final['bytes']['upload']==frontier['bytes']['upload']
                        and final['frames']['upload']==frontier['frames']['upload']
                        and final['reset_records']==frontier['reset_records']
                        and final['terminal_control_records']==frontier['terminal_control_records']
                        and (cid not in historical_closed[endpoint] or final==frontier),
                        'unphased channel changed upload or completed witness')
            else:
                expected={'upload_frames':frontier['frames']['upload'],
                          'download_frames':frontier['frames']['download'],
                          'upload_wire_bytes':frontier['bytes']['upload'],
                          'download_wire_bytes':frontier['bytes']['download'],'last_stream_id':frontier['last_stream_id']}
                # Successful synchronous feed consumes every observed byte,
                # including its bounded partial-frame buffer, before this barrier.
                for row in final.get('cleanup_cancel_records',[]):
                    local_frontier=row['local']['phase_frontier']
                    require(local_frontier==expected, 'record phase frontier join')
                    if row['local']['eligibility']=='frontier_active':
                        require(row['stream_id'] in frontier['active_stream_ids'], 'stream was not active at barrier')
    return {'schema':'campaign002-cleanup-barrier-proof-1','applicable':True,'nonce':phase,
            'request_sha256':request_hash,'channels':len(channels),
            'scope':'Authenticated cleanup authorization and source-witnessed structural evidence; no RST-to-RPC causation or payload replay.'}
