"""Freeze Session 10 source/attempt bytes and append honest development evidence.

This operator-only helper never launches a model, robot, or queue job. A new
revision directory is immutable; existing directories and IDs are never reused.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
READINESS = HERE.parent
INTEGRATION = READINESS.parent
EXPERIMENT = INTEGRATION.parent
REPO = EXPERIMENT.parent
MAP = EXPERIMENT / 'Architecture Map'
spec = importlib.util.spec_from_file_location('session10_architecture_map', MAP / 'map.py')
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)
ARCHITECTURE = 'RCI001'
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]*$')
SKIP = {'__pycache__', 'records', 'probes', 'local-evidence', 'protected-canaries', '.git'}
EXTENSIONS = {'.py', '.md', '.json', '.toml', '.txt', '.sh', '.ps1'}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return am.strict_json(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def valid_id(value):
    # IDs also become Windows filenames: colon, traversal and reserved names fail.
    if not isinstance(value, str) or not ID.fullmatch(value) or ':' in value or value in {'.', '..'}:
        raise ValueError('Invalid filesystem-safe immutable ID')
    if value.rstrip('. ').upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1, 10)), *('LPT'+str(i) for i in range(1, 10))}:
        raise ValueError('Reserved immutable ID')
    return value


def reference(root, label, path, access='operator'):
    path = Path(path).resolve(strict=True)
    return {'label': label, 'uri': Path(os.path.relpath(path, root)).as_posix(),
            'sha256': digest(path.read_bytes()), 'state': 'available', 'access': access, 'locator': None}


def recorded(ref):
    return {'state': 'recorded', 'refs': [ref], 'reason': None}


def common(identifier):
    return {'schema_version': am.SCHEMA, 'id': identifier, 'recorded_at': now(),
            'author': 'Development Codex session 10',
            'tags': ['robot-codex-integration-001', 'readiness-session-10', 'development-only'], 'details': {}}


def store(root, expected=None):
    data, raw, errors = am.read_store(root)
    errors += am.validate_records(data, root)
    if errors:
        raise ValueError('; '.join(errors))
    actual = am.store_digest(raw)
    if expected is not None and expected != actual:
        raise ValueError('Architecture store changed; inspect the current store before retrying')
    return data, raw, actual


def capture_sources(manifest):
    """Only bounded implementation/template trees; no logs or credential roots."""
    trees = [INTEGRATION / name for name in ('host', 'launch', 'runtime-template', 'smoke-template')]
    trees += [INTEGRATION / 'isolation-session-9' / name for name in ('wsl', 'native')]
    trees += [READINESS / name for name in ('boundary', 'orchestrator', 'templates', 'registration')]
    trees += [REPO / 'Robot Agent Filesystem v0.1']
    paths = set()
    for tree in trees:
        if not tree.is_dir():
            raise ValueError('Required source tree missing: ' + str(tree))
        for path in tree.rglob('*'):
            if set(path.relative_to(tree).parts) & SKIP:
                continue
            if path.is_symlink():
                raise ValueError('Symlink source not permitted: ' + str(path))
            if path.is_file() and path.suffix.lower() in EXTENSIONS:
                paths.add(path)
    for tree in (EXPERIMENT / 'Runtime 004', EXPERIMENT / 'Storage Retention Implementation 001/future'):
        sources = list(tree.glob('*.py'))
        if not sources:
            raise ValueError('Required runtime sources missing: ' + str(tree))
        paths.update(sources)
    paths.update([INTEGRATION / 'provenance.py', INTEGRATION / 'register.py',
                  REPO / 'requirements.txt', EXPERIMENT / 'Runtime 004/vendor/panda/manifest.json',
                  EXPERIMENT / 'Evidence/prepared-artifacts/batch01-eval-r4-final/code.json'])
    extra = manifest.get('runtime_input_files', [])
    if not isinstance(extra, list) or any(not isinstance(item, str) for item in extra):
        raise ValueError('runtime_input_files must be a list of repository-relative paths')
    for name in extra:
        path = REPO / name
        if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve(strict=True).is_relative_to(REPO):
            raise ValueError('Runtime input escapes repository')
        paths.add(path)
    payloads = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or symlink source: ' + str(path))
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError('Source file exceeds bounded snapshot size: ' + str(path))
        payloads[path.relative_to(REPO).as_posix()] = path.read_bytes()
    if sum(map(len, payloads.values())) > 64 * 1024 * 1024:
        raise ValueError('Source snapshot exceeds 64 MiB')
    return payloads


def environment():
    versions = {}
    for package in ('mujoco', 'numpy', 'websockets', 'grpcio', 'protobuf'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {'python': platform.python_version(), 'platform': platform.platform(), 'packages': versions}


def refresh(root):
    for command in (['build'], ['validate', '--output', 'validation.json']):
        if am.main(['--root', str(root), *command]):
            raise ValueError('Architecture map refresh failed')


def prepare(args):
    root = args.map_root.resolve()
    revision, run_id = valid_id(args.revision), valid_id(args.run_id)
    data, raw, expected = store(root, args.expected_sha256)
    known = {r['id'] for records in data.values() for r in records}
    if ARCHITECTURE not in known or revision in known or run_id in known or revision == run_id:
        raise ValueError('Existing architecture and unused distinct revision/run IDs required')
    manifest_bytes = args.manifest.read_bytes()
    manifest = am.strict_json(manifest_bytes.decode('utf-8'))
    if manifest.get('run_id') != run_id or manifest.get('stage') not in {'development-only', 'development', 'diagnostic'}:
        raise ValueError('Matching run_id and explicitly bounded development/diagnostic stage required')
    condition = manifest.get('qualification_stage') or manifest.get('mode')
    if not isinstance(condition, str) or not condition.strip():
        raise ValueError('Manifest needs a qualification_stage or mode')
    payloads = capture_sources(manifest)
    directory = root / 'releases' / revision
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'manifest.json').write_bytes(manifest_bytes)
    mechanism = args.mechanism.read_text(encoding='utf-8') if args.mechanism else (
        'The unchanged Runtime 004 conventional controller and native simulation continue while a protected host '
        'uses public evidence to grant exclusive recovery ownership. A trusted Windows ChatGPT-authenticated '
        'GPT-6 Astra Max client uses the exact RobotAgentPrompt bootstrap with credential-free WSL2/bubblewrap '
        'executor and Code Mode namespaces. Only runtime files and a fixed authenticated robot broker are visible. '
        'Protected host journals action identities before dispatch, fences ownership and generations, and checks '
        'handback against public observations. Fresh invocations reconcile continuity with current public history. '
        'Agent-written shell/Python scripts are an explicit capability inside the invocation boundary: all robot '
        'calls retain action/observation budgets and lifecycle retirement. There is no independent persistent '
        'program service. Exact limits, stage tasks, retained artifacts and qualification results belong to the '
        'linked manifest and evidence; registration does not establish that these mechanisms passed qualification. '
        'No complete supervisor/computer restart guarantee, general collision safety or performance claim is made.')
    (directory / 'mechanism.md').write_text(mechanism, encoding='utf-8', newline='\n')
    with zipfile.ZipFile(directory / 'code.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(payloads.items()):
            archive.writestr(name, payload)
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    except subprocess.CalledProcessError:
        commit = None
    snapshot = {'schema': 'robot-codex-readiness-source-1', 'revision': revision, 'run_id': run_id,
                'created_at': now(), 'git_head_at_freeze': commit,
                'sources': {name: {'sha256': digest(raw), 'bytes': len(raw)} for name, raw in sorted(payloads.items())},
                'environment': environment(), 'model_requested': 'gpt-6-astra', 'reasoning_requested': 'max',
                'authentication_requested': 'existing ChatGPT subscription; no API key',
                'bootstrap': 'Follow the instructions in RobotAgentPrompt.md.',
                'manifest_sha256': digest(manifest_bytes),
                'qualification_status': 'unestablished; consult separately appended result',
                'assets': 'Large vendor assets are referenced by their frozen vendor manifest, not duplicated or reverified by this helper.'}
    write_new(directory / 'snapshot.json', snapshot)
    code_ref = reference(root, 'Exact implementation and runtime templates', directory / 'code.zip')
    snapshot_ref = reference(root, 'Source hashes and requested environment', directory / 'snapshot.json')
    manifest_ref = reference(root, 'Protected immutable development attempt manifest', directory / 'manifest.json', 'evaluator_only')
    previous = [r for r in data['revision'] if r['architecture_id'] == ARCHITECTURE]
    revision_record = {**common(revision), 'architecture_id': ARCHITECTURE,
        'parent_revision_id': previous[-1]['id'] if previous else None, 'status': 'implemented',
        'title': 'Isolated Robot-Codex readiness ' + revision,
        'summary': 'Exact bounded development source and configuration; actual qualification is recorded separately.',
        'mechanism': mechanism,
        'attachments': [code_ref, snapshot_ref, manifest_ref, reference(root, 'Mechanism and limitations', directory / 'mechanism.md')]}
    run_record = {**common(run_id), 'revision_id': revision,
        'stage': 'diagnostic' if manifest['stage'] == 'diagnostic' else 'development',
        'condition_id': condition, 'protocol_id': 'RCI001-readiness-session10-v1',
        'scenario_id': manifest.get('family', manifest.get('scenario_id', 'isolated-readiness-' + condition)),
        'paired_block_id': 'unpaired-' + run_id, 'replicate': 1, 'started_at': None,
        'rerun_of_run_id': manifest.get('rerun_of_run_id', manifest.get('rerun_of')),
        'condition_details': {'manifest': manifest, 'scope': 'One predeclared readiness attempt; no comparative performance inference'},
        'seeds': recorded(manifest_ref),
        'frozen_refs': {'code': recorded(code_ref), 'environment': recorded(snapshot_ref),
                        'models': recorded(snapshot_ref), 'protocol': recorded(manifest_ref), 'scenario': recorded(manifest_ref)},
        'evidence': [manifest_ref]}
    proposed = {kind: list(records) for kind, records in data.items()}
    proposed['revision'].append(revision_record)
    proposed['run'].append(run_record)
    errors = am.validate_records(proposed, root)
    if errors:
        raise ValueError('; '.join(errors))
    write_new(directory / 'revision-record.json', revision_record)
    write_new(directory / 'run-record.json', run_record)
    am.append_record(root, 'revision', revision_record, expected)
    # Predict our own append's exact digest. Do not silently accept concurrent writes.
    revision_line = (json.dumps(revision_record, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()
    raw[am.KINDS['revision']] += revision_line
    am.append_record(root, 'run', run_record, am.store_digest(raw))
    refresh(root)
    return {'revision': revision, 'run_id': run_id, 'snapshot': str(directory / 'snapshot.json'), 'source_files': len(payloads)}


def verify(args):
    snapshot = read_json(args.snapshot)
    problems = []
    for name, expected in snapshot['sources'].items():
        path = REPO / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.is_file():
            problems.append(name + ': invalid or absent source')
        elif digest(path.read_bytes()) != expected['sha256']:
            problems.append(name + ': source changed')
    if problems:
        raise ValueError('; '.join(problems))
    return {'verified': True, 'source_files': len(snapshot['sources']), 'revision': snapshot['revision']}


def finish(args):
    root = args.map_root.resolve()
    run_id = valid_id(args.run_id)
    data, _, expected = store(root, args.expected_sha256)
    run = next((r for r in data['run'] if r['id'] == run_id), None)
    if run is None:
        raise ValueError('Unknown run')
    if any(r['run_id'] == run_id for r in data['result']):
        raise ValueError('Run already has a result; use an explicit map correction record')
    result = read_json(args.result)
    if result.get('run_id') not in (None, run_id):
        raise ValueError('Result run_id differs from registered attempt')
    receipt = read_json(args.queue_receipt) if args.queue_receipt else None
    job = receipt.get('job', receipt) if receipt else None
    queue_ok = job is not None and job.get('state') == 'succeeded' and job.get('exit_status') == 0
    if args.execution_status == 'not_run':
        if args.validity != 'unknown' or args.outcome != 'not_assessed':
            raise ValueError('Not-run records require unknown validity and unassessed outcome')
    elif not queue_ok and not (args.validity == 'invalid' and args.outcome in {'unknown', 'not_assessed'}):
        raise ValueError('Only succeeded/exit0 queue results support ordinary assessed outcomes; failed receipts may preserve invalid infrastructure diagnostics')
    directory = root / 'releases' / run['revision_id'] / ('result-' + run_id)
    directory.mkdir(exist_ok=False)
    (directory / 'result.json').write_bytes(args.result.read_bytes())
    refs = [reference(root, 'Retained readiness result', directory / 'result.json', 'evaluator_only')]
    if receipt is not None:
        (directory / 'queue.json').write_bytes(args.queue_receipt.read_bytes())
        refs.append(reference(root, 'Original shared queue terminal receipt', directory / 'queue.json'))
    for pos, path in enumerate(args.evidence):
        refs.append(reference(root, 'Supporting evidence ' + str(pos + 1), path))
    record = {**common(run_id + '-result'), 'run_id': run_id, 'supersedes_result_id': None,
              'execution_status': args.execution_status, 'validity': args.validity, 'validity_reason': args.reason,
              'outcome': args.outcome, 'ended_at': None if args.execution_status == 'not_run' else result.get('ended_at', now()),
              'termination_reason': args.termination, 'metrics': [], 'evidence': refs}
    record['details'] = {'source_result': result, 'queue_success_verified': queue_ok,
                         'scope': 'Development qualification only; no general performance inference'}
    write_new(directory / 'result-record.json', record)
    am.append_record(root, 'result', record, expected)
    refresh(root)
    return {'result': record['id'], 'outcome': args.outcome, 'validity': args.validity}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-root', type=Path, default=MAP)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--revision', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--mechanism', type=Path)
    p.add_argument('--expected-sha256')
    p = sub.add_parser('verify')
    p.add_argument('--snapshot', type=Path, required=True)
    p = sub.add_parser('finish')
    p.add_argument('--run-id', required=True)
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--queue-receipt', type=Path)
    p.add_argument('--execution-status', required=True, choices=sorted(am.ENUMS['execution_status']))
    p.add_argument('--validity', required=True, choices=sorted(am.ENUMS['validity']))
    p.add_argument('--outcome', required=True, choices=sorted(am.ENUMS['outcome']))
    p.add_argument('--reason', required=True)
    p.add_argument('--termination', required=True)
    p.add_argument('--evidence', action='append', type=Path, default=[])
    p.add_argument('--expected-sha256')
    args = parser.parse_args(argv)
    print(json.dumps({'prepare': prepare, 'verify': verify, 'finish': finish}[args.command](args), indent=2))


if __name__ == '__main__':
    main()
