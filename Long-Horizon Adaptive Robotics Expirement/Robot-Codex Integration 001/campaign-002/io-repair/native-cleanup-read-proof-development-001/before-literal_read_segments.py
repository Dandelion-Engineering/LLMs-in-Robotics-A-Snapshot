"""Authenticate finite literal cat compositions without guessing shell semantics.

Only ordered reads of the five startup files and two trusted JSON mirrors are
supported. Every output byte belongs to one nonempty, source-bound segment.
Nothing here executes a command or synthesizes a model-visible command/output.
"""
from __future__ import annotations
import base64
import json
from pathlib import Path
import re
import shlex
import zipfile

from empty_startup_reads import (environment_proof, finite_time, import_boundary,
                                load_json, require, unique_object)
from retained_reads import load_capture, process_reads, sha

STARTUP_PATHS = ('RobotAgentPrompt.md', 'Tasks.md', 'Robot.md', 'Tools.md', 'Continuity.md')
LIVE_PATHS = ('live/activation.json', 'live/state.json')
APPROVED_PATHS = frozenset(STARTUP_PATHS + LIVE_PATHS)
MAX_OPERANDS = 16
MAX_SCRIPT_BYTES = 4096
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MIRROR_SOURCE = '/campaign-002/harness/runtime.py'
MIRROR_SOURCE_SHA256 = '4e521d64b45de426d31cabecf25669e9f50346a6d82b97a2bcd7f53b6f4dd6ad'
WORD = re.compile(r"(?:'[^'\r\n]*'|\"[^\"$`\\\r\n]*\"|[A-Za-z0-9_./-]+)")


def literal_cat_paths(argv):
    """A finite grammar: literal cat operands, optionally joined by literal &&.

    Quotes may surround a whole path, never an operator/command or part of a
    token. No options, comments, escapes, newlines, expansion or other commands.
    This deliberately does not use commandActions or split an arbitrary shell.
    """
    if (not isinstance(argv, list) or len(argv) != 3 or argv[:2] != ['/usr/bin/bash', '-lc']
            or not isinstance(argv[2], str) or len(argv[2].encode()) > MAX_SCRIPT_BYTES):
        return []
    script, offset, paths, need_command, command_operands = argv[2], 0, [], True, 0
    while offset < len(script):
        while offset < len(script) and script[offset] in ' \t':
            offset += 1
        if offset == len(script):
            break
        if script.startswith('&&', offset):
            if need_command or not command_operands:
                return []
            offset += 2
            need_command, command_operands = True, 0
            continue
        match = WORD.match(script, offset)
        if not match:
            return []
        token = match.group()
        offset = match.end()
        if offset < len(script) and script[offset] not in ' \t' and not script.startswith('&&', offset):
            return []
        if need_command:
            if token not in ('cat', '/bin/cat', '/usr/bin/cat'):
                return []
            need_command = False
        else:
            path = token[1:-1] if token[:1] in ('\"', "'") else token
            path = path.removeprefix('/workspace/')
            if path not in APPROVED_PATHS:
                return []
            paths.append(path)
            command_operands += 1
            if len(paths) > MAX_OPERANDS:
                return []
    return paths if paths and not need_command and command_operands else []


def reject_constant(value):
    raise ValueError('Nonfinite JSON constant: ' + value)


def segment_output(paths, raw, static_bytes):
    """Consume every byte in order; no substring search or whitespace repair."""
    require(0 < len(raw) <= MAX_OUTPUT_BYTES, 'Empty/oversize composed output')
    decoder = json.JSONDecoder(object_pairs_hook=unique_object, parse_constant=reject_constant)
    offset, segments = 0, []
    for name in paths:
        value = None
        if name in LIVE_PATHS:
            remaining = raw[offset:].decode('utf-8', errors='strict')
            value, end = decoder.raw_decode(remaining)
            require(isinstance(value, dict), 'Live segment is not a JSON object')
            required = ({'authority_epoch', 'invocation', 'packet'} if name == 'live/state.json'
                        else {'activation_id', 'authority_epoch', 'invocation', 'order_version'})
            require(required <= value.keys() and isinstance(value['invocation'], dict)
                    and (isinstance(value.get('packet'), dict) if name == 'live/state.json' else 'packet' not in value),
                    'JSON object does not have the requested live source type')
            payload = json.dumps(value, allow_nan=False).encode()
            require(remaining[:end].encode() == payload, 'Live bytes differ from exact readonly JSON producer')
        else:
            payload = static_bytes.get(name)
            require(isinstance(payload, bytes) and payload, 'Missing/nonempty initial bytes required: ' + name)
        require(raw[offset:offset + len(payload)] == payload, 'Segment does not match expected source bytes: ' + name)
        segments.append({'path': name, 'start_byte': offset, 'end_byte': offset + len(payload),
                         'bytes': len(payload), 'sha256': sha(payload), 'value': value})
        offset += len(payload)
    require(offset == len(raw), 'Unconsumed trailing bytes or ambiguous segment boundary')
    return segments


def protected_live_match(name, value, history, public_episode, epoch, invocation_id):
    """Preserve the existing protected identity/observation/order requirements."""
    if (value.get('authority_epoch') != epoch
            or value.get('invocation', {}).get('invocation_id') != invocation_id):
        return None
    if name == 'live/activation.json':
        if value.get('activation_id') == 'activation-001' and value.get('order_version') is not None:
            return {'authority_epoch': epoch, 'invocation_id': invocation_id}
        return None
    packet = value.get('packet', {})
    observations = [e for e in history if e.get('type') == 'observation'
                    and e.get('authority_epoch') == epoch
                    and e.get('payload', {}).get('sequence') == packet.get('sequence')]
    if (packet.get('run_id') != public_episode or len(observations) != 1
            or packet.get('capture_sim_time_s') != observations[0]['payload'].get('capture_sim_time_s')
            or packet.get('order') != observations[0]['payload'].get('order')):
        return None
    return {'authority_epoch': epoch, 'protected_observation_event_id': observations[0]['event_id']}


def static_sources(root, host, source_zip, hashes, history, paths, read_start, receipts):
    needed = set(paths) & set(STARTUP_PATHS)
    result, proofs = {}, {}
    snapshot = load_json(root / 'runtime-before-close.json', receipts) if needed - {'Continuity.md'} else None
    for name in sorted(needed):
        digest = hashes.get(name)
        require(isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest), 'Missing initial input hash: ' + name)
        if name == 'Continuity.md':
            path = host / 'continuity-history' / (digest + '.md')
            raw = path.read_bytes()
            require(raw and sha(raw) == digest, 'Initial continuity is empty/missing/changed; separate empty-read proof required')
            commits = [e for e in history if e.get('type') == 'continuity_committed'
                       and e.get('payload', {}).get('sha256') == digest
                       and e['payload'].get('bytes') == len(raw) and e['wall_unix_s'] < read_start]
            require(commits, 'Initial continuity bytes lack preceding protected commit')
            receipts.append({'path': str(path), 'sha256': digest, 'bytes': len(raw)})
            proofs[name] = {'source': str(path), 'sha256': digest, 'bytes': len(raw),
                            'protected_commit_event_ids': [e['event_id'] for e in commits]}
        else:
            record = snapshot.get('files', {}).get(name, {})
            raw = base64.b64decode(record.get('base64', ''), validate=True)
            if not (raw and sha(raw) == digest == record.get('sha256') == record.get('retained_sha256')
                    and len(raw) == record.get('bytes')):
                # Frozen file bytes may also supply an unchanged static input.
                with zipfile.ZipFile(source_zip) as archive:
                    matches = [(n, archive.read(n)) for n in archive.namelist() if n.endswith('/' + name)]
                matches = [(n, b) for n, b in matches if b and sha(b) == digest]
                require(len(matches) == 1, 'Initial static bytes unavailable or ambiguous: ' + name)
                source, raw = matches[0]
            else:
                source = str(root / 'runtime-before-close.json') + '#' + name
            proofs[name] = {'source': source, 'sha256': digest, 'bytes': len(raw),
                            'binding': 'exact trusted runtime initial hash, raw and retained bytes equal'}
        result[name] = raw
    return result, proofs


def execution_proof(root, event, events, read):
    item, provenance = event['params']['item'], read['provenance']
    rows, delivered, _ = load_capture(root / provenance['file'])
    request = rows[provenance['request_sequence'] - 1]
    require(request.get('original_message_sha256') == request.get('retained_message_sha256'),
            'Process request bytes were changed/redacted')
    params = request['message']['params']
    require(params.get('argv') == shlex.split(item.get('command', ''))
            and params.get('metadata', {}).get('toolCallId') == item.get('id'), 'Actual argv/tool identity mismatch')
    proof = environment_proof(params)
    identities = [e for e in events if e.get('method') in ('item/started', 'item/completed')
                  and e.get('params', {}).get('item', {}).get('id') == item.get('id')]
    require([e['method'] for e in identities] == ['item/started', 'item/completed']
            and all(e['params']['item'].get('command') == item['command'] for e in identities),
            'Ambiguous started/completed command identity')
    for row in rows:
        finite_time(row.get('wall_unix_s'))
    require(all(a['wall_unix_s'] <= b['wall_unix_s'] for a, b in zip(rows, rows[1:])),
            'Executor capture clock/order inconsistent')
    closed = [r for r in rows if r.get('kind') == 'response'
              and (r.get('message') or {}).get('method') == 'process/closed'
              and r['message']['params'].get('processId') == provenance['process_id']]
    require(len(closed) == 1 and closed[0]['sequence'] in delivered, 'Missing unique delivered process close')
    deliveries = [r for r in rows if r.get('kind') == 'delivered'
                  and r.get('response_sequence') == closed[0]['sequence']]
    require(len(deliveries) == 1, 'Missing unique close delivery')
    start, end = request['wall_unix_s'], finite_time(event.get('emittedAtMs')) / 1000
    require(start < closed[0]['wall_unix_s'] <= deliveries[0]['wall_unix_s'] <= end,
            'Process/app completion chronology inconsistent')
    proof.update(request_wall_unix_s=start, closed_wall_unix_s=closed[0]['wall_unix_s'],
                 app_complete_wall_unix_s=end, closed_capture_sequence=closed[0]['sequence'])
    return proof


def assess_literal_reads(root, host, source_zip, public_episode, expected_epoch, invocation_id):
    """Independently read trusted inputs and return additive, explicit evidence."""
    root, host, source_zip = Path(root), Path(host), Path(source_zip)
    audit = {'startup': {n: [] for n in STARTUP_PATHS}, 'live': {n: [] for n in LIVE_PATHS},
             'proofs': [], 'errors': [], 'schema': 'literal-read-segments-1'}
    receipts = []
    try:
        hashes = load_json(root / 'runtime-input-hashes.json', receipts)
        boundary = import_boundary(source_zip, hashes)
        with zipfile.ZipFile(source_zip) as archive:
            names = [n for n in archive.namelist() if n.endswith(MIRROR_SOURCE)]
            require(len(names) == 1 and sha(archive.read(names[0])) == MIRROR_SOURCE_SHA256,
                    'Readonly mirror producer source absent/changed')
            boundary.append({'path': names[0], 'sha256': MIRROR_SOURCE_SHA256})
        receipts.append({'path': str(source_zip), 'sha256': sha(source_zip.read_bytes()), 'bytes': source_zip.stat().st_size})
        for path in (Path(__file__), Path(__file__).with_name('empty_startup_reads.py'), Path(__file__).with_name('retained_reads.py')):
            receipts.append({'path': str(path), 'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size})
        stage = load_json(root / 'stage-result.json', receipts)
        require(stage.get('invocation_id') == invocation_id, 'Declared invocation differs from retained stage')
        result = load_json(host / 'result.json', receipts)
        require(result.get('public_episode_id') == public_episode, 'Declared episode differs from protected result')
        history = load_json(host / 'public-history.jsonl', receipts, lines=True)
        require(history and history[-1].get('type') == 'episode_stopped', 'Incomplete protected history')
        for index, e in enumerate(history, 1):
            require(type(e.get('event_id')) is int and e['event_id'] == index, 'Protected history gap/ambiguity')
            finite_time(e.get('wall_unix_s'))
        starts = [e for e in history if e.get('type') == 'invocation_start-invocation'
                  and e.get('authority_epoch') == expected_epoch
                  and e.get('payload', {}).get('invocation', {}).get('invocation_id') == invocation_id]
        require(len(starts) == 1, 'Expected invocation/epoch lacks unique protected start')
        events = load_json(root / 'client/events.jsonl', receipts, lines=True)
        reads, integrity = process_reads(root, events)
        require(integrity['verified'], 'Executor capture integrity failed: ' + '; '.join(integrity['errors']))
        receipts.extend({'path': str(root / r['file']), 'sha256': r['sha256'],
                         'bytes': (root / r['file']).stat().st_size} for r in integrity['files'])
        for event in events:
            item = event.get('params', {}).get('item', {})
            if event.get('method') != 'item/completed' or item.get('type') != 'commandExecution':
                continue
            try:
                argv = shlex.split(item.get('command', ''))
            except ValueError:
                continue
            paths = literal_cat_paths(argv)
            if not paths:
                continue
            try:
                require(item.get('id') in reads, 'No authenticated successful complete process stream')
                read = reads[item['id']]
                execution = execution_proof(root, event, events, read)
                require(starts[0]['wall_unix_s'] < execution['request_wall_unix_s']
                        < execution['app_complete_wall_unix_s'] < history[-1]['wall_unix_s'],
                        'Read outside protected invocation/episode chronology')
                candidate_receipts = list(receipts)
                static, static_proof = static_sources(root, host, source_zip, hashes, history, paths,
                                                      execution['request_wall_unix_s'], candidate_receipts)
                segments = segment_output(paths, read['stdout'].encode(), static)
                proof = {'item_id': item['id'], 'match': 'authenticated_literal_cat_segments',
                         'ordered_paths': paths, 'whole_output_consumed': True,
                         'segments': [{k: v for k, v in s.items() if k != 'value'} for s in segments],
                         'executor_provenance': read['provenance'], 'execution': execution,
                         'static_sources': static_proof, 'source_contract': boundary, 'inputs': candidate_receipts,
                         'scope': 'Complete source output through process/closed; startup requires equal app projection. No attention claim.'}
                audit['proofs'].append(proof)
                raw_proof = None
                if read['provenance']['app_projection_equals_executor'] is not True and any(n in STARTUP_PATHS for n in paths):
                    try:
                        from raw_tool_result_reads import raw_result_proof
                        raw_proof = raw_result_proof(root, event, events, read, source_zip)
                        proof['prepared_tool_result'] = raw_proof
                    except (ValueError, KeyError, TypeError, OSError, UnicodeError, zipfile.BadZipFile) as error:
                        proof['prepared_tool_result_error'] = str(error)
                for segment in segments:
                    name = segment['path']
                    evidence = {'item_id': item['id'], 'match': proof['match'],
                                'segment': {k: v for k, v in segment.items() if k != 'value'},
                                'executor_provenance': read['provenance'], 'proof_index': len(audit['proofs']) - 1}
                    if name in STARTUP_PATHS:
                        if read['provenance']['app_projection_equals_executor'] is True:
                            audit['startup'][name].append({**evidence, 'input_sha256': hashes[name]})
                        elif raw_proof is not None:
                            audit['startup'][name].append({**evidence, 'input_sha256': hashes[name],
                                'match': 'complete_prepared_tool_result_literal_segments',
                                'app_projection_equals_executor': False, 'prepared_tool_result': raw_proof})
                    else:
                        match = protected_live_match(name, segment['value'], history, public_episode,
                                                     expected_epoch, invocation_id)
                        if match:
                            audit['live'][name].append({**evidence, **match, 'observed_read_sha256': segment['sha256'],
                                'app_projection_equals_executor': read['provenance']['app_projection_equals_executor']})
            except (ValueError, KeyError, TypeError, OSError, UnicodeError) as error:
                audit['errors'].append(str(item.get('id')) + ': ' + str(error))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, zipfile.BadZipFile) as error:
        audit['errors'].append(str(error))
    return audit
