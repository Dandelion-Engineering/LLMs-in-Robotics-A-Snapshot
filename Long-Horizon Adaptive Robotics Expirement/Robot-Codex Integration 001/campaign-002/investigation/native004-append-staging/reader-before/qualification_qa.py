"""Static and data-integrity QA for the separate qualification companion."""
import argparse
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parents[2]
NO_MODEL_DIAGNOSTIC_KINDS = {'raw_event_preflight_diagnostic', 'transport_probe_diagnostic'}


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.urls = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('href', 'src'):
            if attrs.get(key):
                self.urls.append(attrs[key])
        if tag in ('script', 'link', 'img', 'iframe') and ('src' in attrs or 'href' in attrs):
            raise ValueError('Companion must have no external runtime dependencies')


def static_html(html, *, javascript=True):
    structure = Structure()
    structure.feed(html)
    if len(structure.ids) != len(set(structure.ids)):
        raise ValueError('Duplicate HTML identity')
    scripts = re.findall(r'<script>(.*?)</script>', html, flags=re.S)
    if len(scripts) != 1:
        raise ValueError('Exactly one inline script required')
    references = set(re.findall(r"\$\('([^']+)'\)", scripts[0]))
    if references - set(structure.ids):
        raise ValueError('Missing referenced UI identities: ' + str(references - set(structure.ids)))
    if javascript:
        node = shutil.which('node')
        if not node:
            raise ValueError('Node is required for static JavaScript syntax QA')
        with tempfile.TemporaryDirectory(prefix='qualification-js-') as tmp:
            script = Path(tmp) / 'script.js'
            script.write_text(scripts[0], encoding='utf-8')
            result = subprocess.run([node, '--check', str(script)], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError('JavaScript syntax failed: ' + result.stderr)
    return {'unique_ids': len(structure.ids), 'script_references': len(references),
            'javascript_syntax': 'passed' if javascript else 'not_run', 'external_dependencies': 0}


def diagnostic_links_guard(items, output, source_links, *, context='Qualification'):
    """Verify diagnostic hyperlink bytes only; permit a distinct run identity."""
    if not isinstance(items, list):
        raise ValueError(context + ' diagnostics must remain separate hash-only links')
    source_paths = {(Path(output) / unquote(item['href'])).resolve() for item in source_links}
    source_labels = {item.get('label') for item in source_links} | {'Original assessment'}
    urls, seen, labels = [], set(), set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'label', 'href', 'sha256', 'bytes', 'basis'}
                or item.get('basis') != 'diagnostic_link_only' or not isinstance(item.get('label'), str)
                or not item['label'].strip() or item['label'] in labels | source_labels
                or type(item.get('bytes')) is not int or not 0 <= item['bytes'] <= 128 * 1024 * 1024
                or not isinstance(item.get('sha256'), str) or re.fullmatch('[0-9a-f]{64}', item['sha256']) is None
                or not isinstance(item.get('href'), str) or urlparse(item['href']).scheme
                or urlparse(item['href']).netloc or urlparse(item['href']).query or urlparse(item['href']).fragment
                or re.fullmatch(r'.+-(?:analysis|diagnosis)\.(?:md|json)', Path(unquote(item['href'])).name) is None):
            raise ValueError(context + ' diagnostics must remain separate hash-only links')
        path = Path(output) / unquote(item['href'])
        if (not path.is_file() or path.is_symlink() or path.resolve() in seen | source_paths
                or path.stat().st_size > 128 * 1024 * 1024):
            raise ValueError(context + ' diagnostic link unavailable or aliases source evidence')
        raw = path.read_bytes()  # Hash verification only; never parse diagnostic content.
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError(context + ' diagnostic document changed')
        seen.add(path.resolve())
        labels.add(item['label'])
        urls.append(item['href'])
    return urls


# One declared failed interruption diagnostic; never a generic model-manifest alias.
SINGLE_INTERRUPT_SCHEMA = 'campaign002-failed-single-interrupt-queue-1'
SINGLE_INTERRUPT_SOURCES = {
    'io-repair/single-interrupt-diagnostic/run.py':
        {'sha256': '3ec098c7aaee147adf3c6228e3330eb9322fdbf20f3738dca3af668db417c3ec', 'bytes': 4959},
    'io-repair/single-interrupt-diagnostic/common.py':
        {'sha256': 'd1e9b2f215b2878c325548526d50dfc6a10b4df383135ac40fe552cddb2be128', 'bytes': 6938},
    'io-repair/SHUTDOWN_REJECTION_DIAGNOSTIC_V1.md':
        {'sha256': '020c597f6754be9cd072eff1a0e573093c06259a2b6cfe4a289155ec7eb36108', 'bytes': 3024},
}


# Exact immutable dev062 dispatch identities; no current runtime source is opened.
RESET_INTERRUPT_SOURCES = {'io-repair/single-interrupt-diagnostic-v2/run.py': {'sha256': '3ec098c7aaee147adf3c6228e3330eb9322fdbf20f3738dca3af668db417c3ec', 'bytes': 4959}, 'io-repair/single-interrupt-diagnostic-v2/common.py': {'sha256': '7d17dbf34aa4b539cb5e37ac850569d3b5f41739881c7aba591e5171ece3ad9a', 'bytes': 7034}, 'io-repair/single-interrupt-diagnostic-v2/launch.py': {'sha256': '63af0d5c9e1383c7e51d52c30dab38043c707b9df42ba5dc01a247ce742cf79d', 'bytes': 4074}, 'io-repair/RESET_REJECTION_DIAGNOSTIC_V1.md': {'sha256': '383ed2034e5b804b50a368725d74622933cf7b184ec7faed56131c7a9b9f8af2', 'bytes': 4325}}


# Exact declared dev091 dispatch; failed metadata only, never a success alias.
SOCKET_INTERRUPT_SOURCES = {'io-repair/single-interrupt-diagnostic-v3/run.py': {'sha256': '3ec098c7aaee147adf3c6228e3330eb9322fdbf20f3738dca3af668db417c3ec', 'bytes': 4959}, 'io-repair/single-interrupt-diagnostic-v3/common.py': {'sha256': 'c340102252816a4a6b8a3b074ee1182dcd727548525e2ab776c81980d0008917', 'bytes': 12499}, 'io-repair/single-interrupt-diagnostic-v3/launch.py': {'sha256': '63af0d5c9e1383c7e51d52c30dab38043c707b9df42ba5dc01a247ce742cf79d', 'bytes': 4074}, 'io-repair/SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md': {'sha256': 'eda635ef8981a0c28ceeeb90df9f5426213f87f6e8c874658381f8ee29368314', 'bytes': 6223}}


def failed_single_interrupt_dispatch(row, job, paths, manifest, snapshot, manifest_hash):
    """Recognize fixed dispatch metadata only, without opening failed outputs."""
    run, revision = 'RCI001-C02-shutdown-diagnostic-001', 'RCI001-C02-dev-055'
    root = CAMPAIGN / 'io-repair/shutdown-diagnostic-001'
    script = CAMPAIGN / 'io-repair/single-interrupt-diagnostic/run.py'
    protocol = 'RCI001-Campaign002-single-interrupt-diagnostic-v1'
    required_sources = SINGLE_INTERRUPT_SOURCES
    if row.get('run_id') == 'RCI001-C02-shutdown-diagnostic-002':
        run, revision = 'RCI001-C02-shutdown-diagnostic-002', 'RCI001-C02-dev-062'
        root = CAMPAIGN / 'io-repair/shutdown-diagnostic-002'
        script = CAMPAIGN / 'io-repair/single-interrupt-diagnostic-v2/run.py'
        protocol = 'RCI001-Campaign002-single-interrupt-diagnostic-v2'
        required_sources = RESET_INTERRUPT_SOURCES
    elif row.get('run_id') == 'RCI001-C02-shutdown-diagnostic-003':
        run, revision = 'RCI001-C02-shutdown-diagnostic-003', 'RCI001-C02-dev-091'
        root = CAMPAIGN / 'io-repair/shutdown-diagnostic-003'
        script = CAMPAIGN / 'io-repair/single-interrupt-diagnostic-v3/run.py'
        protocol = 'RCI001-Campaign002-single-interrupt-diagnostic-v3'
        required_sources = SOCKET_INTERRUPT_SOURCES
    manifest_path = root / 'manifest.json'
    snapshot_path = CAMPAIGN.parent.parent / 'Architecture Map/releases' / revision / 'snapshot.json'
    evidence = CAMPAIGN.parent / 'local-evidence/campaign002/io-repair' / run
    workspace = Path(os.environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/diagnostic' / run
    executable = REPO / 'venv/Scripts/python.exe'
    expected = [str(executable), '-X', 'utf8', '-B', str(script), '--manifest', str(manifest_path),
                '--snapshot', str(snapshot_path), '--evidence', str(evidence / 'orchestrator'),
                '--host-evidence', str(evidence / 'host'), '--workspace', str(workspace)]
    if (row.get('run_id') != run or row.get('revision') != revision
            or Path(paths['Frozen attempt manifest']).resolve() != manifest_path.resolve()
            or Path(paths['Frozen source snapshot']).resolve() != snapshot_path.resolve()
            or job.get('argv') != expected or job.get('cwd') != str(REPO)
            or job.get('resolved_executable') != str(executable)):
        raise ValueError('Single-interrupt exact dispatch or identity differs')
    expected_fields = {
        'schema': 'robot-codex-development-manifest-1.0', 'stage': 'development-only',
        'run_id': run, 'framework_revision': revision, 'family': 'misplaced-stock', 'mode': 'serve',
        'qualification_stage': 'campaign002-single-interrupt-diagnostic',
        'outer_campaign_protocol': protocol,
        'model': 'gpt-6-astra', 'effort': 'max', 'bootstrap': 'Follow the instructions in RobotAgentPrompt.md.',
        'seed': 173, 'noise_seed': 24101, 'sim_cap_s': 1500, 'wall_cap_s': 1800,
        'storage_cap_bytes': 536870912, 'physics_dt_s': 0.002, 'model_turns_max': 1,
        'invocation_wall_cap_s': 600, 'action_request_budget': 20, 'observation_request_budget': 50,
        'interruption_trigger': 'first admitted smoke-open-001 gripper open action; revoke authority then abort client',
        'runtime_workspace': str(workspace),
    }
    if any(type(manifest.get(k)) is not type(v) or manifest[k] != v for k, v in expected_fields.items()):
        raise ValueError('Single-interrupt manifest schema, scope or original cap differs')
    if (snapshot.get('schema') != 'robot-codex-readiness-source-1' or snapshot.get('run_id') != run
            or snapshot.get('revision') != revision or snapshot.get('manifest_sha256') != manifest_hash):
        raise ValueError('Single-interrupt snapshot does not bind the exact manifest')
    sources, declared = snapshot.get('sources'), manifest.get('runtime_input_files')
    if (not isinstance(sources, dict) or not isinstance(declared, list)
            or not all(isinstance(name, str) for name in declared) or len(set(declared)) != len(declared)):
        raise ValueError('Single-interrupt source inventory is malformed')
    for relative, identity in required_sources.items():
        name = (CAMPAIGN / relative).relative_to(REPO).as_posix()
        found = sources.get(name)
        if (not isinstance(found, dict) or set(found) != {'sha256', 'bytes'}
                or type(found.get('bytes')) is not int or found != identity or name not in declared):
            raise ValueError('Single-interrupt frozen wrapper or method source differs')


def failed_queue_guard(row, output):
    """Check the metadata-only failed-job branch without opening attempt outputs."""
    failure = row.get('queue_failure') or {}
    if (set(failure) != {'schema', 'basis', 'assessment_state', 'queue_job_id', 'official_queue_sha256',
                         'official_queue_href', 'manifest_sha256', 'snapshot_sha256', 'diagnostic_links', 'scope'}
            or failure.get('schema') not in ('campaign002-failed-queue-diagnostic-1', 'campaign002-failed-diagnostic-queue-1', SINGLE_INTERRUPT_SCHEMA)
            or failure.get('basis') != 'official_terminal_execution_failure'
            or failure.get('assessment_state') != 'not_assessed'
            or row.get('assessment_state') != 'not_assessed' or row.get('assessment_schema') is not None
            or row.get('status') != 'failed' or row.get('validity') != 'unknown'
            or row.get('scorable') is not False or row.get('task_outcome') != 'unknown'
            or row.get('model_calls') is not None or row.get('queue_state') != 'failed'
            or type(row.get('queue_exit_status')) is not int or row['queue_exit_status'] == 0
            or failure.get('queue_job_id') != row.get('job_id')
            or any(row.get(k) is not None for k in ('timing', 'supervisory_timing', 'recorder_feasibility',
                'protected_io', 'pilot_admission', 'admission_disposition', 'preflight', 'native_reference'))
            or row.get('recorder_subphases_declared') is not False
            or any(row.get(k) != {} for k in ('checks', 'assessment_errors', 'declared_details'))
            or any(row.get(k) != [] for k in ('failed_checks', 'analyses'))
            or row.get('diagnostic_links', []) != []):
        raise ValueError('Failed queue acquired assessment, measurement or outcome evidence')
    try:
        start = datetime.fromisoformat(row['started_at'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(row['ended_at'].replace('Z', '+00:00'))
        if start.tzinfo is None or end.tzinfo is None or not start <= end:
            raise ValueError('Invalid interval')
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError('Failed queue lacks terminal official start/end interval') from error
    labels = {'Official queue receipt': 'official_queue_sha256',
              'Frozen attempt manifest': 'manifest_sha256', 'Frozen source snapshot': 'snapshot_sha256'}
    links = row.get('links', [])
    if len(links) != 3 or {x.get('label') for x in links} != set(labels):
        raise ValueError('Failed queue contains nonmetadata source links')
    paths, documents = {}, {}
    for item in links:
        digest = item.get('sha256')
        url = item.get('href')
        if (not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None
                or digest != failure.get(labels[item['label']]) or not isinstance(url, str)
                or urlparse(url).scheme):
            raise ValueError('Failed queue metadata hash/link binding mismatch')
        path = Path(output) / unquote(url)
        if not path.is_file() or path.is_symlink():
            raise ValueError('Failed queue metadata link unavailable or linked')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Failed queue metadata bytes changed')
        paths[item['label']] = path
        documents[item['label']] = json.loads(raw)
    official = next(x for x in links if x['label'] == 'Official queue receipt')
    if failure.get('official_queue_href') != official['href']:
        raise ValueError('Failed queue receipt link differs from source inventory')
    receipt = documents['Official queue receipt']
    job = receipt.get('job', receipt)
    if (job.get('id') != row['job_id'] or job.get('state') != 'failed'
            or type(job.get('exit_status')) is not int or job['exit_status'] != row['queue_exit_status']
            or job.get('started_at') != row['started_at'] or job.get('ended_at') != row['ended_at']):
        raise ValueError('Failed queue display differs from exact official terminal receipt')
    manifest, snapshot = documents['Frozen attempt manifest'], documents['Frozen source snapshot']
    if failure['schema'] == SINGLE_INTERRUPT_SCHEMA:
        failed_single_interrupt_dispatch(row, job, paths, manifest, snapshot, failure['manifest_sha256'])
        return diagnostic_links_guard(failure.get('diagnostic_links', []), output, links, context='Failed queue')
    if failure['schema'] == 'campaign002-failed-diagnostic-queue-1':
        failed_diagnostic_dispatch(row, job, paths, manifest, snapshot, failure['snapshot_sha256'])
        return diagnostic_links_guard(failure.get('diagnostic_links', []), output, links, context='Failed queue')
    argv = job.get('argv', [])
    if not isinstance(argv, list) or argv.count('--manifest') != 1 or argv.index('--manifest') + 1 >= len(argv):
        raise ValueError('Failed queue exact manifest dispatch unavailable')
    dispatched = Path(argv[argv.index('--manifest') + 1])
    if not dispatched.is_absolute():
        if not isinstance(job.get('cwd'), str) or not Path(job['cwd']).is_absolute():
            raise ValueError('Failed queue relative manifest lacks absolute working directory')
        dispatched = Path(job['cwd']) / dispatched
    if (dispatched.resolve() != paths['Frozen attempt manifest'].resolve()
            or not paths['Frozen attempt manifest'].name.endswith('-manifest.json')
            or paths['Frozen source snapshot'].name != 'snapshot.json'
            or manifest.get('run_id') != row['run_id'] or manifest.get('framework_revision') != row['revision']
            or snapshot.get('revision') != row['revision']):
        raise ValueError('Failed queue manifest/revision correspondence differs')
    return diagnostic_links_guard(failure.get('diagnostic_links', []), output, links, context='Failed queue')


def failed_diagnostic_dispatch(row, job, paths, manifest, snapshot, snapshot_hash):
    """Independent metadata-only check of the two declared direct CLI families."""
    run = row['run_id']
    names = {'raw-preflight':'raw_event_preflight_v2.py', 'transport-probe':'codehost_transport_probe_v3.py'}
    families = [name for name in names if re.fullmatch('RCI001-C02-'+name+r'-\d{3}', run)]
    if len(families) != 1:
        raise ValueError('Failed diagnostic family differs')
    script = CAMPAIGN/'harness'/names[families[0]]
    manifest_path, snapshot_path = paths['Frozen attempt manifest'].resolve(), paths['Frozen source snapshot'].resolve()
    argv = job.get('argv')
    if (not isinstance(argv,list) or len(argv)!=13 or not all(isinstance(v,str) for v in argv)
            or not Path(argv[0]).is_absolute() or not isinstance(job.get('resolved_executable'),str)
            or Path(job['resolved_executable']).resolve()!=Path(argv[0]).resolve()
            or not isinstance(job.get('cwd'),str) or not Path(job['cwd']).is_absolute()
            or Path(job['cwd']).resolve()!=REPO.resolve()
            or argv[1:4]!=['-X','utf8','-B'] or not Path(argv[4]).is_absolute()
            or Path(argv[4]).resolve()!=script.resolve()
            or argv[5:]!=['--run-id',run,'--framework-revision',row['revision'],
                          '--snapshot',str(snapshot_path),'--output',str(manifest_path.parent/'evidence')]
            or manifest_path!=(CAMPAIGN/'io-repair'/run.removeprefix('RCI001-C02-')/'manifest.json').resolve()
            or snapshot_path.name!='snapshot.json'
            or manifest.get('run_id')!=run or manifest.get('framework_revision')!=row['revision']
            or snapshot.get('revision')!=row['revision']):
        raise ValueError('Failed diagnostic exact direct dispatch or revision differs')
    anchor = manifest.get('source_snapshot')
    if (not isinstance(anchor,dict) or set(anchor)!={'path','sha256'}
            or not isinstance(anchor['path'],str) or not Path(anchor['path']).is_absolute()
            or Path(anchor['path']).resolve()!=snapshot_path or anchor['sha256']!=snapshot_hash
            or type(manifest.get('model_calls'))is not int or manifest['model_calls']!=0
            or manifest.get('physical_simulation')is not False):
        raise ValueError('Failed diagnostic frozen anchor or declared scope differs')
    sources = snapshot.get('sources')
    source = sources.get(script.relative_to(REPO).as_posix()) if isinstance(sources,dict) else None
    if (not isinstance(source,dict) or set(source)!={'sha256','bytes'}
            or type(source['bytes'])is not int or source['bytes']<=0
            or not isinstance(source['sha256'],str) or re.fullmatch('[0-9a-f]{64}',source['sha256'])is None):
        raise ValueError('Failed diagnostic entry source absent from bound snapshot')


def latest_completed_qualifier(rows):
    return next((row for row in reversed(rows) if row['status'] in ('passed', 'failed')
                 and row.get('diagnostic_result') is None
                 and row.get('host_prerequisite') is None
                 and row.get('attempt_kind') not in NO_MODEL_DIAGNOSTIC_KINDS), None)


def host_prerequisite_guard(row,output):
    detail=row.get('host_prerequisite')
    keys={'schema','assessment_sha256','official_queue_sha256','manifest_sha256','snapshot_sha256','qualification_claim','scope'}
    required={'host_exit_zero','queue_encloses_host','exact_manifest','no_model_or_reference_recovery',
              'host_completed','declared_interval_completed','free_reserve_preserved','strict_fresh_timing'}
    if (not isinstance(detail,dict) or set(detail)!=keys or detail['schema']!='campaign002-host-prerequisite-history-1'
            or detail['qualification_claim']is not False or row.get('attempt_kind')!='host_prerequisite_diagnostic'
            or row.get('status')!='passed' or row.get('validity')!='diagnostic_passed' or row.get('scorable')is not False
            or row.get('task_outcome')!='unknown' or type(row.get('model_calls'))is not int or row['model_calls']!=0
            or row.get('assessment_schema')!='campaign002-host-probe-assessment-1' or row.get('queue_failure')is not None
            or row.get('diagnostic_result')is not None or row.get('assessment_errors')!={}
            or re.fullmatch(r'RCI001-C02-host-probe-\d{3}',row['run_id'])is None):
        raise ValueError('Host prerequisite classification or scope differs')
    labels={'Official queue receipt':'official_queue_sha256','Frozen host prerequisite manifest':'manifest_sha256',
            'Frozen source snapshot':'snapshot_sha256','Original host diagnostic assessment':'assessment_sha256'}
    paths,documents={},{}
    for label,key in labels.items():
        found=[v for v in row['links'] if v.get('label')==label and v.get('sha256')==detail[key]]
        if len(found)!=1:raise ValueError('Host prerequisite metadata links differ')
        item=found[0];url=item.get('href','');path=(Path(output)/unquote(url)).resolve()
        if urlparse(url).scheme or not path.is_file() or path.is_symlink():raise ValueError('Host prerequisite metadata unavailable')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=detail[key]:raise ValueError('Host prerequisite metadata changed')
        paths[key]=path;documents[key]=json.loads(raw)
    receipt=documents['official_queue_sha256'];job=receipt.get('job',receipt);assessment=documents['assessment_sha256']
    if (job.get('id')!=row['job_id'] or job.get('state')!='succeeded' or type(job.get('exit_status'))is not int
            or job['exit_status']!=0 or row.get('queue_state')!='succeeded' or type(row.get('queue_exit_status'))is not int
            or row['queue_exit_status']!=0 or any(job.get(k)!=row.get(k) for k in ('started_at','ended_at'))
            or assessment.get('schema')!='campaign002-host-probe-assessment-1' or assessment.get('diagnostic_passed')is not True
            or set(assessment.get('checks',{}))!=required or any(v is not True for v in assessment['checks'].values())
            or assessment.get('checks')!=row.get('checks') or row.get('failed_checks')!=[] or assessment.get('errors')!={}
            or assessment.get('run_id')!=row['run_id'] or assessment.get('framework_revision')!=row['revision']
            or assessment.get('queue_job_id')!=job['id'] or assessment.get('scorable')is not False
            or assessment.get('task_outcome')!='unknown' or type(assessment.get('model_calls'))is not int or assessment['model_calls']!=0):
        raise ValueError('Host prerequisite original queue or eight-check assessment differs')
    manifest,snapshot=documents['manifest_sha256'],documents['snapshot_sha256']
    script=CAMPAIGN/'qualification/host_probe.py';short=row['run_id'].removeprefix('RCI001-C02-')
    expected=[str(REPO/'venv/Scripts/python.exe'),'-X','utf8','-B',str(script),'run','--manifest',str(paths['manifest_sha256']),
              '--output',str(CAMPAIGN.parent/'local-evidence/campaign002/qualification'/row['run_id'])]
    if (job.get('argv')!=expected or Path(job.get('cwd','')).resolve()!=REPO.resolve()
            or Path(job.get('resolved_executable','')).resolve()!=(REPO/'venv/Scripts/python.exe').resolve()
            or paths['manifest_sha256']!=(CAMPAIGN/'qualification'/(short+'-manifest.json')).resolve()
            or paths['assessment_sha256']!=(CAMPAIGN/'qualification'/(short+'-assessment.json')).resolve()
            or paths['snapshot_sha256'].name!='snapshot.json' or snapshot.get('revision')!=row['revision']
            or manifest.get('run_id')!=row['run_id'] or manifest.get('framework_revision')!=row['revision']
            or manifest.get('qualification_stage')!='campaign002-host-probe-qualification' or manifest.get('mode')!='serve'
            or type(manifest.get('model_turns_max'))is not int or manifest['model_turns_max']!=0):
        raise ValueError('Host prerequisite exact command or manifest/source identity differs')
    for key,name in (('manifest_sha256','manifest'),('snapshot_sha256','snapshot'),('official_queue_sha256','queue')):
        if assessment.get('bindings',{}).get(name)!={'path':str(paths[key]),'sha256':detail[key]}:
            raise ValueError('Host prerequisite original metadata bindings differ')
    source=snapshot.get('sources',{}).get(script.relative_to(REPO).as_posix())
    if (not isinstance(source,dict) or type(source.get('bytes'))is not int or source['bytes']<=0
            or not isinstance(source.get('sha256'),str) or re.fullmatch('[0-9a-f]{64}',source['sha256'])is None):
        raise ValueError('Host prerequisite frozen entry source absent')


def no_model_diagnostic_guard(row, output):
    """Keep metadata and H2 prerequisite passes out of qualification claims."""
    detail = row.get('diagnostic_result')
    schemas = {'raw_event_preflight_diagnostic': {'campaign002-raw-event-preflight-1':'raw_event_preflight.py',
                                                'campaign002-raw-event-preflight-2':'raw_event_preflight_v2.py'},
               'transport_probe_diagnostic': {'campaign002-codehost-probe-1':'codehost_probe.py',
                                              'campaign002-codehost-channel-probe-3':'codehost_transport_probe_v3.py'}}
    keys = {'schema', 'kind', 'result_schema', 'diagnostic_passed', 'qualification_claim',
            'physical_simulation', 'model_calls', 'result_href', 'result_sha256',
            'readiness_entry_href', 'readiness_entry_sha256', 'snapshot_sha256', 'proof_scope', 'scope'}
    if isinstance(detail, dict) and detail.get('result_schema') == 'campaign002-codehost-channel-probe-3':
        keys.add('transport_cases')
    if (not isinstance(detail, dict) or set(detail) != keys
            or detail.get('schema') != 'campaign002-history-diagnostic-1'
            or row.get('attempt_kind') not in schemas or detail.get('kind') != row['attempt_kind']
            or detail.get('result_schema') not in schemas[row['attempt_kind']]
            or detail.get('diagnostic_passed') is not True or detail.get('qualification_claim') is not False
            or detail.get('physical_simulation') is not False
            or type(detail.get('model_calls')) is not int or detail['model_calls'] != 0
            or type(row.get('model_calls')) is not int or row['model_calls'] != 0
            or row.get('status') != 'passed' or row.get('validity') != 'diagnostic_checks_passed'
            or row.get('scorable') is not False or row.get('task_outcome') != 'unknown'
            or row.get('assessment_schema') is not None or row.get('failed_checks') != []
            or row.get('assessment_errors') != {} or row.get('analyses') != []
            or row.get('recorder_subphases_declared') is not False
            or any(row.get(key) is not None for key in ('queue_failure', 'timing', 'supervisory_timing',
                'recorder_feasibility', 'protected_io', 'pilot_admission', 'admission_disposition', 'preflight', 'native_reference'))):
        raise ValueError('No-model diagnostic acquired a qualifier or empirical projection')
    links = row.get('links', [])
    if (len({item.get('label') for item in links}) != len(links)
            or len({item.get('href') for item in links}) != len(links)
            or any(item.get('label') == 'Original assessment' or item.get('href', '').endswith('-assessment.json') for item in links)):
        raise ValueError('No-model diagnostic source identity is ambiguous or impersonates an assessment')

    def read(label, expected_href=None, expected_hash=None):
        selected = [item for item in links if item.get('label') == label]
        if len(selected) != 1:
            raise ValueError('No-model diagnostic missing exact source link: ' + label)
        item = selected[0]
        if ((expected_href is not None and item.get('href') != expected_href)
                or (expected_hash is not None and item.get('sha256') != expected_hash)
                or not isinstance(item.get('href'), str) or urlparse(item['href']).scheme):
            raise ValueError('No-model diagnostic source binding differs')
        path = (Path(output) / unquote(item['href'])).resolve()
        if not path.is_file() or path.is_symlink():
            raise ValueError('No-model diagnostic source is missing or linked')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item.get('sha256'):
            raise ValueError('No-model diagnostic source bytes changed')
        return json.loads(raw), path, item

    receipt, queue_path, official = read('Official queue receipt')
    job = receipt.get('job', receipt)
    if (job.get('id') != row.get('job_id') or job.get('state') != 'succeeded'
            or type(job.get('exit_status')) is not int or job['exit_status'] != 0
            or row.get('queue_state') != 'succeeded' or type(row.get('queue_exit_status')) is not int
            or row['queue_exit_status'] != 0 or job.get('started_at') != row.get('started_at')
            or job.get('ended_at') != row.get('ended_at')):
        raise ValueError('No-model diagnostic lacks successful official queue receipt')
    original, result_path, result_link = read('Original no-model diagnostic result', detail['result_href'], detail['result_sha256'])
    readiness = [item for item in links if item.get('label') in ('Verified v11 readiness entry', 'Verified readiness entry')]
    if len(readiness) != 1:
        raise ValueError('No-model diagnostic requires one exact verified readiness entry')
    entry, _, _ = read(readiness[0]['label'], detail['readiness_entry_href'], detail['readiness_entry_sha256'])
    snapshot, snapshot_path, _ = read('Frozen source snapshot', expected_hash=detail['snapshot_sha256'])
    checks = original.get('checks')
    if (original.get('schema') != detail['result_schema'] or original.get('passed') is not True
            or original.get('run_id') != row['run_id'] or original.get('framework_revision') != row['revision']
            or snapshot.get('revision') != row['revision'] or original.get('snapshot_sha256') != detail['snapshot_sha256']
            or type(original.get('model_calls')) is not int or original['model_calls'] != 0
            or original.get('physical_simulation') is not False or original.get('errors', {}) != {}
            or not isinstance(checks, dict) or not checks or any(value is not True for value in checks.values())
            or row.get('checks') != checks or any(value is not True for value in row['checks'].values())):
        raise ValueError('No-model diagnostic projection differs from original typed pass')
    if (not isinstance(entry, dict) or set(entry) != {'run_id', 'job_id', 'queue', 'result'}
            or entry.get('run_id') != row['run_id'] or entry.get('job_id') != job['id']
            or entry.get('queue') != {'path': str(queue_path), 'sha256': official['sha256']}
            or entry.get('result') != {'path': str(result_path), 'sha256': result_link['sha256']}):
        raise ValueError('No-model diagnostic verified entry does not bind its own queue and result')
    argv = job.get('argv', [])
    script = schemas[detail['kind']][detail['result_schema']]
    if (len(argv) != 13 or argv[1:4] != ['-X', 'utf8', '-B']
            or Path(argv[4]).resolve() != (Path(output).parent / 'harness' / script).resolve()
            or Path(argv[0]).resolve() != Path(job.get('resolved_executable', '')).resolve()
            or Path(argv[0]).resolve() != (Path(job.get('cwd', '')) / 'venv/Scripts/python.exe').resolve()
            or argv[5:] != ['--run-id', row['run_id'], '--framework-revision', row['revision'],
                            '--snapshot', str(snapshot_path), '--output', str(result_path.parent)]
            or result_path.name != 'result.json' or snapshot_path.name != 'snapshot.json'):
        raise ValueError('No-model diagnostic original command/output correspondence differs')
    if detail['result_schema'] == 'campaign002-codehost-channel-probe-3':
        cases = original.get('cases')
        names = ['multi_channel', 'foreign_owner', 'in_flight_eof']
        if not isinstance(cases, list) or [c.get('case') if isinstance(c, dict) else None for c in cases] != names:
            raise ValueError('No-model channel diagnostic lost a fixed case')
        expected = []
        for case in cases:
            negative = case['case'] != 'multi_channel'
            proof = case.get('transport_proof', {})
            if case.get('passed') is not True or not isinstance(proof, dict):
                raise ValueError('No-model channel diagnostic lost its typed proof')
            if negative:
                if (case.get('production_qualified') is not False
                        or proof.get('schema') != 'campaign002-transport-expected-failure-3'
                        or proof.get('case') != case['case'] or proof.get('expected_failure_verified') is not True
                        or proof.get('diagnostic_only') is not True or proof.get('ordinary_transport_passed') is not False
                        or type(proof.get('model_calls')) is not int or proof['model_calls'] != 0
                        or proof.get('physical_simulation') is not False
                        or proof.get('passed') is not None and proof.get('passed') is not False):
                    raise ValueError('Expected negative channel proof acquired production qualification')
            elif (case.get('production_qualified') is not True or proof.get('passed') is not True
                  or proof.get('diagnostic_only') is True):
                raise ValueError('Ordinary multi-channel proof is missing')
            expected.append({'case':case['case'],'diagnostic_passed':True,'production_qualified':not negative,
                'diagnostic_only':negative,'expected_failure_verified':negative,
                'scope':'Expected rejection and retirement only; production transport did not qualify.' if negative
                        else 'Synthetic multi-channel transport only; no model, physics or campaign qualification.'})
        actual = detail.get('transport_cases')
        if (not isinstance(actual, list) or any(not isinstance(c, dict) or any(type(c.get(k)) is not bool
                for k in ('diagnostic_passed','production_qualified','diagnostic_only','expected_failure_verified')) for c in actual)
                or actual != expected):
            raise ValueError('Channel case projection differs from its original diagnostic scope')
    elif detail['kind'] == 'transport_probe_diagnostic':
        cases = original.get('cases')
        if (not isinstance(cases, list) or [case.get('kind') for case in cases] != ['normal', 'reset']
                or any(case.get('passed') is not True or case.get('cleanup_clean') is not True
                       or case.get('h2', {}).get('passed') is not True
                       or case.get('transport_integrity', {}).get('passed') is not True for case in cases)):
            raise ValueError('No-model transport lost one original passing case')
    return [item['href'] for item in links]


def failed_queue_closeout_guard(closeout, rows):
    """A failed queue may bind ongoing/blocked engineering, never qualification."""
    basis = next((row for row in rows if row['run_id'] == closeout.get('basis_run_id')), None)
    if basis is None or basis.get('queue_failure') is None:
        return False
    failure = basis['queue_failure']
    if (closeout.get('state') not in ('qualification_failed_blocked', 'qualification_in_progress')
            or closeout.get('basis_assessment_sha256') is not None
            or closeout.get('basis_queue_sha256') != failure['official_queue_sha256']
            or closeout.get('basis_kind') != 'official_terminal_execution_failure_without_assessment'
            or basis is not latest_completed_qualifier(rows)
            or not any(a.get('sha256') == failure['official_queue_sha256']
                       and a.get('href') == failure['official_queue_href'] for a in closeout.get('links', []))):
        raise ValueError('Failed queue closeout lacks exact latest unassessed receipt basis')
    return True


def verify(output):
    output = Path(output)
    html = (output / 'qualification-report.html').read_text(encoding='utf-8')
    data_raw = (output / 'qualification-data.json').read_bytes()
    data = json.loads(data_raw)
    proof = json.loads((output / 'qualification-provenance.json').read_bytes())
    if hashlib.sha256(html.encode()).hexdigest() != proof['report_sha256'] or hashlib.sha256(data_raw).hexdigest() != proof['data_sha256']:
        raise ValueError('Generated artifact hash mismatch')
    embedded = re.search(r'const DATA = (.*?);\nconst \$', html, flags=re.S)
    if embedded is None or json.loads(embedded.group(1)) != data:
        raise ValueError('Embedded report data differs from the data artifact')
    if (data.get('schema') != 'campaign002-qualification-investigation-1'
            or data.get('empirical_outcome_rows') != 0 or 'runs' in data):
        raise ValueError('Qualification report cannot contain fabricated scored rows')
    counts = data['previous']['counts']
    if [counts.get(k) for k in ('valid', 'successes', 'invalid', 'not_run')] != [6, 6, 4, 14]:
        raise ValueError('Campaign001 fixed counts changed')
    rows = data['history']
    if not rows or len({r['run_id'] for r in rows}) != len(rows):
        raise ValueError('Missing or duplicate history entries')
    urls = [data['previous']['report_href'], data['previous']['data_href'], data['history_href']]
    for row in rows:
        if row['status'] not in ('passed', 'failed', 'cancelled', 'not_run') or row['scorable'] is not False or row['task_outcome'] != 'unknown':
            raise ValueError('Invalid diagnostic classification')
        if row.get('host_prerequisite') is not None or row.get('attempt_kind')=='host_prerequisite_diagnostic':
            host_prerequisite_guard(row,output)
        if row.get('queue_failure') is not None:
            urls.extend(failed_queue_guard(row, output))
        elif row.get('diagnostic_result') is not None or row.get('attempt_kind') in NO_MODEL_DIAGNOSTIC_KINDS:
            no_model_diagnostic_guard(row, output)
        elif row['status'] == 'not_run':
            preflight = row.get('preflight') or {}
            if (row.get('validity') != 'unknown' or row.get('job_id') is not None or row.get('queue_state') is not None
                    or row.get('queue_exit_status') is not None or row.get('started_at') is not None
                    or preflight.get('queue_submitted') is not False or preflight.get('assessment_state') != 'not_assessed'
                    or row.get('timing') is not None or row.get('recorder_feasibility') is not None):
                raise ValueError('Unlaunched preflight acquired a queue result or assessment')
        elif row['status'] == 'cancelled':
            if row['started_at'] is not None or row['queue_state'] not in ('canceled', 'cancelled'):
                raise ValueError('Cancellation was executed')
        elif row['queue_state'] != 'succeeded' or type(row['queue_exit_status']) is not int or row['queue_exit_status'] != 0:
            raise ValueError('Unqualified official receipt')
        if row.get('queue_failure') is None:
            urls.extend(diagnostic_links_guard(row.get('diagnostic_links', []), output, row['links']))
        timing = row.get('timing')
        if timing and timing['basis'] == 'diagnostic_only' and (timing['strict_passed'] is not None or timing['strict_verification_available'] is not False):
            raise ValueError('Raw diagnostics promoted to a strict timing verdict')
        feasibility = row.get('recorder_feasibility')
        pilot = row.get('pilot_admission')
        admission = row.get('admission_disposition')
        if admission and (type(admission.get('admission_passed')) is not bool
                or admission['admission_passed'] is not (row['status'] == 'passed')
                or type(admission.get('original_raw_passed')) is not bool
                or (admission['admission_passed'] and not admission['original_raw_passed'])):
            raise ValueError('History promoted or changed original suite/admission decisions')
        if pilot and (type(pilot.get('admission_passed')) is not bool
                or pilot['admission_passed'] is not (row['status'] == 'passed')
                or (pilot['admission_passed'] and (pilot.get('original_validity') != 'valid'
                    or pilot.get('task_evidence_valid') is not True
                    or pilot.get('assessed_task_outcome') not in ('success','failure')))):
            raise ValueError('Pilot apparatus admission contradicts original task evidence')
        if feasibility and (feasibility.get('production_adopted') is not False
                or feasibility.get('scorable') is not False or feasibility.get('task_outcome') != 'unknown'
                or type(feasibility.get('model_calls')) is not int or feasibility['model_calls'] != 0
                or len(feasibility.get('rounds', [])) != 8 or len(feasibility.get('recovery_checks', [])) != 4
                or feasibility.get('mechanical_feasibility_passed') is not (row['status'] == 'passed')):
            raise ValueError('Synthetic mechanical evidence was pooled, truncated or promoted')
        urls.extend(link['href'] for link in row['links'])
        urls.extend(analysis['href'] for analysis in row['analyses'])
        if timing:
            urls.append(timing['metadata_href'])
            urls.extend(link['href'] for link in timing['samples'])
    for entry in proof['inputs']:
        raw = Path(entry['path']).read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Consumed evidence changed after build: ' + entry['path'])
    inv = data['scored_launch_inventory']
    if (inv['state'] == 'no_scored_launch_recorded') != (not inv['entries']):
        raise ValueError('Launch state contradicts inventoried records')
    closeout = data.get('qualification_closeout')
    if closeout:
        basis = next((row for row in rows if row['run_id'] == closeout['basis_run_id']), None)
        state = closeout.get('state')
        earlier = state in ('qualification_failed_blocked','qualification_in_progress')
        current = not inv['entries'] if earlier else True
        queue_basis = failed_queue_closeout_guard(closeout, rows)
        if (basis is None or basis.get('diagnostic_result') is not None or state not in ('qualification_failed_blocked','qualification_in_progress',
                                          'qualified_campaign_in_progress','campaign_terminal')
                or (state == 'qualification_failed_blocked' and basis['status'] != 'failed')
                or (state != 'qualification_failed_blocked' and basis is not
                    latest_completed_qualifier(rows))
                or (not queue_basis and not any(a['sha256'] == closeout.get('basis_assessment_sha256')
                           and (a['href'].endswith('-assessment.json') or
                                (basis.get('assessment_schema') == 'campaign002-boundary-suite-1'
                                 and a['href'].endswith('suite-result.json'))) for a in basis['links']))
                or closeout['current_for_launch_inventory'] != current
                or data['qualification_state'] != (state if current else 'preserved_qualification_history')):
            raise ValueError('Closeout state contradicts completed evidence or launch inventory')
        if not earlier and (len(set(closeout.get('final_qualification_run_ids', []))) != 5
                            or any(next((r['status'] for r in rows if r['run_id'] == identity),None) != 'passed'
                                   for identity in closeout['final_qualification_run_ids'])):
            raise ValueError('Qualified state lacks five passed final-stage bindings')
        if state == 'campaign_terminal' and (closeout.get('terminal_disposition_count') != 20
                                             or len(closeout.get('terminal_dispositions',[])) != 20):
            raise ValueError('Terminal state lacks twenty terminal disposition bindings')
        urls.extend(item['href'] for item in closeout.get('links', []))
    urls.append(inv['operator_href'])
    urls.extend(e['href'] for e in inv['entries'])
    if inv.get('registration'):
        urls.append(inv['registration']['href'])
    if data.get('empirical_report_href'):
        urls.append(data['empirical_report_href'])
    for url in urls:
        if urlparse(url).scheme or not (output / unquote(url)).is_file():
            raise ValueError('Missing or non-local evidence link: ' + url)
    result = static_html(html)
    result.update({'history_records': len(rows), 'scored_outcome_rows': 0, 'verified_input_records': len(proof['inputs']),
                   'evidence_links': len(urls), 'scope': 'Static syntax, local links and byte integrity; browser layout is a separate check.'})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    result = static_html((HERE / 'qualification_template.html').read_text(encoding='utf-8')) if args.source_only else verify(args.output)
    print(json.dumps(result, indent=2))
