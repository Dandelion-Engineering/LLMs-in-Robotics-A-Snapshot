"""Read-only failed-run infrastructure diagnosis; no assessor or subprocess launch."""
import hashlib
import json
from pathlib import Path
import zipfile

OUT = Path(__file__).resolve().parent
C = OUT.parent.parent
R = C.parent
REPO = R.parent.parent
RUN = 'RCI001-C02-smoke-026'
JOB = '20260929T050327589414Z-e2cffb4f'
RAW = R / 'local-evidence/campaign002/qualification' / RUN / 'orchestrator'
STAGE = RAW / 'interrupt'
REL = R.parent / 'Architecture Map/releases/RCI001-C02-dev-090'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data), 'sha256': digest(data)}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def save(name, value):
    with (OUT/name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def main():
    official = load(OUT/'official-status.json')
    assert official['id'] == JOB and official['state'] == 'failed'
    assert type(official['exit_status']) is int and official['exit_status'] == 1
    assert load(OUT/'authentication.json')['exit_code'] == 0
    # No failed-run bytes are consumed above the authenticated gate.
    sequence = load(RAW/'sequence-result.json')
    stage = load(STAGE/'stage-result.json')
    client = load(STAGE/'client/result.json')
    quiet = load(STAGE/'client/native-quiescence.json')
    bridge = load(STAGE/'codehost-owner-bridge-v3.json')
    ledger = [json.loads(line) for line in (STAGE/'codehost-transport-v3.jsonl').read_text(encoding='utf-8').splitlines()]
    events = [json.loads(line) for line in (STAGE/'client/events.jsonl').read_text(encoding='utf-8').splitlines()]
    previous = None
    for number, row in enumerate(ledger, 1):
        assert row['sequence'] == number
        if previous is not None:
            assert row['previous_sha256'] == previous
        record = dict(row); recorded = record.pop('record_sha256')
        assert digest(canonical(record)) == recorded
        previous = recorded
    first = next(row for row in ledger if row['kind'] == 'failure')
    assert first['sequence'] == 174 and first['reason'] == 'channel_ConnectionAbortedError'
    marker_line, marker = next((n,row) for n,row in enumerate(events,1) if row['kind'] == 'client_finishing_before_close')
    assert first['wall_unix_s'] == marker['wall_unix_s']
    assert first['monotonic_s'] == marker['monotonic_s']
    assert [row for row in events if row['kind'] == 'native_quiescence'] == quiet['events']
    inputs = [RAW/'sequence-result.json', STAGE/'stage-result.json', STAGE/'client/result.json',
              STAGE/'client/native-quiescence.json', STAGE/'client/events.jsonl', STAGE/'client/launch.json',
              STAGE/'codehost-owner-bridge-v3.json', STAGE/'codehost-transport-v3.jsonl',
              STAGE/'codehost-owner-stderr-v3.txt', STAGE/'codehost-native-owner-v3.json',
              STAGE/'cleanup.json', STAGE/'authority-revocation.json', STAGE/'runtime-before-close.json',
              STAGE/'runtime-after-close.json', C/'qualification/smoke-026-manifest.json',
              REL/'snapshot.json', REL/'code.zip']
    before = {str(path):binding(path) for path in inputs}
    snapshot = load(REL/'snapshot.json')
    assert before[str(REL/'snapshot.json')]['sha256'] == 'a72d7068856370b531a0b5e704ca6e8bf1f8091d5798a5c08fbd0f8c0cd476b9'
    source_names = ['harness/codehost_bridge_v3.py', 'harness/codehost_inside_v3.py',
                    'harness/codehost_mux_protocol.py', 'harness/native_quiescence.py',
                    'harness/bootstrap_client_v4.py', 'harness/transport_stderr.py',
                    'harness/physical.py', 'harness/runtime.py']
    sources = {}
    with zipfile.ZipFile(REL/'code.zip') as archive:
        for name in source_names:
            path = C/name; key = path.relative_to(REPO).as_posix()
            bound = binding(path); archived = archive.read(key)
            assert snapshot['sources'][key] == {'bytes':bound['bytes'],'sha256':bound['sha256']}
            assert len(archived) == bound['bytes'] and digest(archived) == bound['sha256']
            sources[name] = {**bound, 'archive_member':key, 'current_equals_frozen':True}
    upstream_names = [
        'codehost-channel-source-001/codex-rs__code-mode__src__grpc_session__mod.rs',
        'native-shutdown-source-001/codex-rs__core__src__session__handlers.rs',
        'native-output-source-002/codex-rs__app-server__src__request_processors__thread_lifecycle.rs',
    ]
    upstream = {name:binding(C/'io-repair'/name) for name in upstream_names}
    channels = []
    for channel in bridge['channels']:
        meters = channel['meters']; remote = channel['namespace_closed']; h2 = channel['h2']
        equal = (meters['client_read'] == meters['upload'] == remote['upload'] and
                 meters['download'] == meters['client_written'] == remote['download'])
        assert equal
        assert h2.get('error') is None and h2.get('first_rejection') is None
        channels.append({'channel_id':channel['channel_id'], 'meters':meters,
                         'namespace_upload':remote['upload'], 'namespace_download':remote['download'],
                         'all_observed_meter_identities_match':equal,
                         'parent_eof_sequence':(channel['parent_eof'] or {}).get('sequence'),
                         'upload_drained_sequence':(channel['upload_drained'] or {}).get('sequence'),
                         'namespace_upload_eof':remote['upload_eof'],
                         'namespace_upload_drained':remote['upload_drained'],
                         'namespace_download_eof':remote['download_eof'],
                         'namespace_qualified':remote['qualified'],
                         'h2':{key:h2.get(key) for key in ['error','first_rejection','active_stream_ids','open_streams',
                             'closed_streams','reset_streams','frames_complete','headers_complete','upload_complete',
                             'frames','bytes','goaway','reset_records','terminal_control_records','cleanup_cancel_records']}})
    retirements = []
    for name in ['executor-1-retirement.json','executor-2-retirement.json','codehost-owner-retirement-v3.json']:
        path = STAGE/name; value = load(path); last = value['observations'][-1]
        inputs.append(path); before[str(path)] = binding(path)
        retirements.append({'binding':before[str(path)], 'qualified':value['qualified'],
                            'windows_exit_code':value['windows_exit_code'],
                            'last':{key:last[key] for key in ['retired','namespace_evidence_available','namespace_ids',
                                                             'namespace_members','outer_same_process']}})
    lifecycle = []
    for number,row in enumerate(events,1):
        if row['kind'] in ['native_quiescence','client_finishing_before_close','shutdown']:
            lifecycle.append({'line':number, **{key:row[key] for key in ['kind','sequence','phase','wall_unix_s',
                'monotonic_s','method','request_id','status','qualified','exit_code','observed_monotonic_s'] if key in row}})
    timeline = []
    for row in ledger:
        if row['sequence'] >= 160:
            timeline.append({key:row[key] for key in ['sequence','kind','wall_unix_s','monotonic_s','channel_id',
                'reason','direction','frame_type','payload_bytes','payload_sha256','seal_qualified','seal_error_code',
                'after_finish_drain','after_finished','record_sha256'] if key in row})
    analysis = {
        'schema':'campaign002-smoke-queue-failure-diagnosis-1', 'run_id':RUN, 'queue_job_id':JOB,
        'scope':'Failed-job infrastructure diagnosis only. No empirical qualification or task assessment, replay, retry or promotion.',
        'task_outcome':'unknown', 'qualification_assessed':False,
        'official_authentication':binding(OUT/'authentication.json'), 'official_status':binding(OUT/'official-status.json'),
        'official_state':official['state'], 'official_exit_status':official['exit_status'],
        'official_started_at':official['started_at'], 'official_ended_at':official['ended_at'],
        'client_completion':{'model_started':client['model_started'],'success':client['success'],
            'error':client.get('error'),'source':binding(STAGE/'client/result.json'),
            'classification':'One observed model-start lower-bound item from failed-job diagnostic metadata; not an assessable task result or billed generation count.'},
        'orchestrator':{'completed':sequence['orchestrator_completed'],'error':sequence['error'],
            'host_exit_code':sequence['host_exit_code'],'stage_count':len(sequence['stages']),
            'resume_directory_exists':(RAW/'resume').exists(),'injected_interruption':stage['injected_interruption'],
            'command_at_interruption_request_id':stage['command_at_interruption']['request_id'],
            'retired_invocation':stage['retirement_transition']['invocation']['state'],
            'retired_epoch':stage['retirement_transition']['authority_epoch'],
            'old_token_denied_after_retirement':stage['old_token_denied_after_retirement'],
            'watchdog_errors':stage['watchdog_errors'],'cleanup_clean':stage['cleanup_clean'],
            'durable_retention_verified':stage['durable_retention_verified'],
            'all_namespaces_retired_field_present':'all_namespaces_retired' in stage,
            'stage_error':stage['error']},
        'first_failure':first,
        'cause_interpretation':{
            'observed':'The first retained transport failure is channel_ConnectionAbortedError. Channel 1 has no genuine client EOF or upload-drained receipt; both H2 summaries have no error/rejection and no active streams.',
            'source_inference':'The failure prefix and absent earlier sink/frame failures, together with missing channel-1 EOF and successful channel-2 EOF, locate the probable exception to channel-1 upload SocketReader.read -> loop.sock_recv. No stack trace, channel identifier or numeric OS code accompanies the first failure record, so this is source/state inference rather than a direct exception-site receipt.',
            'downstream':'finish_owner awaits the failed upload task and retains drain_invalid. Emergency FINISH then reaches Linux without channel-1 HALF_CLOSE; the first applicable source guard rejects Owner finish before genuine upload EOF. Namespace error and wrapper exit1 remain honest failed terminal cleanup.',
            'not_supported':'No evidence establishes benign graceful EOF, numeric WSA error, TCP RST cause, native pooled-channel drop cause, or absence of unobserved bytes. No H2 parser rejection was observed.'},
        'clock_boundary':{'client_marker_line':marker_line,'client_marker':marker,
            'first_failure_equals_marker_wall_and_monotonic':True,
            'interpretation':'Exact same Windows timestamps do not establish strict cross-file ordering. Thread-closed and handshake-complete were recorded earlier; stdin-closed/native-exit later. Namespace clock is not subtracted from Windows clock.'},
        'native_quiescence':{key:quiet[key] for key in ['qualified','handshake_qualified','forced_job_close','native_exit_code',
            'start_monotonic_s','graceful_deadline_monotonic_s','hard_deadline_monotonic_s','completed_monotonic_s','failures']},
        'transport':{'qualified':bridge['qualified'],'failures':bridge['failures'],'exit_code':bridge['exit_code'],
            'attempts':bridge['attempts'],'accepted':bridge['accepted'],'denied':bridge['denied'],
            'drain':bridge['drain'],'queued_bytes_at_close':bridge['queued_bytes_at_close'],
            'queue_with_headroom_maximum_bytes':bridge['queue_with_headroom_maximum_bytes'],
            'namespace_terminal':{key:bridge['finished'][key] for key in ['qualified','reason','error_type','drain_error_code',
                'drain_qualified','owner_drain_received','owner_drain_acknowledged','owner_finish_received','stdin_eof',
                'channel_count','channels_closed','child_exit_code','terminate_sent','kill_sent','queue_bytes_at_close']},
            'channels':channels,'ledger_hash_chain_checked_rows':len(ledger),
            'meter_scope':'Identities cover observed returned bytes only; socket abort can leave unobserved data, so equality is not genuine EOF proof.'},
        'retirements':retirements,
        'cleanup_scope':'All three retained namespace retirements report empty members/retired/qualified. This is scoped historical evidence, not a present global OS process census; transport qualification remains false.',
        'client_lifecycle_timeline':lifecycle,'transport_timeline':timeline,
        'source_bindings':sources,'retained_primary_sources':upstream,
        'source_lines':{
            'harness/codehost_bridge_v3.py':['35-37 socket read','412-438 failed task/drain/seal','548-570 EOF only after empty read','633-659 exception typing and cancellation','774-829 retirement and terminal checks'],
            'harness/codehost_inside_v3.py':['418-424 FINISH requires genuine EOF and upload drained'],
            'harness/physical.py':['55-74 planned abort and conditional all_namespaces_retired','75-101 cleanup retained'],
            'harness/native_quiescence.py':['260-302 handshake, marker, stdin closure and native exit'],
            upstream_names[0]:['305-348 CloseSession, close_state, stream_tasks.wait'],
            upstream_names[1]:['304-305 code-mode shutdown error logged'],
            upstream_names[2]:['408-456 thread shutdown then thread/closed']},
        'prospective_options':[
            'First add bounded secret-safe socket operation metadata (channel, read/write site, exception class and genuine integer errno/winerror where present, event/phase/owner identity and H2/meter snapshot). Preserve the same exception and rejection; never store dynamic exception payloads or fabricate EOF.',
            'Use a separately declared bounded no-model local bridge lifecycle reproducer to distinguish orderly SHUT_WR plus drain from abortive close and Windows scheduling. Such a synthetic reproducer tests the transport boundary, not the installed native teardown cause; no probe was launched here.',
            'A native graceful-channel shutdown correction would require a supported, source-verified mechanism and real EOF proof. The bounded retained source only proves CloseSession/stream-task joining and thread unload notifications, not a public socket FIN hook or installed-binary equivalence. Moving the marker, extra sleep, interpreting abort as EOF, or unchanged full requalification is unsupported.'
        ],
        'input_bindings':list(before.values()),
        'preservation':{'original_input_files_unchanged':False,'frozen_source_files_unchanged':True,
                        'no_assessor_or_test_or_native_or_model_or_queue_launch':True},
    }
    assert all(binding(Path(path)) == value for path,value in before.items())
    analysis['preservation']['original_input_files_unchanged'] = True
    save('analysis.json',analysis)
    lines = [
        '# Smoke026 queue failure: infrastructure diagnosis only', '',
        f'Run `{RUN}`; official job `{JOB}` freshly authenticated **failed / integer 1**. No empirical assessment, retry or task-outcome claim. Task outcome remains unknown.', '',
        'The planned interruption occurred after accepted `smoke-open-001`. Native cleanup completed: turn interrupt, terminal acknowledgement, unsubscribe, thread/closed, native exit 0, no forced job close. The first transport failure was `channel_ConnectionAbortedError` (ledger line/sequence 174). It was followed by `drain_invalid`, failed namespace terminal evidence and wrapper exit 1; resume was not attempted.', '',
        'The source/state inference is a channel-1 native upload socket read exception: `SocketReader.read` delegates directly to `loop.sock_recv`; channel 1 has no `client_eof`, HALF_CLOSE or upload-drained receipt. The first failure does not retain its channel, stack, errno, winerror or message, so the exact OS cause and socket-close mechanism are unknown. Channel 2 retained genuine EOF and upload drain. Neither H2 parser retained an error or first rejection.', '',
        'The first failure and the actual durable `client_finishing_before_close` marker have exactly equal wall and monotonic timestamps (1790658441.0409749 / 515920.5). Their strict cross-file order is unproved. `thread/closed` was recorded earlier at .0384662; the later controller `finishing`/`stdin_closed` records are .0424805. Those later records must not substitute for the marker.', '',
        'All observed meter identities match across native read, parent forwarding, namespace receipt and native writes: channel 1 upload 229450 B/download 166743 B; channel 2 upload 32471 B/download 1303 B. Both parsers ended structurally complete with zero active streams. This does not prove an aborted read is EOF or that no unobserved data remained. Channel 2\'s protected cleanup CANCEL evidence was retained successfully.', '',
        'The existing guard correctly requires genuine EOF. Parent `finish_owner` re-observes the upload exception and records `drain_invalid`; emergency FINISH has no channel-1 HALF_CLOSE. Linux\'s first applicable FINISH guard is `Owner finish before genuine upload EOF`. The namespace retained an unqualified terminal record, then retirement. All three original namespace-retirement receipts report qualified, retired, empty namespace membership and outer process absent; host exit is 0. No live-namespace leak is shown by these scoped historical receipts, but no present global OS census was performed.', '',
        'A supported next step is prospective bounded socket-operation/typed-error instrumentation plus a separately declared no-model local lifecycle reproducer. Keep failure, owner authentication, genuine EOF, byte hashes and deadlines unchanged. The retained native tag source joins CloseSession/stream tasks and emits thread/closed after thread shutdown; it does not expose a proved socket FIN acknowledgment or attest this installed native socket-close cause. Moving the marker, treating abort as EOF, sleeping longer, or another unchanged full qualification is unsupported.', '',
        'See [analysis.json](analysis.json) for exact source/archive identities, all original input bindings, metadata-only timelines, retirement observations and limits. Sources verified byte-equal to dev090 and its code.zip. No original evidence or source was changed.', '',
        'Key source locations: `harness/codehost_bridge_v3.py:35,412,548,633,774`; `harness/codehost_inside_v3.py:418`; `harness/physical.py:55`; `harness/native_quiescence.py:260`. Native tag interpretation remains source evidence, not installed-binary attestation.',
    ]
    with (OUT/'analysis.md').open('x',encoding='utf-8',newline='\n') as stream: stream.write('\n'.join(lines)+'\n')
    save('execution.json',{'schema':'campaign002-read-only-diagnosis-execution-1',
        'collector':binding(Path(__file__)),'analysis':binding(OUT/'analysis.json'),
        'markdown':binding(OUT/'analysis.md'),'input_files_rechecked':len(before),
        'frozen_sources_checked':len(sources),'ledger_rows_checked':len(ledger),
        'original_inputs_unchanged':True,'scope':'Diagnostic metadata and source analysis only; no production assessor executed.'})
    print(json.dumps({'analysis':binding(OUT/'analysis.json'),'markdown':binding(OUT/'analysis.md'),'model_start_observed':client['model_started']}))


if __name__ == '__main__':
    main()
