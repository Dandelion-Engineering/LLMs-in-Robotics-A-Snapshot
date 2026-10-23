"""Finite prepared text segments; no JavaScript evaluation or gap reconstruction.

This module parses bytes and source framing only. The caller must authenticate
the outer interval, every child process and complete stdout, then match every
returned prefix and trusted initial-file segment. No parser result is admission.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import zipfile

import raw_tool_result_reads as raw
from empty_startup_reads import require
from literal_read_segments import literal_cat_paths
from retained_reads import sha

MAX_BYTES = 4 * 1024 * 1024
MAX_SCRIPT_BYTES = 16384
MAX_CHILDREN = 8
SOURCE_HASHES = {
    '/io-repair/PREPARED_STARTUP_SEGMENTS_V1.md': '39287ceb982a9a2077863c5107c15bc4744e1fc544aafd9d32f014cc25e5dd7f',
    '/io-repair/native-output-source-002/codex-rs__core__src__tools__code_mode__mod.rs': '13b5bda6e93a65fe999a3f07b3c5ee4a05850bfca57e4090876d70b310d8ba9e',
    '/io-repair/native-output-source-003/codex-rs__utils__output-truncation__src__lib.rs': 'e2e23cc1b3c9153bef0855cb3c7c91c68e6e43117647c3e97feefda92026a38e',
    '/io-repair/native-output-source-003/codex-rs__utils__string__src__truncate.rs': 'd5755286344f10d10b4bd9f93bb3bff6f1b85270a15df378254051b147ad38ad',
    '/io-repair/native-output-source-003/codex-rs__core__src__unified_exec__mod.rs': 'b44a827c63f6906f4b76e69f2095cb207b4989e67a8a5fcd521a1150443ad240',
    '/io-repair/native-output-source-003/codex-rs__code-mode-protocol__src__description.rs': '2dbd58a3210c05fab918dca4426c3947a6732ec48e80a05344d432e314546c95',
    '/io-repair/native-output-source-003/codex-rs__code-mode-protocol__src__runtime.rs': 'a64d60e9e7d2c1812ace64825d4009f12d1d4ef572c5ba04602acc44658e1094',
    '/io-repair/native-output-source-003/codex-rs__core__src__tools__code_mode__response_adapter.rs': '702b85e1a50baf24470f5018c355f27d7630134a2a9ea7b9a938c292702568f7',
}
TOKEN = re.compile(r'''\s+|"(?:[^"\\\r\n]|\\.)*"|'(?:[^'\\\r\n]|\\.)*'|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|\.\.\.|=>|\+\+|[{}()\[\].,;:=<]''')
RESERVED = {'tools', 'text', 'console', 'await', 'let', 'const', 'Promise', 'for', 'true', 'false'}
WARNING = re.compile(rb'Warning: truncated output \(original token count: ([1-9][0-9]*)\)\nTotal output lines: ([1-9][0-9]*)\n\n')
MARKER = re.compile('…([0-9]+) (?:tokens|chars) truncated…'.encode())
OMITTED = re.compile(r'\.\.\. [0-9]+ bytes omitted \.\.\.')


class Wrapper(raw.Parser):
    def __init__(self, script):
        require(isinstance(script, str) and 0 < len(script.encode()) <= MAX_SCRIPT_BYTES,
                'Invalid/bounded wrapper required')
        self.pragma = {}
        if script.startswith('// @exec:'):
            line, sep, script = script.partition('\n')
            self.pragma = raw.json_value(line[len('// @exec:'):].strip())
            require(sep and isinstance(self.pragma, dict)
                    and set(self.pragma) <= {'yield_time_ms', 'max_output_tokens'}
                    and all(type(v) is int and 0 < v < 2**63 for v in self.pragma.values()),
                    'Unknown native pragma')
        self.items, self.pos = [], 0
        cursor = 0
        while cursor < len(script):
            match = TOKEN.match(script, cursor)
            require(match is not None, 'Unsupported JS token')
            token = match.group(); cursor = match.end()
            if token.isspace():
                continue
            if token[:1] in ('"', "'"):
                values = raw.tokens(token)
                require(len(values) == 1, 'Invalid string token')
                self.items.append(values[0])
            elif token.isdigit():
                self.items.append(('integer', int(token)))
            elif re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', token):
                self.items.append(('name', token))
            else:
                self.items.append((token, token))

    def sequence(self, *values):
        for value in values:
            self.pop(value)

    def identifier(self):
        kind, name = self.pop()
        require(kind == 'name' and name not in RESERVED, 'Invalid binding identifier')
        return name

    def invocation(self, awaited=True):
        if awaited:
            self.pop('await')
        self.sequence('tools', '.', 'exec_command', '(', '{')
        options = {}
        while not self.peek('}'):
            kind, key = self.pop()
            require(kind in ('name', 'string') and key in raw.OPTIONS and key not in options,
                    'Unknown/duplicate command option')
            self.pop(':'); kind, value = self.pop()
            require(kind in ('string', 'integer') or kind == 'name' and value in ('true', 'false'),
                    'Nonliteral command option')
            options[key] = (value == 'true') if kind == 'name' else value
            if not self.peek(','):
                break
            self.pop(','); require(not self.peek('}'), 'Trailing option comma')
        self.sequence('}', ')')
        argv = ['/usr/bin/bash', '-lc', options.get('cmd')]
        raw.command_options(options, argv)
        require(literal_cat_paths(argv), 'Child is not an approved pure literal cat')
        return options

    def print_object(self, counter, result, indexed=False):
        self.sequence('text', '(', '{')
        kind, key = self.pop()
        require(kind in ('name', 'string') and key in ('index', 'part'), 'Unknown index property')
        self.sequence(':', counter, ',', '...', result)
        if indexed:
            self.sequence('[', counter, ']')
        self.sequence('}', ')')
        return key


def parse_wrapper(script):
    p = Wrapper(script)
    output_only, index_key, emission = False, None, 'single'
    if p.peek('const') or p.peek('let'):
        p.pop(); variable = p.identifier(); p.pop('=')
        parallel = (p.items[p.pos:p.pos + 2] == [('name', 'await'), ('name', 'Promise')])
        if parallel:
            p.sequence('await', 'Promise', '.', 'allSettled', '(', '[')
            children = [p.invocation(False)]
            while p.peek(','):
                p.pop(','); children.append(p.invocation(False))
                require(len(children) <= MAX_CHILDREN, 'Too many children')
            p.sequence(']', ')'); p.semi()
            if p.peek('for'):
                p.sequence('for', '(', 'let'); counter = p.identifier()
                require(counter != variable, 'Loop aliases result array')
                p.sequence('='); require(p.pop() == ('integer', 0), 'Nonzero loop start')
                p.sequence(';', counter, '<', variable, '.', 'length', ';', counter, '++', ')')
                index_key = p.print_object(counter, variable, True)
                emission = 'indexed_loop'
            else:
                p.sequence(variable, '.', 'forEach', '(')
                if p.peek('text'):
                    p.pop('text'); emission = 'forEach_text'
                else:
                    p.pop('('); result = p.identifier(); p.pop(','); counter = p.identifier()
                    require(len({variable, result, counter}) == 3, 'Callback alias')
                    p.sequence(')', '=>')
                    index_key = p.print_object(counter, result)
                    emission = 'indexed_forEach'
                p.pop(')')
            p.semi()
        else:
            children = [p.invocation()]; p.semi(); p.sequence('text', '(', variable)
            if p.peek('.'):
                p.sequence('.', 'output'); output_only = True
            p.pop(')'); p.semi()
    else:
        p.sequence('text', '(')
        output_only = p.peek('(')
        if output_only:
            p.pop('(')
        children = [p.invocation()]
        if output_only:
            p.sequence(')', '.', 'output')
        p.pop(')'); p.semi()
    require(p.pos == len(p.items), 'Additional JS statement/expression')
    # Defaults do not distinguish two otherwise identical native command calls.
    signatures = [json.dumps({**{'workdir': '/workspace', 'shell': '/usr/bin/bash',
                                'login': True, 'tty': False}, **c}, sort_keys=True) for c in children]
    require(len(signatures) == len(set(signatures)), 'Ambiguous duplicate child command')
    return {'schema': 'prepared-wrapper-1', 'mode': 'single' if emission == 'single' else 'parallel',
            'children': children, 'output_only': output_only, 'emission': emission,
            'index_key': index_key, 'max_output_tokens': p.pragma.get('max_output_tokens', 10000),
            'pragma': p.pragma}


def _utf8(value):
    try:
        return value.encode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise ValueError('Invalid Unicode scalar') from exc


class Result:
    """Small JSON cursor with a prefix-only string decoder; no closing repair."""
    def __init__(self, data, base=0):
        self.data, self.pos, self.base = data, 0, base

    def whitespace(self):
        while self.pos < len(self.data) and self.data[self.pos] in b' \r\n\t':
            self.pos += 1

    def symbol(self, value):
        self.whitespace(); encoded = value.encode()
        require(self.data[self.pos:self.pos + len(encoded)] == encoded, 'Incomplete/unknown JSON envelope')
        self.pos += len(encoded)

    def scalar(self):
        self.whitespace()
        text = self.data[self.pos:].decode('utf-8')
        try:
            value, end = json.JSONDecoder(object_pairs_hook=raw.unique_object,
                                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite'))).raw_decode(text)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ValueError('Incomplete JSON metadata') from exc
        require(not isinstance(value, (dict, list)), 'Non-scalar JSON metadata')
        self.pos += len(_utf8(text[:end]))
        return value

    def key(self):
        value = self.scalar(); require(isinstance(value, str), 'Non-string JSON key')
        self.symbol(':'); return value

    def string(self, prefix=False):
        self.symbol('"'); start = self.pos
        output = bytearray(); fragment = b''
        while self.pos < len(self.data):
            before = self.pos; char = self.data[self.pos]
            if char == 34:
                end = self.pos; self.pos += 1
                return bytes(output), start, end, True, fragment
            if char == 92:
                remaining = self.data[self.pos:]
                if len(remaining) < 2:
                    fragment = remaining; break
                esc = remaining[1]
                simple = {34: b'"', 92: b'\\', 47: b'/', 98: b'\b', 102: b'\f', 110: b'\n', 114: b'\r', 116: b'\t'}
                if esc in simple:
                    unit, count = simple[esc], 2
                else:
                    require(esc == 117, 'Invalid JSON escape')
                    if len(remaining) < 6:
                        require(re.fullmatch(rb'\\u[0-9a-fA-F]*', remaining), 'Malformed partial Unicode escape')
                        fragment = remaining; break
                    require(re.fullmatch(rb'[0-9a-fA-F]{4}', remaining[2:6]), 'Malformed Unicode escape')
                    scalar = int(remaining[2:6], 16); count = 6
                    if 0xD800 <= scalar <= 0xDBFF:
                        if len(remaining) < 12:
                            tail = remaining[6:]
                            require(not tail or tail == b'\\' or re.fullmatch(rb'\\u[0-9a-fA-F]{0,3}', tail),
                                    'Malformed partial surrogate pair')
                            digits = tail[2:].lower()
                            require(not digits or digits.startswith(b'd')
                                    and (len(digits) < 2 or digits[1:2] in (b'c', b'd', b'e', b'f')),
                                    'Invalid partial low surrogate')
                            fragment = remaining; break
                        require(re.fullmatch(rb'\\u[0-9a-fA-F]{4}', remaining[6:12]), 'Invalid surrogate pair')
                        low = int(remaining[8:12], 16)
                        require(0xDC00 <= low <= 0xDFFF, 'Invalid low surrogate')
                        scalar = 0x10000 + ((scalar - 0xD800) << 10) + low - 0xDC00; count = 12
                    else:
                        require(not 0xDC00 <= scalar <= 0xDFFF, 'Unpaired low surrogate')
                    unit = _utf8(chr(scalar))
                output.extend(unit); self.pos += count
            else:
                require(char >= 32, 'Unescaped JSON control')
                # Find an uninterrupted UTF8 run; decoding checks all scalar boundaries.
                end = self.pos + 1
                while end < len(self.data) and self.data[end] not in (34, 92) and self.data[end] >= 32:
                    end += 1
                unit = self.data[self.pos:end]; unit.decode('utf-8', errors='strict')
                output.extend(unit); self.pos = end
            require(self.pos > before, 'JSON decoder did not advance')
        require(prefix, 'Unclosed output string')
        return bytes(output), start, self.pos, False, fragment


def _native(cursor, command_index, recipe, prefix):
    parallel = recipe['mode'] == 'parallel'
    if parallel:
        cursor.symbol('{')
        if recipe['index_key'] is not None:
            require(cursor.key() == recipe['index_key'], 'Missing/reordered index key')
            index = cursor.scalar()
            require(type(index) is int and index == command_index, 'Wrong/noninteger result index')
            cursor.symbol(',')
        require(cursor.key() == 'status' and cursor.scalar() == 'fulfilled', 'Child is not fulfilled')
        cursor.symbol(','); require(cursor.key() == 'value', 'Unknown allSettled fields')
    cursor.symbol('{'); metadata = {}
    key = cursor.key()
    if key == 'chunk_id':
        value = cursor.scalar()
        require(isinstance(value, str) and re.fullmatch('[A-Za-z0-9_-]+', value), 'Invalid chunk identity')
        metadata[key] = value; cursor.symbol(','); key = cursor.key()
    require(key == 'wall_time_seconds', 'Missing/reordered native timing')
    value = cursor.scalar()
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'Invalid native timing')
    metadata[key] = value; cursor.symbol(',')
    require(cursor.key() == 'exit_code', 'Missing terminal exit')
    value = cursor.scalar(); require(type(value) is int and value == 0, 'Nonzero/noninteger exit')
    metadata['exit_code'] = value; cursor.symbol(','); key = cursor.key()
    if key == 'original_token_count':
        value = cursor.scalar(); require(type(value) is int and value >= 0, 'Invalid native count')
        metadata[key] = value; cursor.symbol(','); key = cursor.key()
    require(key == 'output', 'Unknown/duplicate/unfinished native result')
    decoded, start, end, closed, fragment = cursor.string(prefix)
    if closed:
        cursor.symbol('}')
        if parallel:
            cursor.symbol('}')
    return {'command_index': command_index, 'stdout_prefix': decoded, 'complete': closed,
            'metadata': metadata, 'encoded_start_byte': cursor.base + start,
            'encoded_end_byte': cursor.base + end, 'decoded_bytes': len(decoded),
            'encoding': 'json_string', 'uncredited_trailing_escape': fragment,
            '_encoded_source': cursor.data[start:end]}


def parse_prepared_result(body, recipe):
    require(isinstance(recipe, dict) and recipe.get('schema') == 'prepared-wrapper-1', 'Unknown wrapper recipe')
    if isinstance(body, list):
        require(0 < len(body) <= MAX_CHILDREN + 1 and all(isinstance(x, dict)
                and set(x) == {'type', 'text'} and x['type'] == 'input_text'
                and isinstance(x['text'], str) for x in body), 'Unknown/nontext result items')
        text = ''.join(x['text'] for x in body)
    else:
        require(isinstance(body, str), 'Unknown prepared result body'); text = body
    data = _utf8(text); require(0 < len(data) <= MAX_BYTES, 'Prepared output bound')
    header = raw.CODE_HEADER.match(text); require(header is not None, 'Incomplete/unknown native status header')
    start = len(_utf8(text[:header.end()])); payload = data[start:]
    warning = WARNING.match(payload); truncation = None
    if warning:
        total, lines = map(int, warning.groups()); budget = recipe['max_output_tokens'] * 4
        rest = payload[warning.end():]; matches = list(MARKER.finditer(rest))
        require(len(matches) == 1, 'Missing/ambiguous omission boundary')
        marker = matches[0]; head, tail = rest[:marker.start()], rest[marker.end():]
        require(marker.group() == ('…' + marker.group(1).decode() + ' tokens truncated…').encode(), 'Wrong marker unit')
        require(total > recipe['max_output_tokens'] and int(marker.group(1)) == total - recipe['max_output_tokens'],
                'Truncation count/budget mismatch')
        half = budget // 2
        require(max(0, half - 3) <= len(head) <= half
                and max(0, budget - half - 3) <= len(tail) <= budget - half,
                'Head/tail differ from UTF8 native budget')
        head.decode('utf-8', errors='strict'); tail.decode('utf-8', errors='strict')
        require(not raw.BAD.search((head + tail).decode()) and not OMITTED.search((head + tail).decode()),
                'Redacted/nested truncation/error output')
        start += warning.end(); payload = head
        truncation = {'original_approximate_tokens': total, 'original_lines': lines,
                      'budget_tokens': recipe['max_output_tokens'], 'budget_bytes': budget,
                      'head_start_byte': start, 'head_end_byte': start + len(head),
                      'head_sha256': sha(head), 'marker_start_byte': start + len(head),
                      'marker_bytes': len(marker.group()), 'marker_sha256': sha(marker.group()),
                      'suffix_bytes': len(tail), 'suffix_sha256': sha(tail),
                      'suffix_consumed_as_evidence': False}
    else:
        require(not raw.BAD.search(payload.decode()) and not MARKER.search(payload)
                and not OMITTED.search(payload.decode()), 'Redacted/truncated/error output')
    if recipe['output_only']:
        require(recipe['mode'] == 'single', 'Parallel output-only unsupported')
        records = [{'command_index': 0, 'stdout_prefix': payload, 'complete': truncation is None,
                    'metadata': {}, 'encoded_start_byte': start, 'encoded_end_byte': start + len(payload),
                    'decoded_bytes': len(payload), 'encoding': 'plain', 'uncredited_trailing_escape': b'',
                    '_encoded_source': payload}]
    else:
        cursor = Result(payload, start)
        records = [_native(cursor, i, recipe, truncation is not None)
                   for i in range(1 if truncation is not None else len(recipe['children']))]
        if truncation is None:
            cursor.whitespace(); require(cursor.pos == len(payload), 'Extra/unconsumed result bytes')
    # Empty children still require the caller's authenticated complete stream.
    # They supply no nonempty fixed-file evidence; do not discard their identity.
    return {'schema': 'prepared-result-segments-1', 'mode': 'prefix' if truncation else 'complete',
            'records': records, 'body_sha256': sha(data), 'body_bytes': len(data), 'truncation': truncation}


def encoded_span(record, start, end):
    """Map a complete decoded UTF8 range to actually retained encoded bytes."""
    require(type(start) is int and type(end) is int and 0 <= start <= end <= record['decoded_bytes'],
            'Decoded range exceeds observed prefix')
    decoded = record['stdout_prefix']; decoded[:start].decode(); decoded[:end].decode()
    if record['encoding'] == 'plain':
        return {'start_byte': record['encoded_start_byte'] + start,
                'end_byte': record['encoded_start_byte'] + end}
    # Decode bounded prefixes only at exact JSON-unit boundaries. This avoids a
    # per-character proof table and never credits half of a Unicode/escape unit.
    encoded = record['_encoded_source']; boundaries = {0: 0}; pos = count = 0
    while pos < len(encoded):
        if encoded[pos] != 92:
            length = 1
            while pos + length < len(encoded) and encoded[pos + length] & 0xC0 == 0x80:
                length += 1
            value = encoded[pos:pos + length]; value.decode()
        else:
            length = 2
            if encoded[pos + 1] == 117:
                length = 6
                if 0xD800 <= int(encoded[pos + 2:pos + 6], 16) <= 0xDBFF:
                    length = 12
            value = _utf8(json.loads(b'"' + encoded[pos:pos + length] + b'"'))
        count += len(value); pos += length
        if count in (start, end):
            boundaries[count] = pos
        if count >= end:
            break
    require(start in boundaries and end in boundaries, 'Range cuts a JSON escape/scalar')
    return {'start_byte': record['encoded_start_byte'] + boundaries[start],
            'end_byte': record['encoded_start_byte'] + boundaries[end]}


def validate_prefix_rounding(record, authenticated_stdout, truncation):
    """Prove any shortened head is actual UTF8 rounding, never missing ASCII.

    The caller must invoke this on every record before crediting a file. A next
    scalar from the already authenticated complete stream checks framing only;
    it is not returned as delivered content or included in the observed prefix.
    """
    require(isinstance(authenticated_stdout, bytes), 'Authenticated stdout bytes required')
    prefix = record['stdout_prefix']
    require(authenticated_stdout.startswith(prefix), 'Observed prefix differs from authenticated stdout')
    if truncation is None:
        return {'validated': True, 'mode': 'not_truncated'}
    budget = truncation['budget_bytes']
    observed = truncation['head_end_byte'] - truncation['head_start_byte']
    require(type(budget) is int and budget > 0 and type(observed) is int,
            'Malformed native head budget')
    nominal = budget // 2; residual = nominal - observed
    proof = {'validated': True, 'mode': 'exact_head_budget', 'nominal_head_bytes': nominal,
             'observed_head_bytes': observed, 'remaining_budget_bytes': residual}
    if residual == 0:
        return proof
    require(0 < residual <= 3 and record['complete'] is False
            and record['uncredited_trailing_escape'] == b''
            and record['encoded_end_byte'] == truncation['head_end_byte'],
            'Shortened head lacks an inside-output UTF8 cut')
    remaining = authenticated_stdout[len(prefix):]
    require(remaining, 'No authenticated scalar beyond shortened head')
    next_scalar = _utf8(remaining.decode('utf-8', errors='strict')[0])
    # JSON.stringify emits valid non-ASCII scalars literally; ASCII quotes,
    # controls and backslashes instead begin ASCII escapes and always fit.
    require(len(next_scalar) > residual and len(next_scalar) > 1,
            'Next authenticated scalar fits; native head was shortened')
    require(record['encoding'] in ('plain', 'json_string'), 'Unknown source encoding')
    proof.update(mode='authenticated_next_scalar', next_scalar_utf8_bytes=len(next_scalar),
                 next_scalar_sha256=sha(next_scalar), continuation_used_for_framing_only=True)
    return proof


def source_contract(source_zip):
    bindings = raw.source_contract(source_zip)
    expected = dict(SOURCE_HASHES)
    campaign = Path(__file__).parents[1]
    for path in (Path(__file__),):
        expected['/campaign-002/' + path.relative_to(campaign).as_posix()] = sha(path.read_bytes())
    with zipfile.ZipFile(source_zip) as archive:
        for suffix, digest in expected.items():
            names = [name for name in archive.namelist() if name.endswith(suffix)]
            require(len(names) == 1 and sha(archive.read(names[0])) == digest,
                    'Prepared-segment source absent/changed/ambiguous: ' + suffix)
            bindings.append({'path': names[0], 'sha256': digest})
    return bindings
