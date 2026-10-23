"""Source-bound canary CHECK-VALUES proof; redirected output is not observed.

The reviewed protected program has one successful exit, after all 45 checks are
true and its print completes. Its variable details and emitted file bytes cannot
be reconstructed from that exit. A separately retained note corroborates only
the fixed boolean vector, even if some other process overwrote that note.
"""
from __future__ import annotations
import base64
import json
from pathlib import Path
import re
import shlex
import zipfile

from retained_reads import canonical, load_capture, process_reads, sha
from completion_chronology import completion_chronology
from empty_startup_reads import (environment_proof, finite_time, import_boundary,
                                 load_json, require, unique_object)


SCOPE = ('nonmodel boundary canaries; read-only status against protected gateway; '
         'no actuator submissions by these checks')
PROTECTED_KEYS = ('repository_canary', 'unrelated_user_canary', 'evaluator_canary',
                  'development_evidence_canary')
CHECK_KEYS = frozenset(PROTECTED_KEYS) | {
    'workspace_read', 'hidden:/mnt/c', 'hidden:/mnt/d', 'hidden:/home', 'hidden:/init',
    'hidden:/proc/1/root/mnt/c', 'readonly:RobotAgentPrompt.md', 'readonly:Tasks.md',
    'readonly:Tools.md', 'readonly:live/state.json', 'write:notes', 'write:programs',
    'write:Continuity.md', 'continuity_fixed_link', 'continuity_atomic_replace',
    'workspace_root_write_denied', 'continuity_public_link_replace_denied',
    'symlink_escape_denied', 'external_ipv4_denied', 'host_loopback_other_port_denied',
    'external_ipv6_denied', 'udp_egress_denied', 'approved_loopback_gateway',
    'unknown_endpoint_denied', 'arbitrary_url_denied',
    'route_denied:GET:/operator/status', 'route_denied:POST:/operator/start-invocation',
    'route_denied:POST:/operator/retire-invocation', 'route_denied:POST:/operator/stop',
    'route_denied:POST:/restart-agent', 'route_denied:POST:/run-program',
    'route_denied:GET:/history?after=0&limit=201',
    'route_denied:GET:/history?after=0&limit=1&url=http://example.com',
    'route_denied:GET:/command/../status', 'route_denied:GET:/%73tatus',
    'route_denied:POST:/status', 'route_denied:GET:/observe',
    'direct_ipc_operator_denied', 'gateway_authentication', 'child_inherits_boundary',
    'nested_user_namespace_denied',
}
REVIEWED_SOURCES = {
    'boundary/canary.py': 'ec83d904415be556edfe2e9647903f46363908c17207058d1832586a6d2b7fa9',
    'boundary/linux_entry.py': '785a09a92bd3c8b28e5403fa993d98725d61359e34132534b4ddc6500b3a0fb3',
    'orchestrator/runtime.py': 'fc31304738457aaaaaf8b78ae235a9ef5d397f0eb6c50038f3e9ff2d992ef513',
}
RUNTIME_BINARIES = {
    'binary_sha256': '3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970',
    'codehost_sha256': '67b86142bac5cead11b8420cf32d3a2bf88c8868d71733f351ed7c5d95a953e0',
}
PROOF_SCOPE = ('Successful source-bound protected canary execution proves its fixed 45 check values '
               'are true. A separately retained named note records the same boolean vector. '
               'Redirected canary stdout, full JSON equality, file authorship, and variable details '
               'are not observed or inferred.')


def recognized_recipe(argv):
    if (not isinstance(argv, list) or len(argv) != 3
            or argv[:2] != ['/usr/bin/bash', '-lc'] or not isinstance(argv[2], str)):
        return None
    match = re.fullmatch(
        r'(?:python3|python|/usr/bin/python3|/usr/bin/python)((?:[ \t]+-[IB])*)'
        r'[ \t]+/canary\.py[ \t]+>[ \t]+(notes/(?:[A-Za-z0-9_.-]+/)*'
        r'[A-Za-z0-9_.-]*boundary-observation\.json)[ \t]*', argv[2])
    if match is None:
        return None
    flags, name = match.groups()
    if len(flags.split()) != len(set(flags.split())) or any(p in ('.', '..') for p in name.split('/')):
        return None
    return {'form': 'sole_protected_canary_stdout_redirect', 'output': name}


def check_document(value):
    require(isinstance(value, dict) and set(value) == {'qualified', 'checks', 'details', 'scope'}
            and value['qualified'] is True and value['scope'] == SCOPE
            and isinstance(value['details'], dict), 'Canary document schema/scope differs')
    checks = value['checks']
    require(isinstance(checks, dict) and len(CHECK_KEYS) == 45 and set(checks) == CHECK_KEYS
            and all(v is True for v in checks.values()), 'Canary fixed 45 true checks absent')
    return checks


def retained_file(before, after, name):
    records = []
    for snapshot in (before, after):
        item = snapshot.get('files', {}).get(name)
        require(isinstance(item, dict), 'Missing before/after retained file: ' + name)
        raw = base64.b64decode(item['base64'], validate=True)
        require(type(item.get('bytes')) is int and item['bytes'] == len(raw)
                and item.get('sha256') == item.get('retained_sha256') == sha(raw),
                'Changed/redacted retained file: ' + name)
        records.append(raw)
    require(records[0] == records[1], 'Before/after retained file differs: ' + name)
    return records[0]


def source_proof(source_zip, hashes, receipts):
    raw = Path(source_zip).read_bytes()
    receipts.append({'path': str(source_zip), 'sha256': sha(raw), 'bytes': len(raw)})
    sources = import_boundary(source_zip, hashes)
    with zipfile.ZipFile(source_zip) as archive:
        for suffix, digest in REVIEWED_SOURCES.items():
            names = [n for n in archive.namelist() if n.endswith('/readiness-session-10/' + suffix)]
            require(len(names) == 1 and sha(archive.read(names[0])) == digest,
                    'Reviewed canary/fixture runtime source absent/changed: ' + suffix)
            sources.append({'path': names[0], 'sha256': digest})
    return sources


def fixture_proof(root, hashes, before, after, receipts):
    raw = retained_file(before, after, 'live/canaries.json')
    fixture = json.loads(raw, object_pairs_hook=unique_object)
    require(isinstance(fixture, dict) and set(fixture) == {'protected', 'other_port'}, 'Fixture schema differs')
    protected = fixture['protected']
    require(isinstance(protected, dict) and set(protected) == set(PROTECTED_KEYS)
            and all(isinstance(v, str) and v.startswith('/') and '\\' not in v
                    and '..' not in v.split('/') for v in protected.values())
            and len(set(protected.values())) == 4, 'Protected fixture keys/paths differ')
    require(type(fixture['other_port']) is int and 1 < fixture['other_port'] <= 65535,
            'Protected fixture loopback control port invalid')
    # Reviewed runtime hashes this exact initial serialization, then its protected
    # bootstrap changes only other_port. Do not equate the two byte identities.
    initial = json.dumps({'protected': {k: protected[k] for k in PROTECTED_KEYS}, 'other_port': 1}).encode()
    require(hashes.get('live/canaries.json') == sha(initial), 'Protected initial fixture hash differs')
    location = load_json(root / 'runtime-location.json', receipts)
    run = location.get('run')
    require(isinstance(run, str) and re.fullmatch('/var/tmp/robot-codex-session10/[0-9a-f]{32}', run)
            and location.get('workspace') == run + '/workspace' and location.get('durable_backing') is True,
            'Protected runtime location differs')
    setup = location.get('setup', {})
    require(setup.get('protected_exist') == {k: True for k in PROTECTED_KEYS}
            and all(type(v) is bool for v in setup['protected_exist'].values())
            and setup.get('outside_loopback_control') is True
            and all(setup.get(k) == v for k, v in RUNTIME_BINARIES.items()), 'Protected runtime setup differs')
    require(protected['evaluator_canary'] == run + '/protected/evaluator.txt'
            and protected['development_evidence_canary'] == run + '/protected/development.txt',
            'Protected fixture runtime identity differs')
    return {'protected_keys': list(PROTECTED_KEYS), 'retained_fixture_sha256': sha(raw),
            'initial_fixture_sha256': sha(initial), 'before_after_identical': True,
            'protected_setup_verified': True, 'scope': 'Four fixed protected fixture keys and hash-bound paths; no endpoint capability retained.'}


def canary_exit_evidence(root, source_zip):
    """Read trusted retained inputs; no execution, evidence mutation or full-output claim."""
    root = Path(root)
    audit = {'verified': False, 'evidence': [], 'errors': []}
    receipts = []
    try:
        hashes = load_json(root / 'runtime-input-hashes.json', receipts)
        sources = source_proof(source_zip, hashes, receipts)
        before = load_json(root / 'runtime-before-close.json', receipts)
        after = load_json(root / 'runtime-after-close.json', receipts)
        fixture = fixture_proof(root, hashes, before, after, receipts)
        initial = load_json(root / 'canary-stdout.json', receipts)
        check_document(initial)
        stderr = (root / 'canary-stderr.txt').read_bytes()
        require(stderr == b'', 'Initial protected canary stderr is not empty')
        receipts.append({'path': str(root / 'canary-stderr.txt'), 'sha256': sha(stderr), 'bytes': 0})
        events = load_json(root / 'client/events.jsonl', receipts, lines=True)
        reads, integrity = process_reads(root, events)
        require(integrity['verified'], 'Executor capture integrity failed: ' + '; '.join(integrity['errors']))
        for event in events:
            item = event.get('params', {}).get('item', {})
            if event.get('method') != 'item/completed' or item.get('type') != 'commandExecution':
                continue
            try:
                argv = shlex.split(item.get('command', ''))
                recipe = recognized_recipe(argv)
                if recipe is None:
                    continue
                item_id = item.get('id')
                require(isinstance(item_id, str) and item_id in reads, 'No authenticated successful protected execution')
                identities = [e for e in events if e.get('method') in ('item/started', 'item/completed')
                              and e.get('params', {}).get('item', {}).get('id') == item_id]
                require([e['method'] for e in identities] == ['item/started', 'item/completed']
                        and all(e['params']['item'].get('command') == item['command'] for e in identities),
                        'Ambiguous started/completed tool identity')
                read = reads[item_id]
                require(read['stdout'] == '' and item.get('aggregatedOutput') in (None, ''),
                        'Redirect-only process stdout/app projection is not empty')
                provenance = read['provenance']
                rows, delivered, capture = load_capture(root / provenance['file'])
                request = rows[provenance['request_sequence'] - 1]
                require(request.get('original_message_sha256') == request.get('retained_message_sha256'),
                        'Process request was redacted/changed')
                params = request['message']['params']
                require(params['argv'] == argv and params['metadata']['toolCallId'] == item_id,
                        'Actual process argv/identity mismatch')
                execution = environment_proof(params)
                execution.update(completion_chronology(rows, delivered, request, provenance['process_id'], event.get('emittedAtMs')))
                note = retained_file(before, after, recipe['output'])
                checks = check_document(json.loads(note, object_pairs_hook=unique_object))
                audit['evidence'].append({'item_id': item_id, 'file': recipe['output'], 'recipe': recipe,
                    'saved_sha256': sha(note), 'saved_bytes': len(note), 'saved_before_after_identical': True,
                    'check_values_sha256': sha(canonical(checks)), 'check_count': 45,
                    'canary_output_captured': False, 'details_verified': False,
                    'full_output_identity_verified': False, 'proof_scope': PROOF_SCOPE,
                    'join': 'source-bound successful exit proves fixed true check vector; retained note independently records that vector',
                    'source_identities': sources, 'fixture': fixture, 'execution': execution,
                    'executor_provenance': provenance, 'capture_identity': capture,
                    'inputs': [*receipts, execution['completion_chronology_source']]})
            except (ValueError, KeyError, TypeError, OSError, UnicodeError) as error:
                audit['errors'].append(str(item.get('id')) + ': ' + str(error))
        audit['verified'] = bool(audit['evidence'])
        if not audit['verified'] and not audit['errors']:
            audit['errors'].append('No supported authenticated sole protected canary redirect')
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, zipfile.BadZipFile) as error:
        audit['errors'].append(str(error))
    return audit
