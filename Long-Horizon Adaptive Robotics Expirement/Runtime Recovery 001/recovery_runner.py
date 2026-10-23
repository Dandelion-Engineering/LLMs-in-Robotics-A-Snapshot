"""Explicit administrative successor for untouched r4 manifests only.

Original physical/policy modules, release files and artifact verification remain
in Runtime 004. This module owns a separate, annex-gated execution authority.
It never supplies the original runner's private authority or generates seeds.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass, field
import inspect
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'recovery_runner.py'
FROZEN_RUNTIME = HERE.parent / 'Runtime 004'
if str(FROZEN_RUNTIME) not in sys.path:
    sys.path.insert(0, str(FROZEN_RUNTIME))
import release_runner as original
if Path(original.__file__).resolve() != FROZEN_RUNTIME / 'release_runner.py':
    raise RuntimeError('Recovery must import the actual original release runner')

AUTHORIZATION_VERSION = 'robot-evaluation-recovery-authorization-1.0'
_AUTHORITY = object()
ReleaseError = original.ReleaseError
IntegrityError = original.IntegrityError
INSTALLED_QUEUE_SHA256 = '31997fc851494df62c2466cf189b5e945a6a933464f5cd43e69b3d877c029829'
INSTALLED_QUEUE_MODULE = original.QUEUE_HOME / 'compute_queue.py'
_QUEUE_LOCK_MODULE_NAME = '_robot_recovery_queue_lock_001'


def _read_shared_json(path):
    """Close-before-return snapshot; sharing alone does not permit replacement."""
    path = Path(path).resolve()
    if os.name != 'nt':
        return original.load(path)
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    size = kernel.GetFileSizeEx
    size.argtypes = (wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)); size.restype = wintypes.BOOL
    read = kernel.ReadFile
    read.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p); read.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,); close.restype = wintypes.BOOL
    handle = create(str(path), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), 'Cannot read shared queue snapshot')
    try:
        length = ctypes.c_longlong()
        if not size(handle, ctypes.byref(length)):
            raise OSError(ctypes.get_last_error(), 'Cannot size shared queue snapshot')
        if not 0 < length.value <= 64 * 1024 * 1024:
            raise ReleaseError('Queue snapshot exceeds bounded reader size')
        remaining = length.value; chunks = []
        while remaining:
            buffer = ctypes.create_string_buffer(min(remaining, 128 * 1024)); count = wintypes.DWORD()
            if not read(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise OSError(ctypes.get_last_error(), 'Cannot read shared queue snapshot')
            if not count.value:
                raise ReleaseError('Queue snapshot ended before its recorded size')
            chunks.append(buffer.raw[:count.value]); remaining -= count.value
    finally:
        close(handle)
    return json.loads(b''.join(chunks).decode('utf-8'))


def _installed_queue_lock():
    """Pin the installed lock implementation before any ownership snapshot."""
    path = INSTALLED_QUEUE_MODULE.resolve()
    if original.digest(path) != INSTALLED_QUEUE_SHA256:
        raise ReleaseError('Installed queue source differs from the adopted lock/liveness implementation')
    module = sys.modules.get(_QUEUE_LOCK_MODULE_NAME)
    if module is None:
        spec = importlib.util.spec_from_file_location(_QUEUE_LOCK_MODULE_NAME, path)
        if spec is None or spec.loader is None:
            raise ReleaseError('Cannot load the exact installed queue lock')
        module = importlib.util.module_from_spec(spec)
        sys.modules[_QUEUE_LOCK_MODULE_NAME] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(_QUEUE_LOCK_MODULE_NAME, None)
            raise
    if (Path(getattr(module, '__file__', '')).resolve() != path
            or original.digest(path) != INSTALLED_QUEUE_SHA256):
        raise ReleaseError('Installed queue lock module location/source differs')
    return module.ExclusiveFileLock


def read_shared_json(path):
    """Serialize only the exact production queue snapshot with its existing lock.

    No queue state save, service call or worker lease action occurs. The snapshot
    handle closes before lock release; ownership/CIM checks and sleeps occur only
    after return. Other paths use the raw reader, without acquiring queue locks.
    """
    path = Path(path).resolve()
    if path != original.QUEUE_STATE.resolve():
        return _read_shared_json(path)
    lock = _installed_queue_lock()
    try:
        with lock(path.with_name('state.lock')):
            return _read_shared_json(path)
    except Exception as error:
        raise ReleaseError('Serialized queue snapshot failed: ' + type(error).__name__ + ': ' + str(error)) from error


def queued_job(expected_script=None):
    """Original exact entrypoint/venv checks with a serialized ownership snapshot."""
    expected = Path(expected_script or SCRIPT).resolve()
    if not sys.argv or Path(sys.argv[0]).resolve() != expected:
        raise ReleaseError('Actual entrypoint differs from expected recovery command')
    current_pid, parent_pid = os.getpid(), os.getppid()
    eligible = {current_pid, parent_pid} if sys.platform == 'win32' else {current_pid}
    for _ in range(30):
        jobs = read_shared_json(original.QUEUE_STATE).get('jobs', [])
        matches = [j for j in jobs if j.get('state') == 'running'
                   and type(j.get('child_pid')) is int and j['child_pid'] in eligible]
        if len(matches) > 1:
            raise ReleaseError('Ambiguous installed queue ownership')
        if matches:
            job = matches[0]; cwd = job.get('cwd', '')
            if (not isinstance(cwd, str) or not Path(cwd).is_absolute()
                    or original.python_entrypoint(job.get('argv'), cwd) != expected):
                raise ReleaseError('Queued command is not this exact recovery entrypoint')
            if job['child_pid'] != current_pid:
                original.verify_windows_venv_parent(job, current_pid, parent_pid)
            return job
        time.sleep(.05)
    raise ReleaseError('Execution requires this installed queue child or verified direct venv interpreter')


def _contract(annex_path, release_dir=None):
    import recovery_contract
    if Path(recovery_contract.__file__).resolve() != HERE / 'recovery_contract.py':
        raise ReleaseError('Recovery contract imported from another location')
    checked = recovery_contract.verify_annex(annex_path, release_dir=release_dir, require_adopted=True)
    ref = checked.get('source_index_ref', checked['annex'].get('source_index'))
    if not isinstance(ref, dict):
        raise ReleaseError('Verified annex lacks an explicit source-index reference')
    index_path = original.reference(ref, Path(checked['annex_ref']['path']).parent)
    if original.load(index_path) != checked['source_index']:
        raise ReleaseError('Returned source index differs from retained bytes')
    checked['source_index_ref'] = {'path': str(index_path), 'sha256': ref['sha256']}
    return checked


def _partition(verified, checked):
    ordered = [m['run_id'] for m in sorted(verified['manifests'], key=lambda m: m['scheduled_index'])]
    groups = [checked[key] for key in ('allowed_run_ids', 'retained_run_ids', 'administrative_run_ids')]
    if [len(g) for g in groups] != [131, 132, 1]:
        raise ReleaseError('Recovery partition must remain exactly 131/132/1')
    if any(len(g) != len(set(g)) for g in groups) or len(set().union(*map(set, groups))) != 264:
        raise ReleaseError('Recovery partition is duplicated or overlapping')
    if set().union(*map(set, groups)) != set(ordered):
        raise ReleaseError('Recovery partition differs from the original complete release')
    if groups[0] != [identity for identity in ordered if identity in set(groups[0])]:
        raise ReleaseError('Recovery allowed order differs from original schedule')
    if len(checked['administrative_batch_ids']) != 1:
        raise ReleaseError('Exactly one historical batch disposition is permitted')
    if set(checked['dispositions']) != set(groups[2]):
        raise ReleaseError('Historical attempt lacks its exact verified disposition')


def verify_recovery(annex_path, release_dir=None):
    checked = _contract(annex_path, release_dir)
    verify_administrative_notes(checked)
    verified = original.verify_release(checked['root'])  # Unchanged heavy gate.
    if Path(verified['root']).resolve() != Path(checked['root']).resolve():
        raise ReleaseError('Original release and recovery root differ')
    _partition(verified, checked)
    return {**verified, 'recovery': checked}


def verify_administrative_notes(checked):
    """An adopted annex does not silently stand in for its canonical typed note."""
    import record_attempt as records
    data, _, errors = records.am.read_store(records.MAP)
    if errors:
        raise ReleaseError(str(errors))
    for entry in checked['annex']['administrative_dispositions']:
        matches = [n for n in data['note']
                   if n.get('details', {}).get('provenance_kind') == 'administrative_interruption'
                   and entry['run_id'] in n.get('target_ids', [])]
        if len(matches) != 1 or matches[0].get('id') != entry['expected_canonical_note_id']:
            raise ReleaseError('Required canonical administrative interruption note is absent or duplicated')
        note = matches[0]; details = note.get('details', {})
        if (note.get('target_ids') != [entry['run_id']] or note.get('claim_type') != 'decision'
                or note.get('supersedes_note_id') is not None
                or any(other.get('supersedes_note_id') == note['id'] for other in data['note'])
                or details.get('provenance_kind') != 'administrative_interruption'
                or details.get('recovery_annex_ref') != checked['annex_ref']
                or details.get('administrative_disposition_ref') != entry['disposition_ref']):
            raise ReleaseError('Canonical administrative note does not match exact adopted disposition')


def _refs(checked):
    return {'recovery_annex_ref': checked['annex_ref'],
            'recovery_source_index_ref': checked['source_index_ref']}


def _require_refs(record, checked):
    if any(record.get(key) != value for key, value in _refs(checked).items()):
        raise ReleaseError('Recovery record differs from adopted annex/source index')


def assert_original_module_locations():
    for path in FROZEN_RUNTIME.glob('*.py'):
        module = sys.modules.get(path.stem)
        if module is not None and Path(getattr(module, '__file__', '')).resolve() != path.resolve():
            raise ReleaseError('Frozen module imported from another location: ' + path.stem)


@dataclass(frozen=True)
class RecoveryEvaluationContext:
    release_dir: Path
    manifest_json: str
    release_sha256: str
    manifest_sha256: str
    queue_job_id: str
    verified_at: str
    artifacts_json: str
    recovery_json: str
    _authority: object = field(repr=False, compare=False, default=None)

    def _require_authority(self):
        if self._authority is not _AUTHORITY:
            raise ReleaseError('Recovery context was not issued by its gated authorizer')

    @property
    def manifest(self):
        return json.loads(self.manifest_json)

    @property
    def recovery(self):
        self._require_authority(); return json.loads(self.recovery_json)

    @property
    def execution_provenance(self):
        value = self.recovery
        return {'authorization_version': AUTHORIZATION_VERSION, **_refs(value),
                'execution_authority': {'path': str(SCRIPT), 'sha256': original.digest(SCRIPT)},
                'physical_runtime_root': str(FROZEN_RUNTIME)}

    @property
    def restart_qualification(self):
        self._require_authority()
        return json.loads(self.artifacts_json).get('restart_qualification')

    @property
    def evidence_dir(self):
        return self.release_dir / 'attempts' / self.manifest['run_id'] / 'evidence'

    @property
    def public_episode_id(self):
        m = self.manifest
        return original.matched_public_episode_id(m['release_id'], m['paired_block_id'], m['architecture'])

    @property
    def revision_id(self):
        m = self.manifest
        return self.recovery['revision_ids'][m['architecture']]

    def episode_kwargs(self):
        m = self.manifest
        return {'kind': m['architecture'], 'n': m['parts'], 'cap': m['cap_s'], 'condition': m['condition'],
                'scenario': m['scenario'], 'stage': 'evaluation', 'run_id': m['run_id'],
                **m['seeds'], 'evaluation_context': self}

    def assert_episode(self, **actual):
        self._require_authority()
        expected = self.episode_kwargs(); expected.pop('evaluation_context')
        if actual != expected:
            raise ReleaseError('Supervisor arguments differ from exact original authorized manifest')
        if self.evidence_dir.exists():
            raise ReleaseError('Recovery episode evidence directory is not fresh')
        assert_original_module_locations()
        return self.evidence_dir


def _authorize(manifest, release_dir, annex_path):
    job = queued_job(); verified = verify_recovery(annex_path, release_dir)
    checked = verified['recovery']
    actual = next((m for m in verified['manifests'] if m['run_id'] == manifest.get('run_id')), None)
    if actual is None or actual != manifest or actual['run_id'] not in checked['allowed_run_ids']:
        raise ReleaseError('Manifest is not an exact untouched member authorized by the annex')
    if (verified['root'] / 'attempts' / actual['run_id']).exists() or actual['run_id'] in _registered_ids():
        raise ReleaseError('Context cannot be issued for an already claimed/registered attempt')
    ref = next(r for r in verified['release']['manifest_refs'] if r['run_id'] == actual['run_id'])
    retained = {'annex_ref': checked['annex_ref'], 'source_index_ref': checked['source_index_ref'],
                'source_index': checked['source_index'],
                'revision_ids': checked['annex']['revision_ids'],
                'parent_revision_ids': checked['annex']['parent_revision_ids']}
    context = RecoveryEvaluationContext(verified['root'], original.protocol.canonical(actual).decode(),
        verified['release_sha256'], ref['sha256'], job['id'], original.utc(),
        original.protocol.canonical(verified['artifacts']).decode(),
        original.protocol.canonical(retained).decode(), _AUTHORITY)
    return context, verified


def authorize_evaluation(manifest, release_dir, annex_path):
    return _authorize(manifest, release_dir, annex_path)[0]


def require_supervisor_hook():
    import experiment_recovery
    if Path(experiment_recovery.__file__).resolve() != HERE / 'experiment_recovery.py':
        raise ReleaseError('Recovery supervisor imported from another location')
    required = {'evaluation_context', 'world_seed', 'layout_seed', 'policy_seed', 'noise_seed'}
    if (experiment_recovery.EVALUATION_AUTHORIZATION_VERSION != AUTHORIZATION_VERSION
            or not required <= set(inspect.signature(experiment_recovery.run_episode).parameters)):
        raise ReleaseError('Recovery supervisor lacks the exact gated four-seed context hook')
    assert_original_module_locations()
    return experiment_recovery.run_episode


def continuation_state(verified):
    state = original.continuation_state(verified)
    checked = verified['recovery']; administrative = set(checked['administrative_run_ids'])
    blocks = {m['paired_block_id'] for m in verified['manifests'] if m['run_id'] in administrative}
    return {**state, **_refs(checked),
            'administrative_dispositions': checked['dispositions'],
            'excluded_paired_block_ids': sorted(set(state['excluded_paired_block_ids']) | blocks)}


def _registered_ids():
    import record_attempt as records
    data, _, errors = records.am.read_store(records.MAP)
    if errors:
        raise ReleaseError(str(errors))
    return {r['id'] for r in data['run']} | {r['run_id'] for r in data['result']}


def select_runs(verified, run_ids=None, limit=4, *, _active_batch=None):
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ReleaseError('Batch limit must be 1 through 16')
    root = verified['root']; checked = verified['recovery']; allowed = checked['allowed_run_ids']
    administrative = set(checked['administrative_run_ids'])
    admin_batches = set(checked['administrative_batch_ids'])
    continuation = continuation_state(verified)
    for batch in (root / 'batches').iterdir() if (root / 'batches').exists() else []:
        if not batch.is_dir():
            continue
        if batch.name in admin_batches:
            continue  # Only this exact byte-bound historical disposition.
        if _active_batch and batch.name == _active_batch.get('queue_job_id'):
            if original.reference(_active_batch, root) != batch / 'planned.json':
                raise ReleaseError('Active recovery batch reference differs')
            planned = original.load(batch / 'planned.json'); _require_refs(planned, checked)
            if (planned.get('schema_version') != AUTHORIZATION_VERSION
                    or planned.get('queue_job_id') != batch.name
                    or not set(run_ids or []) <= set(planned.get('selected_run_ids', []))):
                raise ReleaseError('Current in-progress batch does not authorize this selection')
            continue
        if not (batch / 'finalized.json').is_file():
            raise ReleaseError('Unfinalized batch prevents continuation: ' + batch.name)
        planned = original.load(batch / 'planned.json')
        if planned.get('schema_version') == AUTHORIZATION_VERSION:
            _require_refs(planned, checked)
            _require_refs(original.load(batch / 'finalized.json'), checked)
    for attempt in (root / 'attempts').iterdir() if (root / 'attempts').exists() else []:
        if not attempt.is_dir():
            continue
        if attempt.name in administrative:
            if attempt.name not in checked['dispositions']:
                raise ReleaseError('Administrative attempt lacks verified disposition')
            continue
        if not (attempt / 'terminal.json').is_file():
            raise ReleaseError('Unresolved attempt prevents continuation: ' + attempt.name)
        terminal = original.load(attempt / 'terminal.json')
        if attempt.name in allowed:
            _require_refs(terminal, checked)
        if original.integrity_breach(terminal):
            raise IntegrityError('Prior integrity breach blocks continuation: ' + attempt.name)
        if terminal.get('result', {}).get('validity') != 'valid' and attempt.name not in continuation['covered_attempts']:
            raise ReleaseError('Prior invalid attempt requires an exact continuation review: ' + attempt.name)
    registered = _registered_ids()
    for identity in allowed:
        if identity in registered and not (root / 'attempts' / identity).exists():
            raise ReleaseError('Registered attempt lost its evidence directory; retry forbidden: ' + identity)
    eligible = [identity for identity in allowed if not (root / 'attempts' / identity).exists()]
    if run_ids:
        if len(set(run_ids)) != len(run_ids) or len(run_ids) > limit or not set(run_ids) <= set(eligible):
            raise ReleaseError('Explicit recovery IDs must be unique, untouched, allowed and within limit')
        selected = [identity for identity in eligible if identity in set(run_ids)]
    else:
        selected = eligible[:limit]
    if set(selected) & registered:
        raise ReleaseError('Canonical registration already exists; retry forbidden')
    by_id = {m['run_id']: m for m in verified['manifests']}
    return [by_id[identity] for identity in selected]


def _administration_attachments(records, context):
    recovery = context.recovery; index_ref = recovery['source_index_ref']
    index_path = original.reference(index_ref, HERE)
    index = recovery['source_index']; bundle_ref = index['bundle']
    bundle = original.reference(bundle_ref, index_path.parent)
    annex = original.reference(recovery['annex_ref'], HERE)
    directory = original._registration_path(records.MAP) / 'releases' / (context.manifest['release_id'] + '-admin001')
    original._registration_path(directory); directory.mkdir(parents=True, exist_ok=True)
    rows = [(bundle, 'administration.zip', bundle_ref['sha256'], 'Administrative executable source bundle'),
            (index_path, 'administration-index.json', index_ref['sha256'], 'Administrative source index'),
            (annex, 'execution-annex.json', recovery['annex_ref']['sha256'], 'Adopted execution recovery annex')]
    refs = []
    for source, name, digest, label in rows:
        target = directory / name
        original._retain_registration_file(source, target, digest)
        refs.append(original.map_reference(label, target, digest))
    return refs


def register_attempt(context):
    context._require_authority()
    import record_attempt as records
    m = context.manifest; root = context.release_dir; recovery = context.recovery
    release = original.load(root / 'release.json')
    freeze_path = original.reference(release['freeze_manifest'], root); freeze = original.load(freeze_path)
    artifacts = json.loads(context.artifacts_json)
    aid = 'B01-C0' if m['architecture'] == 'baseline' else 'B01-' + m['architecture']
    rid = context.revision_id; parent = recovery['parent_revision_ids'][m['architecture']]
    data, _, errors = records.am.read_store(records.MAP)
    if errors:
        raise ReleaseError(str(errors))
    if any(r['id'] == m['run_id'] for r in data['run']) or any(r['run_id'] == m['run_id'] for r in data['result']):
        raise ReleaseError('Attempt already registered; recovery cannot retry it')
    prior = next((r for r in data['revision'] if r['id'] == parent), None)
    if (not prior or prior['architecture_id'] != aid or prior.get('status') != 'frozen'
            or prior.get('details', {}).get('freeze_sha256') != m['freeze_sha256']):
        raise ReleaseError('Original frozen parent revision is unavailable or differs')
    code_path = original.reference(freeze['artifacts']['code'], freeze_path.parent); code = original.load(code_path)
    bundle = original.reference(code['bundle'], code_path.parent)
    if bundle != Path(artifacts['code_bundle']).resolve():
        raise ReleaseError('Original source bundle differs')
    attachments = original.retained_revision_attachments(records.MAP, m['release_id'], bundle,
        code['bundle']['sha256'], freeze_path, m['freeze_sha256']) + _administration_attachments(records, context)
    details = {'freeze_sha256': m['freeze_sha256'], 'release_id': m['release_id'],
               'model_identity': artifacts['model_identity'], **_refs(recovery),
               'authorization_version': AUTHORIZATION_VERSION}
    existing = next((r for r in data['revision'] if r['id'] == rid), None)
    if existing:
        if (existing.get('parent_revision_id') != parent or existing.get('status') != 'frozen'
                or existing.get('attachments') != attachments or existing.get('details') != details):
            raise ReleaseError('Existing administrative revision differs')
    else:
        records.append('revision', {**records.common(rid, ['batch-01', 'evaluation', 'administrative-recovery']),
            'architecture_id': aid, 'parent_revision_id': parent, 'status': 'frozen',
            'title': m['architecture'] + ' r4 administrative execution recovery 001',
            'summary': 'Original physical/policy/model configuration with separately adopted administrative authority.',
            'mechanism': 'Same original modules and manifests; additional gated runner/context and explicit interruption accounting.',
            'attachments': attachments, 'details': details})
    manifest_path = root / 'runs' / (m['run_id'] + '.json')
    refs = {role: original.map_reference('Original frozen ' + role + ' artifact index',
        artifacts['index_paths'][role], m['artifact_hashes'][role + '_sha256']) for role in ('code', 'environment', 'model')}
    records.append('run', {**records.common(m['run_id'], ['batch-01', 'evaluation', 'administrative-recovery', m['architecture']]),
        'revision_id': rid, 'stage': 'evaluation', 'condition_id': m['condition'], 'protocol_id': m['protocol_id'],
        'scenario_id': m['scenario_id'], 'paired_block_id': m['paired_block_id'], 'replicate': m['replicate'],
        'started_at': None, 'rerun_of_run_id': None,
        'condition_details': {'release_id': m['release_id'], 'scheduled_index': m['scheduled_index'],
            'part_count': m['parts'], 'cap_s': m['cap_s'], 'queue_job_id': context.queue_job_id,
            'revision_id': rid, **_refs(recovery)},
        'seeds': records.state(original.map_reference('Protected original seed manifest', manifest_path, context.manifest_sha256, 'seeds')),
        'frozen_refs': {'code': records.state(refs['code']), 'environment': records.state(refs['environment']),
            'models': records.none('Conventional baseline has no model') if m['architecture'] == 'baseline' else records.state(refs['model']),
            'protocol': records.state(original.map_reference('Original frozen protocol', FROZEN_RUNTIME / 'protocol.py', m['artifact_hashes']['protocol_sha256'])),
            'scenario': records.state(original.map_reference('Original exact scenario manifest', manifest_path, context.manifest_sha256))},
        'evidence': [original.map_reference('Pre-run original manifest', manifest_path, context.manifest_sha256),
                     *attachments[-3:]]})
    return rid


def run_batch(release_dir, annex_path, *, limit=4):
    job = queued_job(); verified = verify_recovery(annex_path, release_dir)
    selected = select_runs(verified, limit=limit); episode = require_supervisor_hook()
    root = verified['root']; checked = verified['recovery']; job_id = original.safe_id(job['id'])
    continuation = continuation_state(verified); refs = _refs(checked)
    batch = root / 'batches' / job_id; batch.mkdir(parents=True, exist_ok=False)
    original.write_once(batch / 'planned.json', {'schema_version': AUTHORIZATION_VERSION,
        'queue_job_id': job_id, 'created_at': original.utc(), 'release_sha256': verified['release_sha256'],
        'limit': limit, 'selected_run_ids': [m['run_id'] for m in selected], 'schedule_order_preserved': True,
        'official_queue_completion_verified': False, 'continuation': continuation, **refs})
    active_batch = {'queue_job_id': job_id, 'path': str(batch / 'planned.json'),
                    'sha256': original.digest(batch / 'planned.json')}
    completed = []; terminal_refs = []; stop_reason = None
    for manifest in selected:
        context, fresh = _authorize(manifest, root, annex_path)
        if context.queue_job_id != job_id or _refs(context.recovery) != refs:
            raise ReleaseError('Queue/administrative ownership changed')
        # The current exact planned journal is the only additional in-progress
        # exception. All other unfinished batches/attempts still block admission.
        if select_runs(fresh, [manifest['run_id']], limit, _active_batch=active_batch) != [manifest]:
            raise ReleaseError('Attempt is no longer the exact permitted untouched selection')
        if _refs(fresh['recovery']) != refs or continuation_state(fresh) != continuation:
            raise IntegrityError('Recovery authority/reviews changed before admission')
        attempt = root / 'attempts' / manifest['run_id']; attempt.mkdir(parents=True, exist_ok=False)
        original.write_once(attempt / 'claimed.json', {'run_id': manifest['run_id'], 'queue_job_id': job_id,
            'claimed_at': original.utc(), 'manifest_sha256': context.manifest_sha256,
            'release_sha256': context.release_sha256, **refs})
        phase = 'pre_registration'; revision = None
        try:
            revision = register_attempt(context)
            original.write_once(attempt / 'registered.json', {'run_id': manifest['run_id'],
                'revision_id': revision, 'registered_at': original.utc(), **refs})
            phase = 'episode_start'
            original.write_once(attempt / 'started.json', {'run_id': manifest['run_id'],
                'started_at': original.utc(), 'queue_job_id': job_id, **refs})
            phase = 'episode_execution'; result = original.execute_episode(context, episode)
            if (not isinstance(result, dict) or result.get('run_id') != manifest['run_id']
                    or result.get('stage') != 'evaluation' or result.get('execution_status') not in original.protocol.TERMINAL):
                raise IntegrityError('Recovery supervisor did not return the exact explicit terminal result')
            source = context.evidence_dir / 'result.json'
            if not source.is_file() or original.load(source) != result:
                raise IntegrityError('Recovery supervisor result lacks identical protected evidence')
        except BaseException as exc:
            result = original.failure_result(manifest['run_id'], exc, phase); source = None
        post = {'passed': False, 'verified_at': original.utc(),
                'original_artifacts': {'passed': False},
                'supplemental_administration': {'passed': False, **refs}}
        try:
            after = verify_recovery(annex_path, root)
            if after['release_sha256'] != context.release_sha256 or continuation_state(after) != continuation:
                raise IntegrityError('Original release or continuation changed during episode')
            if _refs(after['recovery']) != refs:
                raise IntegrityError('Supplemental administration changed during episode')
            post.update(passed=True, release_sha256=after['release_sha256'],
                artifact_hashes=manifest['artifact_hashes'], continuation_review_refs=continuation['review_refs'],
                original_artifacts={'passed': True, 'artifact_hashes': manifest['artifact_hashes'],
                                    'release_sha256': after['release_sha256']},
                supplemental_administration={'passed': True, **refs})
        except BaseException as exc:
            post['error'] = type(exc).__name__ + ': ' + str(exc)
        terminal = {'run_id': manifest['run_id'], 'queue_job_id': job_id, 'recorded_at': original.utc(),
            'revision_id': revision, 'manifest_sha256': context.manifest_sha256,
            'release_sha256': context.release_sha256, 'result': result,
            'supervisor_result_ref': None if source is None else {'path': str(source), 'sha256': original.digest(source)},
            'official_queue_completion_verified': False, 'post_run_integrity': post,
            'integrity_breach': not post['passed'] or original.integrity_breach({'result': result}),
            'continuation': continuation,
            'excluded_from_primary_by_prior_review': manifest['paired_block_id'] in continuation['excluded_paired_block_ids'], **refs}
        original.write_once(attempt / 'terminal.json', terminal); completed.append(manifest['run_id'])
        terminal_refs.append({'run_id': manifest['run_id'], 'path': str((attempt / 'terminal.json').relative_to(root)),
                              'sha256': original.digest(attempt / 'terminal.json')})
        if terminal['integrity_breach'] or result.get('infrastructure_invalid') is True or result.get('validity') != 'valid':
            stop_reason = 'Invalid attempt retained; stop for explicit review'; break
    original.write_once(batch / 'finished.json', {'queue_job_id': job_id, 'finished_at': original.utc(),
        'terminal_run_ids': completed, 'terminal_refs': terminal_refs,
        'unlaunched_selected_run_ids': [m['run_id'] for m in selected if m['run_id'] not in completed],
        'stop_reason': stop_reason, 'official_queue_completion_verified': False, **refs})
    return {'queue_job_id': job_id, 'terminal_attempts': len(completed), 'stop_reason': stop_reason,
            'map_results_applied': False, **refs}


def verify_queue_receipt(job_id, status_path):
    receipt = original.load(status_path)
    if receipt.get('id') != job_id or receipt.get('state') != 'succeeded' or type(receipt.get('exit_status')) is not int or receipt['exit_status'] != 0:
        raise ReleaseError('Authentic successful queue completion is required')
    rows = [j for j in read_shared_json(original.QUEUE_STATE).get('jobs', []) if j.get('id') == job_id]
    keys = ('id', 'state', 'exit_status', 'worker_pid', 'child_pid', 'started_at', 'ended_at', 'argv', 'cwd')
    if len(rows) != 1 or any(rows[0].get(k) != receipt.get(k) for k in keys):
        raise ReleaseError('Saved official receipt differs from installed queue record')
    return receipt


def _receipt_command(receipt, root, checked):
    argv = receipt.get('argv'); cwd = receipt.get('cwd')
    if original.python_entrypoint(argv, cwd) != SCRIPT:
        raise ReleaseError('Receipt is not for the actual recovery runner')
    index = 1
    while index < len(argv):
        value = argv[index]
        if value == '--':
            index += 1; break
        if value in ('-X', '-W'):
            index += 2; continue
        if value in ('-B', '-E', '-I', '-O', '-OO', '-P', '-q', '-s', '-S', '-u', '-v', '-x') or value.startswith(('-X', '-W')):
            index += 1; continue
        break
    try:
        args = parser().parse_args(argv[index + 1:])
    except SystemExit as exc:
        raise ReleaseError('Receipt command is not a declared recovery invocation') from exc
    def command_path(value):
        candidate = Path(value)
        return (candidate if candidate.is_absolute() else Path(cwd) / candidate).resolve()
    if (args.command != 'run' or command_path(args.release_dir) != root
            or command_path(args.annex) != Path(checked['annex_ref']['path']).resolve()):
        raise ReleaseError('Receipt command does not name this release/annex run')
    return args


def append_map_result(terminal, path, receipt_ref, checked):
    import record_attempt as records
    _require_refs(terminal, checked)
    result = terminal['result']; run_id = terminal['run_id']
    evidence = original.map_reference('Protected recovery terminal attempt', path)
    data, _, errors = records.am.read_store(records.MAP)
    if errors:
        raise ReleaseError(str(errors))
    run = next((r for r in data['run'] if r['id'] == run_id), None)
    if not run or not terminal.get('revision_id') or run['revision_id'] != terminal['revision_id']:
        raise ReleaseError('Recovery attempt lacks matching prior administrative registration')
    _require_refs(run.get('condition_details', {}), checked)
    existing = next((r for r in data['result'] if r['id'] == run_id + '-result'), None)
    if existing:
        details = existing.get('details', {})
        _require_refs(details, checked)
        if (details.get('terminal_sha256') != evidence['sha256'] or details.get('queue_job_id') != terminal['queue_job_id']
                or details.get('revision_id') != terminal['revision_id']):
            raise ReleaseError('Existing immutable recovery result differs')
        return False
    metrics = []
    for key, unit in (('completion_time_s', 's'), ('wall_duration_s', 's'), ('model_calls', 'count'),
                      ('total_tokens', 'count'), ('false_done_assertions', 'count')):
        value = result.get(key)
        metrics.append({'name': key, 'value': value, 'unit': unit, 'denominator': None,
            'denominator_description': 'One original frozen evaluation attempt',
            'missing_reason': 'Not measured or task did not complete; inspect protected evidence' if value is None else None,
            'evidence': [evidence] if value is not None else []})
    breached = original.integrity_breach(terminal)
    records.append('result', {**records.common(run_id + '-result', ['batch-01', 'evaluation', 'administrative-recovery']),
        'run_id': run_id, 'supersedes_result_id': None, 'execution_status': result['execution_status'],
        'validity': 'invalid' if breached else result.get('validity', 'unknown'),
        'validity_reason': 'Recovery integrity verification failed; measured result retained' if breached else result.get('validity_reason', 'Validity not established'),
        'outcome': result.get('outcome', 'unknown'), 'ended_at': result['ended_at'],
        'termination_reason': result['termination_reason'], 'metrics': metrics, 'evidence': [evidence, receipt_ref],
        'details': {'queue_job_id': terminal['queue_job_id'], 'official_queue_status': 'succeeded',
            'official_queue_exit_status': 0, 'revision_id': terminal['revision_id'],
            'terminal_sha256': evidence['sha256'], 'failed_attempt_retained': result.get('outcome') != 'success',
            'infrastructure_invalid': True if breached else result.get('infrastructure_invalid'),
            'limits': result.get('limits', []), 'post_run_integrity': terminal.get('post_run_integrity'),
            'continuation': terminal.get('continuation'),
            'excluded_from_primary_by_prior_review': terminal.get('excluded_from_primary_by_prior_review', False), **_refs(checked)}})
    return True


def finalize(release_dir, annex_path, verified_queue_job_id, status_path):
    """Metadata-only normal finalization; never handles the historical interruption."""
    checked = _contract(annex_path, release_dir); root = Path(checked['root']).resolve()
    job_id = original.safe_id(verified_queue_job_id)
    if job_id in checked['administrative_batch_ids']:
        raise ReleaseError('Historical interrupted batch cannot use normal finalization')
    receipt = verify_queue_receipt(job_id, status_path); args = _receipt_command(receipt, root, checked)
    batch = root / 'batches' / job_id
    planned = original.load(batch / 'planned.json'); finished = original.load(batch / 'finished.json')
    for row in (planned, finished):
        _require_refs(row, checked)
        if row.get('queue_job_id') != job_id:
            raise ReleaseError('Recovery batch queue identity differs')
    if planned.get('schema_version') != AUTHORIZATION_VERSION or original.digest(root / 'release.json') != planned.get('release_sha256'):
        raise ReleaseError('Recovery batch release/version differs')
    selected = planned.get('selected_run_ids'); allowed = checked['allowed_run_ids']
    if (not isinstance(selected, list) or len(selected) != len(set(selected)) or not set(selected) <= set(allowed)
            or selected != [identity for identity in allowed if identity in set(selected)]
            or args.limit != planned.get('limit') or len(selected) > args.limit):
        raise ReleaseError('Planned recovery selection differs from allowed schedule/command')
    done = finished.get('terminal_run_ids'); pending = finished.get('unlaunched_selected_run_ids')
    if (not isinstance(done, list) or not isinstance(pending, list)
            or len(done) != len(set(done)) or len(pending) != len(set(pending))
            or done + pending != selected):
        raise ReleaseError('Finished recovery batch lacks exact ordered terminal/unlaunched partition')
    terminal_refs = finished.get('terminal_refs')
    if not isinstance(terminal_refs, list) or [r.get('run_id') for r in terminal_refs] != done:
        raise ReleaseError('Recovery terminal references differ from ordered results')
    terminals = []
    manifests = {r['run_id']: r for r in original.load(root / 'release.json')['manifest_refs']}
    for run_id, ref in zip(done, terminal_refs):
        path = root / 'attempts' / original.safe_id(run_id) / 'terminal.json'
        if original.reference(ref, root) != path:
            raise ReleaseError('Recovery terminal reference escapes its attempt')
        terminal = original.load(path); _require_refs(terminal, checked)
        if (terminal.get('run_id') != run_id or terminal.get('queue_job_id') != job_id
                or terminal.get('release_sha256') != planned['release_sha256']
                or terminal.get('manifest_sha256') != manifests[run_id]['sha256']):
            raise ReleaseError('Recovery terminal identity differs from original manifest/batch')
        registered = original.load(path.parent / 'registered.json'); _require_refs(registered, checked)
        manifest = original.load(original.reference(manifests[run_id], root))
        expected_revision = checked['annex']['revision_ids'][manifest['architecture']]
        if (registered.get('run_id') != run_id or registered.get('revision_id') != terminal.get('revision_id')
                or terminal.get('revision_id') != expected_revision):
            raise ReleaseError('Recovery terminal revision differs from prior registration')
        source = terminal.get('supervisor_result_ref')
        if source and original.load(original.reference(source, path.parent)) != terminal['result']:
            raise ReleaseError('Protected recovery result changed before finalization')
        terminals.append((path, terminal))
    receipt_copy = batch / 'official-queue-status.json'
    if receipt_copy.exists():
        if original.load(receipt_copy) != receipt:
            raise ReleaseError('Retained official recovery receipt differs')
    else:
        original.write_once(receipt_copy, receipt)
    receipt_ref = original.map_reference('Verified official recovery run completion', receipt_copy)
    marker = batch / 'finalized.json'
    value = {'queue_job_id': job_id, 'run_ids': done,
             'official_queue_receipt_sha256': original.digest(receipt_copy), **_refs(checked)}
    if marker.exists():
        existing = original.load(marker)
        if any(existing.get(key) != item for key, item in value.items()):
            raise ReleaseError('Retained recovery finalization marker differs')
    applied = []
    for path, terminal in terminals:
        append_map_result(terminal, path, receipt_ref, checked); applied.append(terminal['run_id'])
    import record_attempt as records
    if records.am.main(['build']) != 0 or records.am.main(['validate', '--output', 'validation.json']) != 0:
        raise ReleaseError('Map validation failed; exact partial appends retained without completion marker')
    if marker.exists():
        existing = original.load(marker)
        if any(existing.get(key) != item for key, item in value.items()):
            raise ReleaseError('Retained recovery finalization marker differs')
    else:
        original.write_once(marker, {**value, 'finalized_at': original.utc()})
    return {'queue_job_id': job_id, 'map_result_run_ids': applied, 'official_queue_completion_verified': True, **_refs(checked)}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run'); run.add_argument('--release-dir', required=True); run.add_argument('--annex', required=True)
    run.add_argument('--limit', type=int, default=4)
    finish = commands.add_parser('finalize'); finish.add_argument('--release-dir', required=True); finish.add_argument('--annex', required=True)
    finish.add_argument('--verified-queue-job-id', required=True); finish.add_argument('--queue-status', required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'run':
            value = run_batch(args.release_dir, args.annex, limit=args.limit)
        else:
            value = finalize(args.release_dir, args.annex, args.verified_queue_job_id, args.queue_status)
    except (ReleaseError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser().exit(2, 'Refused: ' + str(exc) + '\n')
    print(json.dumps(value, indent=2, allow_nan=False)); return 0


if __name__ == '__main__':
    # Normal import supplies one canonical class/token without changing argv or
    # inserting aliases into sys.modules. The original module is never patched.
    import recovery_runner
    if Path(recovery_runner.__file__).resolve() != SCRIPT:
        raise RuntimeError('Recovery CLI imported another runner')
    raise SystemExit(recovery_runner.main())
