"""Operator-only paths/readback. No scientific module is replaced or patched."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tomllib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'session-59'))
import support as legacy
PAIR, FROZEN, CODE, DATA, PARENT, QUEUE = legacy.PAIR, legacy.FROZEN, legacy.CODE, legacy.DATA, legacy.RUN, legacy.QUEUE
BASE = DATA / 'recovery-session63'
QUAL = BASE / 'qualification001'
AUDIT = BASE / 'audit001'
DEST = BASE / 'recovered-run'
CP = PARENT / 'checkpoints/session-00005'
PARENT_JOB = '20261010T163419885117Z-d580bba0'
EXPECTED_CP = 'c66ca5214483fda60aa4ac2b45f5578b34d9c0f8b0823d241f50c4817122256d'
EXPECTED_STATE = 'aa9c5e9929630ea730488a8c99230064af65bf941f69d7365e7af98d7df72d32'
GIB = 1024**3
read, sha, save, ref, inventory, output, queue, now = legacy.read, legacy.sha, legacy.save, legacy.ref, legacy.inventory, legacy.output, legacy.queue, legacy.now
sys.path.insert(0, str(CODE))

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def assert_manifest(name):
    manifest = read(HERE / (name + '-manifest.json'))
    for filename, row in manifest['files'].items():
        assert sha(HERE / filename) == row['sha256'], filename
    return manifest

def capacity():
    return legacy.capacity(read(legacy.QUAL / 'baseline-allocation.json'))

def quiet():
    # Exclude only this operator's scripts and queue infrastructure; retain all
    # raw matching processes for independent interpretation.
    command = "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -match 'Dandelion-Apartment-Experiment|Local Experiment Data|robot-codex-session10') } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 3 -Compress"
    raw = output('powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command)
    windows = json.loads(raw) if raw.strip() else []
    if isinstance(windows, dict): windows = [windows]
    allowed = ('operations/session-63/', 'operations\\session-63\\', 'compute_queue.py')
    unexpected = [p for p in windows if not any(s in (p.get('CommandLine') or '') for s in allowed)]
    probe = r'''import os,json,pathlib
anc={os.getpid()};pid=os.getpid()
while pid>1:
 try:pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);anc.add(pid)
 except (OSError,ValueError):break
matches=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc:continue
 try:
  args=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if any(s in args for s in ('/var/tmp/robot-codex-session10','/tmp/robot-codex-session9','Dandelion-Apartment-Experiment','Local Experiment Data','journal_service.py','runtime_helper.py')):matches.append({'pid':int(p.name),'args':args})
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if 'robot-codex-session' in r]
print(json.dumps(dict(processes=matches,mounts=mounts)))'''
    linux = json.loads(output('wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', probe))
    jobs = sum((queue('list', '--state', state) for state in ('running', 'queued', 'cancel_requested')), [])
    conflicts = [j for j in jobs if any('run.py' in str(a) for a in j['argv']) and '--official' in j['argv']]
    monitors = []
    for p in sorted(Path('C:/Users/cresp/.codex/automations').glob('*/automation.toml')):
        row = tomllib.loads(p.read_text(encoding='utf-8'))
        if 'apartment' in json.dumps(row).lower(): monitors.append(dict(id=row.get('id', p.parent.name), status=row['status'], record=ref(p)))
    locks = [str(p) for root in (PAIR.parent, DATA) for p in root.rglob('running.lock')]
    with socket.socket() as sock:
        sock.settimeout(2); viewer_offline = sock.connect_ex(('127.0.0.1', 59465)) != 0
    return dict(windows=windows, unexpected_windows=unexpected, linux=linux, jobs=jobs, conflicting_jobs=conflicts,
        monitors=monitors, locks=locks, original_viewer_offline=viewer_offline,
        passed=not(unexpected or conflicts or linux['processes'] or linux['mounts'] or locks) and viewer_offline and all(m['status']=='PAUSED' for m in monitors))

def frozen_identity():
    from run import verify_run
    from environment import identity
    route = read(legacy.HERE / 'storage-route.json')
    for name in ('source_manifest', 'certificate', 'original_pair_manifest', 'initial_manifest'):
        row = route[name]; assert sha(row['uri']) == row['sha256'], name
    source = read(FROZEN / 'source-manifest.json')
    for name, row in source.items():
        p = FROZEN / name
        assert sha(p) == row['sha256'] and p.stat().st_size == row['bytes'], name
    certificate = read(CODE / 'commissioning.json')
    current = identity(); assert certificate['environment'] == current
    for name, digest in certificate['protocol_sha256'].items(): assert sha(CODE / name) == digest, name
    run = verify_run(PARENT, True)
    expected = read(PAIR / 'maps/run.json'); expected['launched'] = True
    assert run == expected
    assert inventory(PAIR / 'maps') == read(legacy.QUAL / 'maps-before.json')
    endpoint = read(HERE.parent / 'session-57/endpoint.json')
    for name, row in endpoint['evidence'].items(): assert sha(row['uri']) == row['sha256'], name
    receipts = {}
    for name in ('official_queue', 'full_audit_queue', 'supplement_queue'):
        old = read(endpoint['evidence'][name]['uri']); current_queue = queue('status', old['id'])
        assert current_queue == old and current_queue['state']=='succeeded' and type(current_queue['exit_status']) is int and current_queue['exit_status']==0
        receipts[name] = current_queue
    for name in ('full_audit', 'supplement'):
        report = read(endpoint['evidence'][name]['uri'])
        assert report['passed'] and all(v is True for v in report['checks'].values())
    return dict(source_files=len(source), source_manifest=ref(FROZEN/'source-manifest.json'), certificate=ref(CODE/'commissioning.json'),
        current_environment=current, baseline_endpoint=ref(HERE.parent/'session-57/endpoint.json'), baseline_receipts=receipts,
        original_maps=ref(legacy.QUAL/'maps-before.json'), source_code_changes=0)

def native_history(root=PARENT):
    import journal_reader
    sys.path.insert(0, str(HERE.parent/'session-60'))
    from read_progress import owner_status
    rows=[]
    for number in range(1,7):
        p=Path(root)/'sessions'/('session-'+str(number).zfill(5)); w=p/'workspace'
        loc=read(w/'location.json'); n=read(p/'native/client/result.json'); cleanup=read(w/'cleanup-001.json'); end=read(w/'journal/native-exit.json')
        proof=journal_reader.verify(w/'journal',loc['run_id'])
        assert n['success'] and n['turn_status']=='completed' and n['model_effective']=='gpt-6-astra' and n['effort_effective']=='max'
        assert n['native_quiescence']['qualified'] and n['native_quiescence']['native_exit_code']==0
        assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['log_closed']
        assert type(cleanup['service_exit']) is int and cleanup['service_exit']==0 and not cleanup['errors']
        assert end['libfuse_main_return']==0 and not end['requested_sigterm']
        assert proof['records']==end['final_sequence'] and proof['final_state_sha256']==end['final_state_sha256']
        owners=[owner_status(q) for name in ('native-owner.json','codehost-native-owner-v3.json') for q in p.rglob(name)]
        assert len(owners)==2 and all(o['retired'] for o in owners)
        if number<=5:
            from run import validate_closeout
            before=Path(root)/('filesystem-before-session-'+str(number).zfill(5))
            closeout=validate_closeout(before,w/'final-filesystem')
            assert closeout == read(p/'closeout.json')
        rows.append(dict(session=number,accepted=number<=5,thread_id=n['thread_id'],native_result=ref(p/'native/client/result.json'),
            journal={k:v for k,v in proof.items() if k not in ('state','states','read_events')},owners=owners,location=loc))
    assert len({r['thread_id'] for r in rows})==6
    return rows

def parent_checkpoint():
    from recording import verify_checkpoint, verify_prefix
    from recovery import terminal, best_checkpoint
    receipt=verify_checkpoint(CP); prefix=verify_prefix(PARENT, CP); state=read(CP/'state.json')
    assert receipt['manifest_sha256']==EXPECTED_CP and receipt['state_sha256']==EXPECTED_STATE
    assert state['sessions']==5 and state['position']==2 and len(state['completed'])==2
    selected, checked, selected_state, rejected = best_checkpoint(PARENT)
    assert selected==CP and checked==receipt and selected_state==state and not rejected
    failure=terminal(PARENT)
    assert not failure['passed'] and failure['retirement']['all_retired'] and failure['failure_phase']=='filesystem-closeout'
    q=queue('status',PARENT_JOB)
    assert q['state']=='failed' and type(q['exit_status']) is int and q['exit_status']==1
    rows=[json.loads(line) for line in (PARENT/'events.jsonl').read_bytes().splitlines()]
    tail=[r for r in rows if r['sequence']>state['event_sequence']]
    assert sum(r['kind']=='session_started' for r in tail)==1
    assert not (PARENT/'checkpoints/session-00006').exists()
    return dict(receipt=receipt,prefix=prefix,abandoned_native_calls=1,accepted_sessions=5,advancements=2,
        parent_queue=q,failed_execution=ref(read(PARENT/'latest-execution.json')['path']),tail_events=len(tail),
        tail_start_sequence=state['event_sequence']+1,tail_end_sequence=rows[-1]['sequence'])
