"""Single-use declared diagnostic actions; imports and tests perform no actions."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import zipfile

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
MAP = RCI.parent / 'Architecture Map'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = load(HERE / 'prepare_socket_abort_diagnostic.py', 'socket_abort_preparer')
c = load(CAMPAIGN / 'qualification/run_final_qualification_v28.py', 'socket_abort_action_journal')
RUN, REV = p.RUN, p.REVISION
MANIFEST = p.OUTPUT
SNAPSHOT = MAP / 'releases' / REV / 'snapshot.json'
PREVIOUS = MAP / 'releases/RCI001-C02-dev-090/snapshot.json'
BASELINE = MAP / 'releases/RCI001-wsl-010d/snapshot.json'
JOURNAL = HERE / 'shutdown-diagnostic-control-003'
RAW = RCI / 'local-evidence/campaign002/io-repair' / RUN
WORKSPACE = Path(__import__('os').environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/diagnostic' / RUN
BOUND_TESTS = HERE / 'checks-033/repair-test-receipt.json'
EXPECTED_CHANGES = {
    'harness/codehost_bridge_v3.py': '419c13a6761fa23bed0a06b540ffba3f327a2d86ff94ad55e1c9b8ece16b0a75',
    'harness/test_codehost_bridge_v3.py': 'b0f9002e0740b5998b7c4e7c1d61cbbab143ea5e9bc348750cffeba1f113f2ef',
    'assessment/test_transport_integrity_v3.py': '1f21e835e94e14ba253988bf23da7dcb9a285f7ffd4d7777ec03950f78c5c198',
}
PINS = {
    'SOCKET_ABORT_DIAGNOSTICS_V1.md': 'ec46e6212cfc9b2844fd45715014a1a96b749d3764a2031fe4eec6d6076109d8',
    'SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md': 'eda635ef8981a0c28ceeeb90df9f5426213f87f6e8c874658381f8ee29368314',
    'socket-abort-instrumentation-development-001/final-check-002/receipt.json': 'bb32cf972292600338fd47e9da18a3354255bd15288b70b66c732120f2e990e1',
    'socket-abort-instrumentation-development-001/final-check-002/source-parity.json': '8e6e48609004d51986fb5c5220e81ef0e243202cd8420d25bdc841438d1fc4e5',
    'socket-abort-assessment-fixture-development-001/final-receipt.json': 'a56b23e20f19106b69ee002a69395afc460bf4af8f0346d2995e1ee765455cb2',
    'socket-abort-loopback-development-002/execution-001/receipt.json': '53e10c5097dcf46640450c17266ba8f8a32d5017aff0d4432a60d1177471034e',
    'socket-abort-loopback-development-002/execution-001/child/result.json': 'a8ca5f643403d73bdae9cfca2787bac27d769347ea55855f8bfe9cd78c4780dc',
    'checks-033/test-execution.json': '38c58df4587a36714c282244c0c02d534af071b4b93ed56ae8ed818bccfa078f',
    'checks-033-source-state.json': '0e2c97339cbfe7713ebbb4ce561fbb2787126931ca16832eb256d50aa4f3f88c',
    'checks-033-execution-001/receipt.json': '562815716f583bb4e86a90885c69055e661f9faa9f5b3c504d8a14dbc5606ba2',
}


def name(path):
    return Path(path).resolve().relative_to(REPO).as_posix()


def binding(path):
    item = p.identity(path)
    return {key: item[key] for key in ('sha256', 'bytes')}


def artifact(item):
    path = p.checked_path(item['path'])
    actual = p.identity(path)
    p.require(item.get('sha256') == actual['sha256']
              and ('bytes' not in item or type(item['bytes']) is int and item['bytes'] == actual['bytes']),
              'Artifact changed: ' + str(path))
    return path


def final_checks(path, schema, source_paths, expected_argv):
    value = p.read(path)
    p.require(value.get('schema') == schema and value.get('passed') is True,
              'Final diagnostic checks missing or failed')
    expected = {f.relative_to(CAMPAIGN).as_posix(): binding(f) for f in source_paths}
    p.require(value.get('source_bindings') == expected, 'Final diagnostic tested sources differ')
    commands = value.get('commands')
    p.require(isinstance(commands, list) and len(commands) == 1, 'Exact diagnostic check command required')
    command = commands[0]
    p.require(command.get('argv') == expected_argv and type(command.get('exit_code')) is int
              and command['exit_code'] == 0, 'Diagnostic command failed or differs')
    for key in ('stdout', 'stderr'):
        artifact(command[key])
    return value


def support_checks():
    for relative, expected in PINS.items():
        p.require(p.identity(HERE / relative)['sha256'] == expected, 'Declared support changed: ' + relative)
    execution = p.read(HERE / 'checks-033/test-execution.json')
    state = p.read(HERE / 'checks-033-source-state.json')
    outer = p.read(HERE / 'checks-033-execution-001/receipt.json')
    p.require(execution.get('passed') is True and state.get('passed') is True
              and state.get('sources_unchanged') is True and outer.get('passed') is True
              and type(outer.get('exit_code')) is int and outer['exit_code'] == 0,
              'Full checks failed')
    p.require(artifact(state['tests']) == HERE / 'checks-033/test-execution.json'
              and artifact(outer['source_state']) == HERE / 'checks-033-source-state.json'
              and outer['sources_after'] == state['sources'], 'Full check source-state join differs')
    seen = set()
    for item in state['sources']:
        source = artifact(item)
        p.require(source not in seen, 'Duplicate full-check source'); seen.add(source)
    p.require(len(seen) == 223, 'Full-check source inventory differs')
    commands = execution.get('commands')
    p.require(isinstance(commands, list) and len(commands) == 2, 'Both full suites required')
    for command, directory in zip(commands, ('harness', 'assessment')):
        expected = [str(c.PYTHON), '-X', 'utf8', '-B', '-m', 'unittest', 'discover',
                    '-s', str(CAMPAIGN / directory), '-p', 'test_*.py', '-v']
        p.require(command.get('argv') == expected and type(command.get('exit_code')) is int
                  and command['exit_code'] == 0 and command.get('test_sources_unchanged') is True,
                  'Full check command differs or failed')
        declared = {str(artifact(item)) for item in command['test_inputs']}
        p.require(declared == c.test_targets(expected), 'Full check discovery changed')
        artifact(command['stdout']); artifact(command['stderr'])
    for path in (HERE / list(PINS)[2], HERE / list(PINS)[3]):
        p.require(p.read(path).get('passed') is True, 'Instrumentation or parity failed')
    p.require(p.identity(CAMPAIGN / 'assessment/transport_integrity_v3.py')['sha256']
              == '758a936c2d1bfad6389589cdf80e83e92950353c47418e65abd47a432a88c18e',
              'Production transport assessor changed')
    wrapper = p.WRAPPER
    final_checks(p.WRAPPER_RECEIPT, 'campaign002-single-interrupt-v3-development-1',
                 sorted(wrapper.glob('*.py')), [str(c.PYTHON), '-X', 'utf8', '-B', '-m',
                 'unittest', 'discover', '-s', str(wrapper), '-p', 'test_*.py', '-v'])
    final_checks(p.CONTROL_RECEIPT, 'campaign002-socket-abort-native-control-development-1',
                 [HERE / n for n in ('prepare_socket_abort_diagnostic.py', 'control_socket_abort_diagnostic.py',
                                    'test_control_socket_abort_diagnostic.py')],
                 [str(c.PYTHON), '-X', 'utf8', '-B', str(HERE / 'test_control_socket_abort_diagnostic.py'), '-v'])
    return execution


def archive_sources(path, expected_sha=None, current=False):
    if expected_sha:
        p.require(p.identity(path)['sha256'] == expected_sha, 'Source snapshot identity differs')
    snapshot = p.read(path); sources = snapshot['sources']
    with zipfile.ZipFile(path.with_name('code.zip')) as archive:
        info = archive.infolist()
        p.require(len(info) == len(sources) and {item.filename for item in info} == set(sources)
                  and sum(item.file_size for item in info) <= 64 * 1024 * 1024,
                  'Archive member inventory differs or exceeds bound')
        for item in info:
            source = REPO / item.filename
            p.require(not item.is_dir() and not stat.S_ISLNK(item.external_attr >> 16)
                      and not Path(item.filename).is_absolute() and '..' not in Path(item.filename).parts
                      and source.resolve().is_relative_to(REPO) and item.file_size <= 16 * 1024 * 1024,
                      'Invalid archive member')
            raw = archive.read(item)
            expected = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
            p.require(sources[item.filename] == expected, 'Archive source identity differs')
            if current:
                p.require(binding(source) == expected, 'Current source differs from freeze')
    return snapshot


def compare_sources(old, new, baseline, declared_inputs):
    p.require(len(baseline) == 624, 'Original624 inventory differs')
    changes = sorted(n for n in set(old) & set(new) if old[n] != new[n])
    expected = {name(CAMPAIGN / k): v for k, v in EXPECTED_CHANGES.items()}
    p.require(set(changes) == set(expected) and all(new[n]['sha256'] == h for n, h in expected.items()),
              'Unexpected shared-source changes')
    removed = sorted(set(old) - set(new)); added = sorted(set(new) - set(old))
    p.require(not removed and set(new) == set(old) | set(declared_inputs),
              'Unexpected source additions or omissions')
    p.require(all(old.get(n) == item == new.get(n) for n, item in baseline.items()),
              'Original624 source changed or omitted')
    return {'changed_existing_sources': changes, 'added_sources': added, 'removed_sources': removed}


def source_inventory(manifest, frozen=False):
    common = p.load_wrapper(); common.validate_manifest(manifest)
    p.require(manifest == p.build_manifest(p.read(p.BASIS), p.inputs()), 'Prepared source inventory differs')
    old = archive_sources(PREVIOUS, 'a72d7068856370b531a0b5e704ca6e8bf1f8091d5798a5c08fbd0f8c0cd476b9')
    baseline = archive_sources(BASELINE, 'd84c510ee923a395417944e70a90ab1fa3759bc0061c2b6a4a714fb708f25581')
    if frozen:
        common.validate(MANIFEST, SNAPSHOT)
        new = archive_sources(SNAPSHOT, current=True)['sources']
    else:
        new = {n: binding(REPO / n) for n in set(old['sources']) | set(manifest['runtime_input_files'])}
    delta = compare_sources(old['sources'], new, baseline['sources'], manifest['runtime_input_files'])
    p.require(all(binding(REPO / n) == item for n, item in baseline['sources'].items()),
              'Current original624 changed')
    return {'schema': 'campaign002-socket-abort-native-source-inventory-1',
            'before': c.identity(PREVIOUS), 'baseline': c.identity(BASELINE),
            'after': c.identity(SNAPSHOT) if frozen else None, 'sources': new,
            'protected624_verified': True, 'archives_verified': frozen,
            'diagnostic_only': True, **delta}


def run_action(action):
    support_checks()
    if action == 'prepare':
        candidate = p.build_manifest(p.read(p.BASIS), p.inputs())
        source_inventory(candidate)
        return c.command_once(JOURNAL, 'prepare', c.python(HERE / 'prepare_socket_abort_diagnostic.py'),
            inputs=[HERE / n for n in PINS] + [p.WRAPPER_RECEIPT, p.CONTROL_RECEIPT],
            outputs=[MANIFEST, MANIFEST.with_name('preparation-receipt.json')], absent=[MANIFEST.parent])
    manifest = p.read(MANIFEST)
    if action == 'freeze':
        source_inventory(manifest)
        result = c.command_once(JOURNAL, 'freeze', c.python(CAMPAIGN / 'registry.py', 'freeze',
            '--manifest', MANIFEST, '--revision', REV),
            inputs=[MANIFEST, p.WRAPPER_RECEIPT, p.CONTROL_RECEIPT, HERE / 'checks-033-source-state.json'],
            outputs=[SNAPSHOT, SNAPSHOT.with_name('code.zip'), SNAPSHOT.with_name('revision-record.json'),
                     SNAPSHOT.with_name('run-record.json')], absent=[SNAPSHOT.parent])
        c.save_exact(JOURNAL / 'source-change-inventory.json', source_inventory(manifest, frozen=True))
        return result
    p.require(action == 'launch', 'Unknown action')
    inventory = source_inventory(manifest, frozen=True)
    p.require(p.read(JOURNAL / 'source-change-inventory.json') == inventory, 'Frozen source inventory changed')
    bound = c.verify_repair_tests(c.identity(BOUND_TESTS), {'source_snapshot': c.identity(SNAPSHOT)})
    p.require(bound['commands'] == p.read(HERE / 'checks-033/test-execution.json')['commands'],
              'Bound full checks differ from original checks033')
    return c.command_once(JOURNAL, 'launch', c.python(p.WRAPPER / 'launch.py',
        '--manifest', MANIFEST, '--snapshot', SNAPSHOT),
        inputs=[MANIFEST, SNAPSHOT, BOUND_TESTS, p.WRAPPER_RECEIPT, p.CONTROL_RECEIPT,
                JOURNAL / 'source-change-inventory.json'],
        outputs=[MANIFEST.parent / 'records/queue-submit.json'],
        absent=[MANIFEST.parent / 'records', RAW, WORKSPACE])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'freeze', 'launch'])
    args = parser.parse_args()
    result = run_action(args.action)
    print(json.dumps({'action': args.action, 'exit_code': result['exit_code'], 'stdout': result['stdout']}))


if __name__ == '__main__':
    main()
