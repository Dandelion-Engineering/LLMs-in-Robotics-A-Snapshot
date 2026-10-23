"""One-shot downstream admission actions after all five V26 qualifiers pass.

Outside the frozen runtime inventory. Every invocation requires the caller-held
readiness SHA256. There is no launch action, automatic next action or retry of an
unresolved intent. Compile/static inspection does not execute an action.
"""
import argparse
import importlib.util
import json
from pathlib import Path

IO = Path(__file__).resolve().parent
C = IO.parent
Q = C / 'qualification'
spec = importlib.util.spec_from_file_location('campaign_admission_v26_coordinator',
                                            Q / 'run_final_qualification_v26.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
spec = importlib.util.spec_from_file_location('campaign_admission_v26_certificate',
                                            C / 'admission/prepare_certificate.py')
certificate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(certificate)

READINESS = Q / 'final-qualification-026-readiness.json'
PREFLIGHT = c.LEDGER / 'preflight.json'
COMPLETED = c.LEDGER / 'completed.json'
FINAL_REVISION = 'RCI001-C02-dev-082'
SNAPSHOT = c.MAP / 'releases' / FINAL_REVISION / 'snapshot.json'
INDEX = C / 'admission/qualification-index.json'
PREDECLARED = C / 'predeclared-v1'
SCHEDULE = PREDECLARED / 'schedule.json'
PLAN = C / 'execution-plan.json'
CANDIDATE = C / 'admission/candidate-v1.json'
SEALED = C / 'admission/sealed-v1'
SEAL = SEALED / 'seal.json'
CERTIFICATE = SEALED / 'certificate.json'
RELEASE = c.MAP / 'releases/RCI001-C02-frozen-001'
RECORDS = IO / 'campaign-admission-v26/records'
ACTIONS = ('prepare-index', 'prepare-scored', 'seal', 'register-release')


def admission_basis(expected_sha256):
    """All fresh official gates precede completed/disposition/assessment reads."""
    readiness = c.load_readiness(READINESS, expected_sha256)
    preflight = c.read(PREFLIGHT)
    c.require(preflight.get('schema') == 'campaign002-final-qualification-preflight-1'
              and preflight.get('coordinator') == c.identity(Q / 'run_final_qualification_v26.py')
              and preflight.get('readiness') == c.identity(READINESS)
              and preflight.get('readiness_sha256') == expected_sha256,
              'V26 preflight does not bind current coordinator and exact readiness')
    for field in ('source_snapshot', 'stages', 'diagnostic', 'repair_test_receipt',
                  'transport_diagnostic', 'raw_event_preflight'):
        c.require(preflight.get(field) == readiness.get(field) and field in readiness,
                  'V26 preflight differs from readiness: ' + field)
    jobs, paths = [], []
    for name, kind, revision, seed in readiness['stages']:
        expected = c.entry_for(name, kind, revision)
        retained = c.admission.base.queue_gate(c.read(expected['queue']))
        job = c.admission.base.queue_gate(c.official(retained['id']), retained['id'])
        c.require(job == retained, 'Official qualification receipt changed: ' + name)
        jobs.append(job); paths.append(expected)
    c.require(len({job['id'] for job in jobs}) == 5, 'Five distinct official jobs required')
    # This existing read-only prerequisite gate also authenticates official jobs
    # before replaying their retained results; it creates no records or jobs.
    validated_readiness, _ = c.preflight(READINESS, expected_sha256)
    c.require(validated_readiness == readiness, 'Readiness changed during prerequisite validation')
    completed = c.read(COMPLETED)
    c.require(completed.get('schema') == 'campaign002-final-qualification-completed-1'
              and isinstance(completed.get('pilots'), list) and len(completed['pilots']) == 2,
              'Complete ordered five-stage V26 ledger required')
    entries = [completed.get(name) for name in ('native', 'boundary', 'smoke')] + completed['pilots']
    bindings = [Path(__file__), Q / 'run_final_qualification_v26.py', READINESS,
                PREFLIGHT, COMPLETED, SNAPSHOT, SNAPSHOT.with_name('code.zip')]
    for stage, entry, expected in zip(readiness['stages'], entries, paths):
        name, kind, revision, seed = stage
        c.require(isinstance(entry, dict), 'Malformed completed entry: ' + name)
        for key in ('manifest', 'snapshot', 'queue', 'assessment'):
            c.require(entry.get(key) == c.identity(expected[key]),
                      'Completed entry differs from exact V26 path/bytes: ' + name + '/' + key)
            bindings.append(expected[key])
        c.require(entry.get('evidence') == str(expected['evidence'].resolve()),
                  'Completed evidence path differs: ' + name)
        manifest = c.read(expected['manifest'])
        c.require(manifest.get('run_id') == expected['run_id']
                  and manifest.get('framework_revision') == revision,
                  'Completed manifest identity differs: ' + name)
        if kind == 'native':
            assessor = Q / 'assess_native.py'
            c.require(entry.get('assessor') == c.identity(assessor), 'Native assessor differs')
            bindings.append(assessor)
        elif kind != 'boundary':
            c.require(entry.get('snapshot') == c.identity(SNAPSHOT)
                      and type(manifest.get('noise_seed')) is int and manifest['noise_seed'] == seed
                      and entry.get('host_evidence') == str(expected['host'].resolve()),
                      'Completed model source/seed/host differs: ' + name)
            if kind in ('stock', 'home'):
                c.require(entry.get('family') == {'stock': 'misplaced-stock',
                          'home': 'blocked-insert-home'}[kind], 'Ordered pilot family differs')
        disposition_path = c.LEDGER / name / 'disposition.json'
        disposition = c.read(disposition_path)
        c.require(disposition.get('run_id') == expected['run_id']
                  and disposition.get('passed') is True and disposition.get('error') is None
                  and disposition.get('entry') == entry,
                  'Original V26 admission is absent or unqualified: ' + name)
        registered = c.admission.artifact(disposition['registered_result'])
        c.require(registered == c.MAP / 'releases' / revision /
                  ('result-' + expected['run_id']) / 'result-record.json',
                  'Qualifier registration path differs: ' + name)
        bindings.extend((disposition_path, registered))
    frozen = c.read(SNAPSHOT)
    c.require(frozen.get('revision') == FINAL_REVISION, 'Wrong final V26 source revision')
    c.assert_sources(readiness, SNAPSHOT)
    c.require(c.sha(READINESS) == expected_sha256, 'Readiness changed during admission gate')
    return {'completed': completed, 'entries': entries, 'jobs': jobs,
            'bindings': list(dict.fromkeys(map(Path, bindings)))}


def stage_arguments(entry, model=False):
    # Preserve the exact index-input ordering defined by prepare_index.py.
    args = [entry[key]['path'] for key in ('manifest', 'snapshot', 'queue', 'assessment')]
    args.append(entry['evidence'])
    if model:
        args.append(entry['host_evidence'])
    return args


def scored_manifests():
    return [PREDECLARED / (f'RCI001-C02-{family}-{pair:02d}.json')
            for pair in range(1, 11) for family in ('stock', 'home')]


def command_spec(action, basis):
    inputs = [*basis['bindings'], RECORDS / (action + '-official-status.json')]
    entries = basis['entries']
    if action == 'prepare-index':
        argv = c.python(C / 'admission/prepare_index.py', '--snapshot', SNAPSHOT, '--output', INDEX,
                        '--native', *stage_arguments(entries[0]),
                        '--boundary', *stage_arguments(entries[1]),
                        '--smoke', *stage_arguments(entries[2], True),
                        '--pilot-stock', *stage_arguments(entries[3], True),
                        '--pilot-home', *stage_arguments(entries[4], True))
        return argv, inputs, [INDEX], [INDEX]
    if action == 'prepare-scored':
        return (c.python(C / 'prepare_scored.py', '--snapshot', SNAPSHOT, '--output', PREDECLARED),
                [*inputs, INDEX, C / 'PLAN.md'], [*scored_manifests(), SCHEDULE, PLAN],
                [PREDECLARED, PLAN])
    if action == 'seal':
        artifacts = certificate.artifact_paths(SNAPSHOT, INDEX, SCHEDULE)
        # Existing approval bytes are mandatory here; this operator never creates
        # a new approval copy from a mutable chat while publishing the seal.
        c.require((C / 'admission/approval-source.md').is_file(), 'Bound approval source absent')
        return (c.python(C / 'admission/prepare_certificate.py', '--snapshot', SNAPSHOT,
                         '--qualification-index', INDEX, '--candidate', CANDIDATE,
                         '--schedule', SCHEDULE, '--execution-plan', PLAN),
                list(dict.fromkeys([*inputs, *artifacts.values(), PLAN, *scored_manifests()])),
                [CANDIDATE, CERTIFICATE, SEAL], [CANDIDATE, SEALED, SEALED.with_name('sealed-v1.pending')])
    seal = c.read(SEAL)
    digest = seal.get('certificate_sha256')
    c.require(isinstance(digest, str) and c.sha(CERTIFICATE) == digest
              and seal.get('source_revision') == FINAL_REVISION
              and seal.get('release_revision') == RELEASE.name, 'Exact V26 certificate seal required')
    outputs = [RELEASE / name for name in ('snapshot.json', 'code.zip', 'admission-certificate.json',
                                          'revision-record.json', 'registration.json')]
    outputs += [RELEASE / 'runs' / path.name for path in scored_manifests()]
    return (c.python(C / 'registry.py', 'release', '--certificate', CERTIFICATE,
                     '--certificate-sha256', digest),
            [*inputs, INDEX, SCHEDULE, PLAN, CERTIFICATE, SEAL, *scored_manifests()], outputs, [RELEASE])


def recorded(action, basis):
    """Validate an existing receipt through command_once; never create a prior action."""
    c.require((RECORDS / (action + '-intent.json')).is_file()
              and (RECORDS / (action + '-receipt.json')).is_file(),
              'Prior action missing or ambiguous; explicit reconciliation required: ' + action)
    argv, inputs, outputs, absent = command_spec(action, basis)
    return c.command_once(RECORDS, action, argv, inputs=inputs, outputs=outputs, absent=absent)


def require_index(basis):
    recorded('prepare-index', basis)
    index = c.read(INDEX)
    c.require(index.get('schema') == 'campaign002-qualification-index-1'
              and index.get('source_revision') == FINAL_REVISION
              and index.get('final_source_snapshot') == c.identity(SNAPSHOT)
              and all(index.get(key) == basis['completed'].get(key)
                      for key in ('native', 'boundary', 'smoke', 'pilots')),
              'Prepared index differs from exact completed V26 ledger')


def execute(action, expected_sha256):
    basis = admission_basis(expected_sha256)
    if action != 'prepare-index':
        require_index(basis)
    if action in ('seal', 'register-release'):
        recorded('prepare-scored', basis)
    if action == 'register-release':
        recorded('seal', basis)
    official = {'schema': 'campaign002-admission-official-status-1',
                'readiness': c.identity(READINESS), 'coordinator': c.identity(Q / 'run_final_qualification_v26.py'),
                'stage_jobs': basis['jobs']}
    c.save_exact(RECORDS / (action + '-official-status.json'), official)
    argv, inputs, outputs, absent = command_spec(action, basis)
    receipt = c.command_once(RECORDS, action, argv, inputs=inputs, outputs=outputs, absent=absent)
    if action == 'register-release':
        digest = c.read(SEAL)['certificate_sha256']
        cert = c.admission.verify_certificate(CERTIFICATE, digest)
        c.admission.verify_registration(RELEASE / 'registration.json', cert, digest)
    print(json.dumps({'action': action, 'command_receipt': c.identity(RECORDS / (action + '-receipt.json')),
                      'exit_code': receipt['exit_code'], 'outputs': receipt['outputs'], 'launch_performed': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('--readiness-sha256', required=True,
                        help='Externally held SHA256 of the immutable V26 readiness declaration')
    args = parser.parse_args()
    execute(args.action, args.readiness_sha256)


if __name__ == '__main__':
    main()
