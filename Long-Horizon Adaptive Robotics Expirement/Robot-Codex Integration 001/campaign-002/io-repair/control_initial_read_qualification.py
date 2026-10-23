"""One-shot operator actions for the declared V24 prerequisite lineage.

This is outside the runtime source inventory. It does not poll or retry jobs,
change gates, or launch the final coordinator or any scored attempt.
"""
import argparse
import importlib.util
import json
from pathlib import Path

IO = Path(__file__).resolve().parent
C = IO.parent
Q = C / 'qualification'
spec = importlib.util.spec_from_file_location('native_cleanup_coordinator', Q / 'run_final_qualification_v24.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
REV = 'RCI001-C02-dev-071'
SNAP = c.MAP / 'releases' / REV / 'snapshot.json'
HOST = 'RCI001-C02-host-probe-024'
HOST_MANIFEST = Q / 'host-probe-024-manifest.json'
HOST_RECORDS = Q / HOST
CHECKS = IO / 'checks-026'
DECLARATION = IO / 'v24-qualification-declaration.json'


def bound_declaration():
    value = c.read(DECLARATION)
    c.require(value['anchor_revision'] == REV and value['repair_checks'] == CHECKS.name,
              'Prospective identities changed')
    c.require(value['coordinator'] == c.identity(Q / 'run_final_qualification_v24.py'),
              'Declared coordinator changed')
    for name in ('transport_correction_method', 'prior_failed_diagnostic',
                 'unchanged_scheduling_method', 'unchanged_quiescence_method', 'unchanged_normal_closed_method',
                 'initial_read_evidence_method', 'initial_read_diagnostic', 'chronology_diagnostic'):
        c.admission.artifact(value[name])
    return value


def prepare():
    bound_declaration()
    c.require(c.read(CHECKS / 'test-execution.json')['passed'] is True, 'Full repair tests did not pass')
    c.command_once(HOST_RECORDS, 'prepare', c.python(Q / 'host_probe.py', 'prepare',
        '--manifest', HOST_MANIFEST, '--run-id', HOST, '--revision', REV,
        '--sim-cap-s', 240, '--purpose', 'continuous-physics-during-durable-io'),
        inputs=[DECLARATION, CHECKS / 'test-execution.json'], outputs=[HOST_MANIFEST])
    c.command_once(HOST_RECORDS, 'freeze', c.python(C / 'registry.py', 'freeze',
        '--manifest', HOST_MANIFEST, '--revision', REV),
        inputs=[HOST_MANIFEST, CHECKS / 'test-execution.json'],
        outputs=[SNAP, SNAP.with_name('code.zip'), SNAP.with_name('run-record.json')],
        absent=[SNAP.parent])
    c.command_once(HOST_RECORDS, 'bind-checks', c.python(IO / 'record_checks.py', 'bind',
        '--directory', CHECKS, '--snapshot', SNAP),
        inputs=[SNAP, CHECKS / 'test-execution.json'], outputs=[CHECKS / 'repair-test-receipt.json'])
    print(json.dumps({'snapshot': c.identity(SNAP), 'tests': c.identity(CHECKS / 'repair-test-receipt.json')}))


def submit(records, command, inputs, absent):
    receipt = c.command_once(records, 'submit', c.python(c.QUEUE, 'submit',
        '--project', 'LLMs-in-Robotics', '--cwd', c.REPO, '--', *command),
        inputs=inputs, absent=absent)
    submitted = json.loads(receipt['stdout'])
    submitted = submitted.get('job', submitted)
    c.require(isinstance(submitted.get('id'), str), 'Missing official queue submission identity')
    c.save_exact(records / 'queue-submit.json', submitted)
    print(json.dumps({'job_id': submitted['id'], 'records': str(records)}), flush=True)


def probe_paths(kind):
    name = {'raw': 'raw-preflight-014', 'transport': 'transport-probe-017'}[kind]
    root = IO / name
    script = C / 'harness' / {'raw': 'raw_event_preflight_v2.py', 'transport': 'codehost_transport_probe_v3.py'}[kind]
    return name, root, script


def launch_probe(kind):
    bound_declaration()
    name, root, script = probe_paths(kind)
    if kind == 'transport':
        c.verify_raw_preflight(c.read(IO / 'raw-preflight-014/records/verified-readiness-entry.json'), SNAP)
    old_name = {'raw': 'raw-preflight-013', 'transport': 'transport-probe-016'}[kind]
    manifest = c.read(IO / old_name / 'manifest.json')
    manifest.update(run_id='RCI001-C02-' + name, framework_revision=REV, source_snapshot=c.identity(SNAP))
    manifest['scope'] += ' Fresh lineage adds READ_EVIDENCE_V3 authenticated initial-read composition and completion intervals while preserving native cleanup, owner, byte, EOF, duration, task and isolation gates.'
    target = root / 'manifest.json'
    c.save(target, manifest)
    records = root / 'records'
    c.command_once(records, 'register', c.python(C / 'registry.py', 'add-run',
        '--manifest', target, '--revision', REV), inputs=[target, SNAP])
    submit(records, c.python(script, '--run-id', manifest['run_id'], '--framework-revision', REV,
        '--snapshot', SNAP, '--output', root / 'evidence'), [target, SNAP], [root / 'evidence'])


def settle_probe(kind):
    name, root, _ = probe_paths(kind)
    records = root / 'records'
    job_id = c.read(records / 'queue-submit.json')['id']
    # Official success authentication must precede every outcome hash or read.
    job = c.admission.base.queue_gate(c.official(job_id), job_id)
    c.save(records / 'official-status.json', job)
    result = root / 'evidence/result.json'
    entry = {'run_id': 'RCI001-C02-' + name, 'job_id': job_id,
             'queue': c.identity(records / 'official-status.json'), 'result': c.identity(result)}
    verifier = c.verify_raw_preflight if kind == 'raw' else c.verify_transport_probe
    verifier(entry, SNAP)
    c.save(records / 'verified-readiness-entry.json', entry)
    c.command_once(records, 'finish', c.python(C / 'registry.py', 'finish',
        '--run-id', entry['run_id'], '--result', result, '--queue-receipt', records / 'official-status.json',
        '--validity', 'valid', '--outcome', 'unknown', '--reason',
        'Fresh source-bound no-model prerequisite independently replayed; no task-performance claim.'),
        inputs=[result, records / 'official-status.json', records / 'verified-readiness-entry.json'])
    print(json.dumps({'verified': entry}))


def launch_host():
    bound_declaration()
    raw = IO / 'raw-preflight-014/records/verified-readiness-entry.json'
    c.verify_raw_preflight(c.read(raw), SNAP)
    manifest = c.read(HOST_MANIFEST)
    submit(HOST_RECORDS, c.python(Q / 'host_probe.py', 'run', '--manifest', HOST_MANIFEST,
        '--output', c.RAW / HOST), [HOST_MANIFEST, SNAP, raw],
        [c.RAW / HOST, Path(manifest['runtime_workspace'])])


def settle_host():
    submitted = c.read(HOST_RECORDS / 'queue-submit.json')
    c.admission.base.queue_gate(c.official(submitted['id']), submitted['id'])
    c.command_once(HOST_RECORDS, 'settle', c.python(IO / 'settle_probe.py',
        '--number', '024', '--revision', REV),
        inputs=[HOST_MANIFEST, SNAP, HOST_RECORDS / 'queue-submit.json'],
        outputs=[Q / 'host-probe-024-assessment.json', HOST_RECORDS / 'official-status.json'])


def readiness():
    declaration = bound_declaration()
    submitted = c.read(HOST_RECORDS / 'queue-submit.json')
    c.admission.base.queue_gate(c.official(submitted['id']), submitted['id'])
    value = {'schema': c.READINESS_SCHEMA, 'ledger_directory': str(c.LEDGER),
        'source_snapshot': c.identity(SNAP),
        'diagnostic': {'run_id': HOST, 'job_id': submitted['id'],
            'manifest': c.identity(HOST_MANIFEST), 'queue': c.identity(HOST_RECORDS / 'official-status.json'),
            'assessment': c.identity(Q / 'host-probe-024-assessment.json'),
            'assessor': c.identity(Q / 'assess_host_probe.py'), 'evidence': str(c.RAW / HOST)},
        'repair_test_receipt': c.identity(CHECKS / 'repair-test-receipt.json'),
        'raw_event_preflight': c.read(IO / 'raw-preflight-014/records/verified-readiness-entry.json'),
        'transport_diagnostic': c.read(IO / 'transport-probe-017/records/verified-readiness-entry.json'),
        'stages': declaration['stages']}
    target = Q / 'final-qualification-024-readiness.json'
    c.save(target, value)
    _, core = c.preflight(target, c.sha(target))
    receipt = {'readiness': c.identity(target), 'coordinator': c.identity(Q / 'run_final_qualification_v24.py'),
        'passed': True, 'core_sources': len(core),
        'scope': 'Fresh official success, independent prerequisite replay, test binding and source admission; no final qualifier launched by this check.'}
    c.save(IO / 'v24-readiness-preflight-001.json', receipt)
    print(json.dumps(receipt))


def main():
    actions = {'prepare': prepare, 'raw-submit': lambda: launch_probe('raw'),
        'raw-settle': lambda: settle_probe('raw'), 'transport-submit': lambda: launch_probe('transport'),
        'transport-settle': lambda: settle_probe('transport'), 'host-submit': launch_host,
        'host-settle': settle_host, 'readiness': readiness}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=actions)
    actions[parser.parse_args().action]()


if __name__ == '__main__':
    main()
