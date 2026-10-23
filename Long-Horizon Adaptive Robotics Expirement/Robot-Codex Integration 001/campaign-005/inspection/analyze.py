"""Read-only encounter and artifact accounting, without inferred transfer claims."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys

HOME = Path(__file__).resolve().parent
sys.path.insert(0, str(HOME.parent))
from common import save, sha

APPARATUS_PATHS = {'/notes/executor-canary.txt', '/notes/canary-write.txt',
    '/programs/canary-write.txt', '/.continuity/canary-continuity.tmp',
    '/notes/canary-public.tmp', '/notes/escape-link'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def inventory(state):
    return {path: copy.deepcopy(state['nodes'][str(inode)])
            for path, inode in state['paths'].items()
            if path.startswith(('/notes/', '/programs/', '/.continuity/')) or path == '/ArtifactInventory.json'}


def content_identity(node):
    if node is None:
        return None
    return {key: node[key] for key in ('sha256', 'size', 'mode', 'target') if key in node}


def terminal_status(payload):
    # Servo feedback and immediate request rejection have different retained
    # shapes. Preserve missing/contradictory evidence instead of implying success.
    direct = payload.get('status')
    feedback = payload.get('feedback', {}).get('status')
    if direct is not None and feedback is not None:
        assert direct == feedback, 'Conflicting terminal status fields'
    return feedback or direct or 'unknown'


def handback_events(events):
    requested={e['payload']['request_id'] for e in events
        if e['type']=='command_requested' and e['payload'].get('kind')=='handback'
        and e['payload'].get('actor')=='robot'}
    output=[]
    for event in events:
        payload=event['payload'];rid=payload.get('request_id')
        if rid not in requested:continue
        if event['type'] in ('command_terminal','command_rejected'):
            status=terminal_status(payload)
        elif event['type']=='control_owner_changed' and event['owner']=='conventional':
            status='completed'
        else:continue
        output.append(dict(event_id=event['event_id'],sim_time_s=event['sim_time_s'],
            type=event['type'],request_id=rid,status=status,original_payload=payload,
            status_basis='Authoritative transfer event' if event['type']=='control_owner_changed' else 'Original terminal status'))
    return output


def physical_terminal_events(events,physical_ids):
    terminal={}
    for event in events:
        payload=event['payload'];rid=payload.get('request_id')
        if rid not in physical_ids:continue
        kind=event['type'];status=terminal_status(payload)
        if kind not in ('command_terminal','command_rejected') and not (kind=='command_admission' and status=='rejected'):
            continue
        if rid in terminal:
            assert terminal_status(terminal[rid]['payload'])==status,'Conflicting physical terminal evidence'
        terminal[rid]=event
    return list(terminal.values())


def executor_bindings(episode, session_ids):
    """Positive attribution to the real model executor, not just isolation.

    Connection 1 runs the retained nonmodel preflight; connection 2 serves
    the real model. Session id AND namespace AND native start ticks are used
    because Linux can reuse a namespace number after its owner retires.
    """
    bindings = {}
    for sid in session_ids:
        root = episode/sid
        probe = list(rows(root/'executor-1-requests.jsonl'))
        actual = list(rows(root/'executor-2-requests.jsonl'))
        assert any((r.get('params') or {}).get('processId') == 'canary' for r in probe)
        assert not any((r.get('params') or {}).get('processId') == 'canary' for r in actual)
        retired = read(root/'executor-2-retirement.json')
        assert retired['qualified'] and retired['windows_exit_code'] == 0
        evidence = retired['before_wait']
        ids = evidence['namespace_ids']
        assert len(ids) == 1 and evidence['bubblewrap_info']['pid-namespace'] == ids[0]
        bindings[sid] = dict(pid_namespace='pid:['+str(ids[0])+']',
            owner_start_ticks=int(evidence['identity']['start_ticks']),
            source=sid+'/executor-2-retirement.json',
            sha256=sha(root/'executor-2-retirement.json'),
            request_source=sid+'/executor-2-requests.jsonl',
            request_sha256=sha(root/'executor-2-requests.jsonl'))
    return bindings


def artifact_history(journal, bindings):
    """Keep exact changes and reads; a later read is only a transfer candidate."""
    state = copy.deepcopy(journal[0]['state'])
    changes, reads, boundaries = [], [], {}
    for record in journal:
        sid = record['session_id']
        if record['type'] == 'checkpoint' and record.get('label') == 'before-model-invocation':
            boundaries[sid] = {'sequence': record['sequence'], 'inventory': inventory(state)}
        if record['type'] == 'mutation':
            before = inventory(state)
            for area in ('paths', 'nodes'):
                for key in record['delta'][area]['remove']:
                    del state[area][key]
                state[area].update(record['delta'][area]['set'])
            after = inventory(state)
            for path in sorted(before.keys() | after.keys()):
                old, new = content_identity(before.get(path)), content_identity(after.get(path))
                if old == new:
                    continue
                changes.append(dict(sequence=record['sequence'], session_id=sid, path=path,
                    before=old, after=new, operation=record['operation'],
                    process=record['process'], monotonic_ns=record['monotonic_ns'],
                    after_model_boundary=sid in boundaries,
                    model_runtime_write=bool(sid in boundaries and record.get('process',{}).get('namespace_role')=='isolated-runtime' and record['process'].get('pid_namespace')==bindings[sid]['pid_namespace'] and int(record['process'].get('start_ticks',-1))>=bindings[sid]['owner_start_ticks']),
                    apparatus_path=path in APPARATUS_PATHS,
                    source='mutations.jsonl:' + str(record['sequence'])))
        elif record['type'] == 'read' and ((record.get('path') or '').startswith(('/notes/', '/programs/', '/.continuity/')) or record.get('path') == '/ArtifactInventory.json'):
            boundary = boundaries.get(sid)
            prior = boundary['inventory'].get(record['path']) if boundary else None
            reads.append({**{key: record.get(key) for key in (
                'sequence', 'session_id', 'path', 'bytes', 'offset', 'content_sha256',
                'returned_sha256', 'monotonic_ns', 'process')},
                'after_model_boundary': boundary is not None,
                'model_runtime_read': bool(boundary is not None
                    and record.get('process',{}).get('namespace_role')=='isolated-runtime'
                    and record['process'].get('pid_namespace')==bindings[sid]['pid_namespace']
                    and int(record['process'].get('start_ticks',-1))>=bindings[sid]['owner_start_ticks']),
                'matches_content_at_session_start': bool(prior and record['bytes'] > 0
                    and prior.get('sha256') == record['content_sha256']),
                'apparatus_path': record['path'] in APPARATUS_PATHS,
                'source': 'mutations.jsonl:' + str(record['sequence'])})
        elif record['type'] in ('checkpoint', 'final'):
            assert state == record['state']
    assert state == journal[-1]['state']
    return dict(changes=changes, reads=reads, model_boundaries=boundaries, model_executor_bindings=bindings,
        final_inventory=inventory(state), final_state_sha256=journal[-1]['state_sha256'],
        interpretation='Path names and content-bearing reads are observations. Task relevance, execution and useful transfer require concrete content/action evidence; they are not inferred from existence or a matching hash.')


def analyze(manifest_path, audit_root):
    manifest_path, audit_root = Path(manifest_path).resolve(), Path(audit_root).resolve()
    manifest = read(manifest_path); episode = Path(manifest['output'])
    audit = read(audit_root/'assessment/receipt.json'); official = read(audit_root/'official-status.json')
    assert official['state'] == 'succeeded' and type(official['exit_status']) is int and official['exit_status'] == 0
    assert audit['passed'] and audit['source_manifest_sha256'] == sha(manifest_path)
    identities = read(audit_root/'assessment/input-identities.json')
    for name, identity in identities.items():
        path = episode/name
        assert path.stat().st_size == identity['bytes'] and sha(path) == identity['sha256'], name
    receipt = read(episode/'receipt.json')
    public = list(rows(episode/'host/public-history.jsonl'))
    by_session, active = {}, None
    for event in public:
        payload = event['payload']
        if event['type'] == 'command_requested' and payload.get('kind') == 'start-invocation':
            active = payload['envelope']['invocation_id']
        if active:
            by_session.setdefault(active, []).append(event)
    sessions = []
    for attempt in receipt['attempted_sessions']:
        sid = attempt['session_id']; root = episode/sid
        client = read(root/'client/result.json')
        items = []
        for line, event in enumerate(rows(root/'client/events.jsonl'), 1):
            if event.get('method') != 'item/completed':
                continue
            item = event.get('params', {}).get('item', {})
            if item.get('type') not in ('agentMessage', 'commandExecution', 'dynamicToolCall', 'fileChange'):
                continue
            # Never copy private events or embedded image payloads to analysis.
            if item['type'] in ('agentMessage', 'commandExecution'):
                items.append(dict(source=sid+'/client/events.jsonl:'+str(line),
                    wall_ns=event['capture_wall_unix_ns'],
                    item={key: item[key] for key in ('type','id','text','command','exitCode') if key in item}))
        events = by_session.get(sid, [])
        requested = [e for e in events if e['type'] == 'command_requested' and e['payload'].get('actor') == 'robot']
        physical = [e for e in requested if e['payload']['kind'] == 'command']
        physical_ids = {e['payload']['request_id'] for e in physical}
        terminal = physical_terminal_events(events,physical_ids)
        handbacks = handback_events(events)
        end=read(root/'model-ending-state.json')
        native=list(rows(root/'client/events.jsonl'))
        starts=[e['capture_wall_unix_ns'] for e in native if e.get('method')=='turn/start']
        ends=[e['capture_wall_unix_ns'] for e in native if e.get('method')=='turn/completed']
        elapsed=(ends[-1]-starts[0])/1e9 if starts and ends else None
        sessions.append(dict(session_id=sid, task_outcome=attempt['task_outcome'],
            occurrence=attempt['occurrence'],session_within_occurrence=attempt['session_within_occurrence'],
            physical_at_model_end=end['physical'],public_budget_at_model_end=end['public'].get('robot_action_budget'),
            model_turn_elapsed_s=elapsed,model_time_remaining_s=None if elapsed is None else max(0,3600-elapsed),
            public_completed_item_counts=dict(Counter(e.get('params',{}).get('item',{}).get('type') for e in native if e.get('method')=='item/completed')),
            model_termination=attempt.get('model_termination'), thread_id=client['thread_id'],
            model=client['model_effective'], effort=client['effort_effective'], auth=client['auth_type'],
            physical_requests=len(physical), physical_event_ids=[e['event_id'] for e in physical],
            physical_terminal_statuses=dict(Counter(terminal_status(e['payload']) for e in terminal)),
            explicit_observe_requests=sum(e['payload']['kind']=='observe' for e in requested),
            handbacks=handbacks, public_items=items,
            elapsed_coordinator_wall_s=((attempt['finished_wall_unix_ns']-attempt['started_wall_unix_ns'])/1e9
                if 'finished_wall_unix_ns' in attempt else None)))
    journal = list(rows(audit_root/'assessment/raw/journal/mutations.jsonl'))
    artifacts = artifact_history(journal, executor_bindings(episode, [s['session_id'] for s in sessions]))
    for node in artifacts['final_inventory'].values():
        if 'sha256' in node:
            path = audit_root/'assessment/raw/journal/objects'/node['sha256']
            assert sha(path) == node['sha256'] and path.stat().st_size == node['size']
    for name, identity in identities.items():
        assert sha(episode/name) == identity['sha256'], name
    prior_reads=[]
    for read_event in artifacts['reads']:
        if not read_event['model_runtime_read'] or read_event['apparatus_path'] or not read_event['bytes']:continue
        creators=[c for c in artifacts['changes'] if c['sequence']<read_event['sequence']
            and c['session_id']!=read_event['session_id'] and c['path']==read_event['path'] and c['after_model_boundary']
            and c['after'] and c['after'].get('sha256')==read_event['content_sha256']]
        if creators:prior_reads.append(dict(read=read_event,prior_change=creators[-1]))
    from memory_analysis import analyze_memory
    memory=analyze_memory(journal,audit_root/'assessment/raw/journal',episode,artifacts,sessions)
    return dict(schema='campaign005-observable-investigation-3', model_calls=0,
        attribution_boundary='Only reads positively joined to the real model executor count as model_runtime_read. Other isolated reads, including preflight canaries after the checkpoint, remain retained but unattributed to the model. This field alone does not establish semantic use.',
        run_id=manifest['run_id'], stage=manifest['stage'], manifest=str(manifest_path),
        manifest_sha256=sha(manifest_path), audit_receipt_sha256=sha(audit_root/'assessment/receipt.json'),
        audit_official_status_sha256=sha(audit_root/'official-status.json'),
        original_queue_state=audit['measurements']['original_queue_state'],
        original_queue_exit_status=audit['measurements']['original_queue_exit_status'],
        infrastructure_audit_passed=True, qualification_complete=audit['qualification_complete'],
        joint_task_outcome=audit['task_outcome'], declared_encounters=manifest['encounter_limit'],
        attempted_encounters=len({s['occurrence'] for s in sessions}), attempted_sessions=len(sessions),accepted_terminals=len(receipt['sessions']),
        not_run_encounters=manifest['encounter_limit']-len({s['occurrence'] for s in sessions}),
        independent_protected_C_outcome=audit['measurements']['protected_C_outcome'],
        actual_image_deliveries=audit['measurements']['actual_image_deliveries'],
        wall_elapsed_s=receipt['wall_elapsed_s'], retained_windows_bytes=receipt['retained_windows_bytes'],
        sessions=sessions, artifacts=artifacts,prior_content_read_candidates=prior_reads,memory=memory,
        claims=dict(reuse='not assessable: no later invocation' if len(sessions)<2 else 'requires content/action readback',
            useful_transfer='not assessable: no later invocation' if len(sessions)<2 else 'requires prior-content use and valid later success',
            rediscovery='unknown without concrete derivation evidence',
            causal_artifact_contribution='unknown; no matched withholding intervention authorized',
            independence='Occurrences and fresh sessions within this one persistent block are correlated; one descriptive block cannot establish a population or causal effect.'),
        input_files_verified_before_and_after=len(identities))


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('manifest');parser.add_argument('audit');parser.add_argument('output')
    args=parser.parse_args();value=analyze(args.manifest,args.audit);save(Path(args.output),value)
    from verify_analysis import verify
    verify(args.output,args.audit,str(args.output)+'.verification.json')
    print(json.dumps({key:value[key] for key in ('run_id','joint_task_outcome','attempted_encounters','accepted_terminals','not_run_encounters')}),flush=True)
