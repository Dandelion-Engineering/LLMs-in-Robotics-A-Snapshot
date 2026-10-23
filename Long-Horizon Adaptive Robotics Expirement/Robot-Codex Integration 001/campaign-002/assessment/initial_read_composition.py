"""Finite, authenticated initial-Continuity compositions; no shell evaluation.

The terminal-empty form consumes all preceding source bytes.  The listing form
attributes only the complete protected initial prefix; its remainder is unknown.
Neither form accepts a shortened app projection or changes a historical verdict.
"""
from __future__ import annotations

from pathlib import Path
import re
import shlex
import zipfile

import literal_read_segments as literal
from empty_startup_reads import EMPTY_SHA256, finite_time, import_boundary, load_json, require
from retained_reads import process_reads, sha


SCHEMA = 'initial-read-compositions-1'
ROOT_PREFIXES = (b'/workspace/notes', b'/workspace/programs')
FIND_SCRIPT = r"find /workspace/notes /workspace/programs -maxdepth 3 -type f -printf '%p\n'"
FILTERED_FIND_SCRIPT = ('find /workspace/notes /workspace/programs /workspace/live -maxdepth 3 -type f '
                        '! -name endpoint.json ! -name state.json ! -name activation.json -print')
FILTERED_ROOT_PREFIXES = ROOT_PREFIXES + (b'/workspace/live',)
PRINT_FIND_SCRIPT = 'find /workspace/notes /workspace/programs -maxdepth 3 -type f -print'
_CAT_PATH = r'''(?:Continuity\.md|/workspace/Continuity\.md|'Continuity\.md'|'/workspace/Continuity\.md'|"Continuity\.md"|"/workspace/Continuity\.md")'''
_PREFIX_RECIPE = re.compile(r'[ \t]*cat[ \t]+' + _CAT_PATH + r'[ \t]*&&[ \t]*'
                            + re.escape(FIND_SCRIPT) + r'[ \t]*')
_FILTERED_RECIPE = re.compile(r'[ \t]*cat[ \t]+' + _CAT_PATH + r'[ \t]*&&[ \t]*'
                              + re.escape(FILTERED_FIND_SCRIPT) + r'[ \t]*')

_PRINT_RECIPE = re.compile(r'[ \t]*cat[ \t]+' + _CAT_PATH + r'[ \t]*&&[ \t]*'
                           + re.escape(PRINT_FIND_SCRIPT) + r'[ \t]*')


def find_prefix_roots(argv):
    """Return only the root set for one of the three complete finite recipes."""
    if (not isinstance(argv, list) or len(argv) != 3 or argv[:2] != ['/usr/bin/bash', '-lc']
            or not isinstance(argv[2], str) or len(argv[2].encode()) > literal.MAX_SCRIPT_BYTES):
        return None
    if _PREFIX_RECIPE.fullmatch(argv[2]) or _PRINT_RECIPE.fullmatch(argv[2]):
        return ROOT_PREFIXES
    if _FILTERED_RECIPE.fullmatch(argv[2]):
        return FILTERED_ROOT_PREFIXES
    return None


def find_prefix_recipe(argv):
    return find_prefix_roots(argv) is not None


def prefix_attribution(expected, raw, roots=ROOT_PREFIXES):
    """Prove find cannot supply any byte of the required initial prefix."""
    require(isinstance(expected, bytes) and 0 < len(expected) <= literal.MAX_OUTPUT_BYTES,
            'Initial prefix must be bounded and nonempty')
    require(isinstance(raw, bytes) and 0 < len(raw) <= literal.MAX_OUTPUT_BYTES,
            'Empty/oversize composed output')
    require(raw[:len(expected)] == expected, 'Complete initial prefix differs from observed bytes')
    require(roots in (ROOT_PREFIXES, FILTERED_ROOT_PREFIXES), 'Unsupported find root set')
    for root in roots:
        require(root not in expected, 'Find root occurs inside initial prefix')
        require(not any(expected.endswith(root[:size]) for size in range(1, len(root))),
                'Find root can straddle initial prefix boundary')
    return {'segment': {'path': 'Continuity.md', 'start_byte': 0, 'end_byte': len(expected),
                        'bytes': len(expected), 'sha256': sha(expected)},
            'excluded_find_initial_prefixes': [root.decode() for root in roots],
            'root_straddle_excluded': True,
            'unattributed_remainder': {'start_byte': len(expected), 'end_byte': len(raw),
                                      'bytes': len(raw) - len(expected), 'sha256': sha(raw[len(expected):])},
            'whole_current_file_identity_claimed': False,
            'remainder_listing_snapshot_claimed': False}


def _source_receipt(path):
    raw = Path(path).read_bytes()
    return {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def assess_initial_read_compositions(root, host, source_zip, public_episode, expected_epoch, invocation_id):
    """Return additive startup proofs only after every declared gate succeeds."""
    root, host, source_zip = Path(root), Path(host), Path(source_zip)
    audit = {'schema': SCHEMA, 'startup': {'Continuity.md': []}, 'proofs': [], 'errors': []}
    receipts = []
    try:
        hashes = load_json(root / 'runtime-input-hashes.json', receipts)
        boundary = import_boundary(source_zip, hashes)
        with zipfile.ZipFile(source_zip) as archive:
            boundary.append(literal.mirror_source_contract(archive))
        receipts.append(_source_receipt(source_zip))
        for name in ('initial_read_composition.py', 'literal_read_segments.py', 'empty_startup_reads.py',
                     'retained_reads.py', 'completion_chronology.py'):
            receipts.append(_source_receipt(Path(__file__).with_name(name)))
        stage = load_json(root / 'stage-result.json', receipts)
        require(stage.get('invocation_id') == invocation_id, 'Declared invocation differs from retained stage')
        result = load_json(host / 'result.json', receipts)
        require(result.get('public_episode_id') == public_episode, 'Declared episode differs from protected result')
        history = load_json(host / 'public-history.jsonl', receipts, lines=True)
        require(history and history[-1].get('type') == 'episode_stopped', 'Incomplete protected history')
        for index, event in enumerate(history, 1):
            require(type(event.get('event_id')) is int and event['event_id'] == index,
                    'Protected history gap/ambiguity')
            finite_time(event.get('wall_unix_s'))
        require(all(a['wall_unix_s'] <= b['wall_unix_s'] for a, b in zip(history, history[1:])),
                'Protected history clock/order inconsistent')
        starts = [event for event in history if event.get('type') == 'invocation_start-invocation'
                  and event.get('authority_epoch') == expected_epoch
                  and event.get('payload', {}).get('invocation', {}).get('invocation_id') == invocation_id]
        require(len(starts) == 1, 'Expected invocation/epoch lacks unique protected start')
        events = load_json(root / 'client/events.jsonl', receipts, lines=True)
        reads, integrity = process_reads(root, events)
        require(integrity['verified'], 'Executor capture integrity failed: ' + '; '.join(integrity['errors']))
        receipts.extend(_source_receipt(root / record['file']) for record in integrity['files'])
        for event in events:
            item = event.get('params', {}).get('item', {})
            if event.get('method') != 'item/completed' or item.get('type') != 'commandExecution':
                continue
            try:
                argv = shlex.split(item.get('command', ''))
            except ValueError:
                continue
            paths = literal.literal_cat_paths(argv)
            empty = len(paths) >= 2 and paths[-1] == 'Continuity.md' and paths.count('Continuity.md') == 1
            prefix = find_prefix_recipe(argv)
            if not empty and not prefix:
                continue
            try:
                require(item.get('id') in reads, 'No authenticated successful complete process stream')
                read = reads[item['id']]
                require(read['provenance']['app_projection_equals_executor'] is True,
                        'Complete app-visible output differs from executor output')
                raw = read['stdout'].encode()
                require(0 < len(raw) <= literal.MAX_OUTPUT_BYTES, 'Empty/oversize composed output')
                execution = literal.execution_proof(root, event, events, read)
                require(starts[0]['wall_unix_s'] < execution['request_wall_unix_s']
                        < execution['evidence_complete_upper_wall_unix_s'] < history[-1]['wall_unix_s'],
                        'Read outside protected invocation/episode chronology')
                candidate_receipts = list(receipts)
                if empty:
                    require(hashes.get('Continuity.md') == EMPTY_SHA256,
                            'Terminal-empty composition requires initial empty hash')
                    path = host / 'continuity-history' / (EMPTY_SHA256 + '.md')
                    require(path.read_bytes() == b'', 'Protected initial empty bytes missing/changed')
                    candidate_receipts.append(_source_receipt(path))
                    static, static_proof = literal.static_sources(root, host, source_zip, hashes, history,
                        paths[:-1], execution['request_wall_unix_s'], candidate_receipts)
                    segments = literal.segment_output(paths[:-1], raw, static)
                    live_proofs = []
                    for segment in segments:
                        if segment['path'] in literal.LIVE_PATHS:
                            match = literal.protected_live_match(segment['path'], segment['value'], history,
                                public_episode, expected_epoch, invocation_id)
                            require(match is not None, 'Preceding live source differs from protected invocation/observation')
                            live_proofs.append({'path': segment['path'], **match})
                    segment = {'path': 'Continuity.md', 'start_byte': len(raw), 'end_byte': len(raw),
                               'bytes': 0, 'sha256': EMPTY_SHA256}
                    static_proof['Continuity.md'] = {'source': str(path), 'sha256': EMPTY_SHA256, 'bytes': 0}
                    details = {'ordered_paths': paths, 'whole_output_consumed': True,
                               'segments': [{k: v for k, v in value.items() if k != 'value'} for value in segments] + [segment],
                               'protected_live_sources': live_proofs, 'segment': segment}
                    match_name = 'authenticated_terminal_empty_continuity'
                    scope = 'Exact prior source segments consume all stdout; final literal Continuity operand contributes zero bytes. No synthetic printed marker or attention claim.'
                else:
                    static, static_proof = literal.static_sources(root, host, source_zip, hashes, history,
                        ['Continuity.md'], execution['request_wall_unix_s'], candidate_receipts)
                    details = prefix_attribution(static['Continuity.md'], raw, find_prefix_roots(argv))
                    match_name = 'complete_initial_continuity_prefix_from_literal_cat'
                    scope = 'All protected initial bytes are attributed to literal cat. The remaining bytes are unattributed; no whole-current-file identity, listing snapshot, no-mutation or attention claim.'
                proof = {'item_id': item['id'], 'match': match_name, 'input_sha256': hashes['Continuity.md'],
                         **details, 'executor_provenance': read['provenance'], 'execution': execution,
                         'static_sources': static_proof, 'source_contract': boundary,
                         'inputs': candidate_receipts, 'scope': scope}
                audit['proofs'].append(proof)
                audit['startup']['Continuity.md'].append({'item_id': item['id'], 'match': match_name,
                    'input_sha256': hashes['Continuity.md'], 'segment': details['segment'],
                    'executor_provenance': read['provenance'], 'proof_index': len(audit['proofs']) - 1})
            except (ValueError, KeyError, TypeError, OSError, UnicodeError, zipfile.BadZipFile) as error:
                audit['errors'].append(str(item.get('id')) + ': ' + str(error))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, zipfile.BadZipFile) as error:
        audit['errors'].append(str(error))
    return audit
