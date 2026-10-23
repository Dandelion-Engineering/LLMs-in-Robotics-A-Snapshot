"""Continue unchanged repaired-source qualification after a packaging-only failure.

Native004 remains its original passed dev016 run. Boundary004 remains invalid;
its sole missing README inventory entry is authenticated, never forgiven. Four
new stages use new identities, including a complete boundary source inventory.
All execution and result gates delegate to unchanged v4 helpers. This module
does not change v4 globals, rewrite records, seal a release or launch scoring.
"""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('campaign002_qualification_v4_for_v5', HERE / 'run_final_qualification_v4.py')
v4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)
admission = v4.admission
require, read, sha, identity = v4.require, v4.read, v4.sha, v4.identity
LEDGER = HERE / 'final-qualification-005'
SCHEMA = 'campaign002-final-qualification-continuation-1'
NATIVE_JOB = '20260928T015123956289Z-85d3701b'
BOUNDARY_JOB = '20260928T015949502082Z-5c498d22'
MISSING_README = (v4.CAMPAIGN / 'assessment/README.md').relative_to(v4.REPO).as_posix()
BOUNDARY_ERROR = 'Boundary source receipt differs from snapshot'
STAGES = (('boundary-005', 'boundary', 'RCI001-C02-dev-018', None),
          ('smoke-003', 'smoke', 'RCI001-C02-dev-019', 24101),
          ('pilot-stock-002', 'stock', 'RCI001-C02-dev-019', 24102),
          ('pilot-home-002', 'home', 'RCI001-C02-dev-019', 24103))


def load_readiness(path, digest):
    require(isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
            'Continuation readiness requires a caller-held SHA256')
    path = admission.artifact({'path': str(Path(path).resolve()), 'sha256': digest})
    value = read(path)
    require(value.get('schema') == SCHEMA and admission.same_path(value.get('ledger_directory', ''), LEDGER),
            'Wrong immutable continuation readiness or ledger')
    require(value.get('stages') == [list(stage) for stage in STAGES]
            and all(type(row[3]) is int for row in value['stages'][1:]),
            'Continuation must contain exactly the four fixed fresh stages')
    require(value.get('native', {}).get('job_id') == NATIVE_JOB
            and value.get('boundary_failure', {}).get('job_id') == BOUNDARY_JOB,
            'Continuation names different prior qualification jobs')
    require(admission.same_path(value.get('prior_coordinator', {}).get('path', ''), v4.__file__)
            and admission.same_path(value.get('prior_readiness', {}).get('path', ''),
                                    HERE / 'final-qualification-004-readiness.json'),
            'Continuation must bind the unchanged v4 coordinator and original readiness')
    return value


def retained_disposition(section, name, revision, passed, official_job):
    run_id = 'RCI001-C02-' + name
    path = admission.artifact(section['disposition'])
    require(path == HERE / 'final-qualification-004' / name / 'disposition.json',
            'Prior disposition is outside its original v4 ledger')
    disposition = read(path)
    require(disposition.get('run_id') == run_id and disposition.get('passed') is passed
            and disposition.get('error') == (None if passed else BOUNDARY_ERROR),
            'Prior disposition was changed or reclassified')
    entry = disposition['entry']
    require(read(admission.artifact(entry['queue'])) == official_job,
            'Prior disposition queue differs from fresh official authentication')
    if passed:
        require(section.get('entry') == entry, 'Carried native entry differs from its original passed disposition')
    record_path = admission.artifact(disposition['registered_result'])
    require(record_path == v4.MAP / 'releases' / revision / ('result-' + run_id) / 'result-record.json',
            'Prior registered result path differs')
    record = read(record_path)
    require(record.get('id') == run_id + '-result' and record.get('run_id') == run_id
            and record.get('execution_status') == 'completed'
            and record.get('validity') == ('valid' if passed else 'invalid')
            and record.get('outcome') == ('success' if passed else 'unknown')
            and record.get('details', {}).get('queue_success_verified') is True,
            'Prior registered result lost its original validity or execution identity')
    result = read(admission.artifact(entry['assessment']))
    require(record['details'].get('source_result') == result, 'Registered source result differs from retained assessment')
    return entry


def verify_packaging_failure(entry, core):
    value, manifest, frozen, job = admission.qualifier_entry(entry, 'boundary', core, time.time())
    require(manifest.get('run_id') == 'RCI001-C02-boundary-004'
            and frozen.get('revision') == 'RCI001-C02-dev-017' and job.get('id') == BOUNDARY_JOB,
            'Packaging diagnosis identifies another boundary attempt')
    root = Path(entry['evidence'])
    before = read(root / 'source-binding-before.json')
    after = read(root / 'source-binding-after.json')
    require(isinstance(before, dict) and bool(before) and before == after,
            'Boundary failure also changed source bytes during execution')
    missing = {name for name in before if name not in frozen['sources']}
    changed = {name for name, digest in before.items() if name in frozen['sources']
               and frozen['sources'][name].get('sha256') != digest}
    require(missing == {MISSING_README} and not changed,
            'Boundary failure is not the exact sole README inventory omission')
    require(all((v4.REPO / name).is_file() and sha(v4.REPO / name) == digest for name, digest in before.items()),
            'Boundary measured source bytes changed after the original attempt')
    require(value.get('qualified') is True and value.get('model_calls') == 0
            and value.get('physical_simulation') is False and not value.get('error'),
            'Original boundary suite had an additional execution failure')
    admission.all_checks(value.get('checks'), admission.BOUNDARY_CHECKS, 'Original boundary')
    admission.verify_boundary_suites(value.get('unit_suites', []))
    # Verify that the existing independent gate still rejects this unchanged
    # record. It is retained as failed evidence, never an admitted qualifier.
    try:
        admission.verify_boundary(entry, core, time.time())
    except ValueError as error:
        require(str(error) == BOUNDARY_ERROR, 'Original boundary now fails a different admission gate')
    else:
        raise ValueError('Original invalid boundary was unexpectedly admitted')
    return {'missing_source': MISSING_README, 'missing_source_sha256': before[MISSING_README],
            'source_receipt_entries': len(before), 'changed_hashes': 0,
            'disposition_preserved': 'invalid/unknown',
            'before': identity(root / 'source-binding-before.json'),
            'after': identity(root / 'source-binding-after.json')}


def preflight(path, digest):
    value = load_readiness(path, digest)
    # No prior result/disposition/source-result hash is opened until both fresh
    # official jobs authenticate. Prior v4 then authenticates its own host probe.
    native_job = admission.base.queue_gate(v4.official(NATIVE_JOB), NATIVE_JOB)
    boundary_job = admission.base.queue_gate(v4.official(BOUNDARY_JOB), BOUNDARY_JOB)
    admission.artifact(value['prior_coordinator'])
    prior_path = admission.artifact(value['prior_readiness'])
    prior, core = v4.preflight(prior_path, value['prior_readiness']['sha256'])
    native = retained_disposition(value['native'], 'native-004', 'RCI001-C02-dev-016', True, native_job)
    v4.assert_sources(prior, Path(native['snapshot']['path']))
    artifacts = {name: identity(v4.CAMPAIGN / 'assessment' / filename) for name, filename in
                 (('base_assessor', 'assess.py'), ('smoke_assessor', 'assess_smoke_v2.py'))}
    admission.verify_native(native, core, time.time(), artifacts)
    boundary = retained_disposition(value['boundary_failure'], 'boundary-004', 'RCI001-C02-dev-017', False, boundary_job)
    diagnosis = verify_packaging_failure(boundary, core)
    return value, prior, core, native, diagnosis


def prepare_boundary(folder, paths, prior):
    name, kind, revision, seed = STAGES[0]
    manifest, snapshot = paths['manifest'], paths['snapshot']
    preparer = HERE / 'prepare_boundary_v2.py'
    v4.command_once(folder, 'prepare', v4.python(preparer, '--run-id', paths['run_id'],
        '--revision', revision, '--output', manifest), outputs=[manifest])
    value = read(manifest)
    require(value.get('run_id') == paths['run_id'] and value.get('framework_revision') == revision,
            'Fresh packaging-fixed boundary manifest identity differs')
    v4.command_once(folder, 'register', v4.python(v4.CAMPAIGN / 'registry.py', 'freeze',
        '--manifest', manifest, '--revision', revision), inputs=[manifest],
        outputs=[snapshot, snapshot.with_name('code.zip'), snapshot.with_name('run-record.json')],
        absent=[snapshot.parent])
    v4.assert_sources(prior, snapshot)
    # The corrected preparer must cover the complete current boundary receipt
    # before anything is submitted, including files beyond executable modules.
    spec = importlib.util.spec_from_file_location('campaign002_boundary_sources_v5', HERE / 'boundary_suite.py')
    suite = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite)
    actual, frozen = suite.sources(), read(snapshot)['sources']
    require(all(name in frozen and frozen[name]['sha256'] == digest for name, digest in actual.items()),
            'Packaging-fixed boundary freeze still omits a measured source')
    return value


@contextmanager
def coordinator_lock():
    LEDGER.mkdir(parents=True, exist_ok=True)
    with (LEDGER / '.lock').open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run(path, digest):
    with coordinator_lock():
        value, prior, core, native, diagnosis = preflight(path, digest)
        v4.save_exact(LEDGER / 'preflight.json', {'schema': 'campaign002-final-qualification-continuation-preflight-1',
            'readiness': identity(path), 'coordinator': identity(__file__), 'prior_coordinator': value['prior_coordinator'],
            'prior_readiness': value['prior_readiness'], 'source_snapshot': prior['source_snapshot'],
            'retained_native': value['native'], 'preserved_boundary_failure': value['boundary_failure'],
            'packaging_diagnosis': diagnosis, 'stages': value['stages'],
            'orchestration_sources': [identity(item) for item in (HERE / 'prepare_boundary_v2.py',
                HERE / 'prepare_model.py', HERE / 'launch.py', HERE / 'boundary_suite.py',
                v4.CAMPAIGN / 'registry.py', v4.CAMPAIGN / 'admission.py', v4.CAMPAIGN / 'operate.py',
                v4.QUEUE, v4.operate.GUARD, v4.CAMPAIGN / 'admission/storage-policy.json',
                v4.CAMPAIGN / 'admission/storage-baseline-001.json')]})
        entries = [native]
        for name, kind, revision, seed in STAGES:
            require(sha(path) == digest, 'Continuation readiness changed during execution')
            admission.artifact(value['prior_coordinator'])
            admission.artifact(value['prior_readiness'])
            v4.assert_sources(prior)
            folder, paths = LEDGER / name, v4.entry_for(name, kind, revision)
            manifest = (prepare_boundary(folder, paths, prior) if kind == 'boundary' else
                        v4.prepare_stage(folder, name, kind, revision, seed, paths, prior))
            job = v4.launch_stage(folder, kind, paths, manifest)
            if kind != 'boundary':
                v4.storage_gate(folder, paths, manifest, job)
            v4.assess_stage(folder, kind, revision, paths, manifest, job)
            entries.append(v4.finish_stage(folder, kind, revision, paths, core))
        v4.save_exact(LEDGER / 'completed.json', {'schema': 'campaign002-final-qualification-completed-1',
            'native': entries[0], 'boundary': entries[1], 'smoke': entries[2], 'pilots': entries[3:],
            'scope': 'Original exact-source native004 and four fresh qualified jobs. Boundary004 remains invalid. '
                     'Requires separate final index, certificate and release admission.'})
        v4.notice('all_qualification_stages_completed', evidence=str(LEDGER / 'completed.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--readiness', type=Path, required=True)
    parser.add_argument('--readiness-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        run(args.readiness.resolve(), args.readiness_sha256)
    except Exception as error:
        v4.notice('stopped', error=str(error), reconciliation='No automatic retry or replacement is permitted.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
