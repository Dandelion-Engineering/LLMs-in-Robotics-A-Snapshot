"""Adversarial finite parsing only; no native/model/queue execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import prepared_result_segments as parser


HEADER = 'Script completed\nWall time 0.100 seconds (code-mode 0.09 seconds; overhead 0.01 seconds)\nOutput:\n'


def native(output, **changes):
    value = {'chunk_id': 'c123', 'wall_time_seconds': .1, 'exit_code': 0,
             'original_token_count': (len(output.encode()) + 3) // 4, 'output': output}
    value.update(changes)
    return value


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def settled(output, index=None, key='index'):
    value = {} if index is None else {key: index}
    value.update(status='fulfilled', value=native(output))
    return value


def wrapper(count=2, emission='plain', budget=None):
    commands = ['cat ' + ' '.join(['Tasks.md'] * (i + 1)) for i in range(count)]
    call = 'const r=await Promise.allSettled([' + ','.join(
        'tools.exec_command(' + encode({'cmd': c}) + ')' for c in commands) + ']);'
    emit = {'plain': 'r.forEach(text);',
            'index': 'r.forEach((value,i)=>text({index:i,...value}));',
            'part': 'for(let i=0;i<r.length;i++)text({part:i,...r[i]});'}[emission]
    pragma = '' if budget is None else '// @exec: ' + encode({'max_output_tokens': budget}) + '\n'
    return pragma + call + emit


def truncate(text, tokens):
    data = text.encode(); half = tokens * 2
    left = data[:half].decode('utf-8', errors='ignore').encode()
    right = data[-half:].decode('utf-8', errors='ignore').encode() if half else b''
    count = (len(data) + 3) // 4
    marker = f'…{count-tokens} tokens truncated…'.encode()
    head = f'Warning: truncated output (original token count: {count})\nTotal output lines: {len(text.splitlines())}\n\n'.encode()
    return (head + left + marker + right).decode()


class PreparedResultTests(unittest.TestCase):
    def test_single_all_existing_text_forms(self):
        forms = [('text(await tools.exec_command({cmd:"cat Tasks.md"}))', False),
                 ('text((await tools.exec_command({cmd:"cat Tasks.md"})).output)', True),
                 ('const r=await tools.exec_command({cmd:"cat Tasks.md"});text(r)', False),
                 ('let r=await tools.exec_command({"cmd":"cat Tasks.md"});text(r.output);', True)]
        for script, output_only in forms:
            with self.subTest(script=script):
                recipe = parser.parse_wrapper(script)
                body = 'fixed file\n' if output_only else encode(native('fixed file\n'))
                value = parser.parse_prepared_result(HEADER + body, recipe)
                self.assertEqual(value['records'][0]['stdout_prefix'], b'fixed file\n')
                self.assertTrue(value['records'][0]['complete'])
                self.assertEqual(recipe['output_only'], output_only)

    def test_parallel_one_through_eight_and_all_three_emitters(self):
        for count in (1, 2, 8):
            for emission in ('plain', 'index', 'part'):
                recipe = parser.parse_wrapper(wrapper(count, emission))
                values = [settled('payload' + str(i), None if emission == 'plain' else i,
                                  'part' if emission == 'part' else 'index') for i in range(count)]
                body = [{'type': 'input_text', 'text': HEADER}] + [
                    {'type': 'input_text', 'text': encode(v)} for v in values]
                result = parser.parse_prepared_result(body, recipe)
                self.assertEqual([r['stdout_prefix'] for r in result['records']],
                                 [('payload' + str(i)).encode() for i in range(count)])
                self.assertEqual([r['command_index'] for r in result['records']], list(range(count)))

    def test_exact_observed_indexed_templates_and_optional_semicolons(self):
        one = 'const results = await Promise.allSettled([tools.exec_command({cmd:"cat Tasks.md"}),tools.exec_command({cmd:"cat Robot.md"})]); results.forEach((r,i)=>text({index:i,...r}));'
        two = 'let r=await Promise.allSettled([tools.exec_command({cmd:"cat Tasks.md"}),tools.exec_command({cmd:"cat Robot.md"})]);for(let i=0;i<r.length;i++)text({part:i,...r[i]});'
        self.assertEqual(parser.parse_wrapper(one)['emission'], 'indexed_forEach')
        self.assertEqual(parser.parse_wrapper(two)['emission'], 'indexed_loop')
        self.assertEqual(parser.parse_wrapper(two.replace(';for', ' for').rstrip(';'))['index_key'], 'part')

    def test_shorthand_both_indexed_emitters_and_consistent_renaming(self):
        for emitter in ('index', 'part'):
            for counter in ('i', 'slot', 'position7'):
                script = wrapper(2, emitter).replace('index:i', 'i').replace('part:i', 'i')
                if counter != 'i':
                    import re
                    script = re.sub(r'\bi\b', counter, script)
                with self.subTest(emitter=emitter, counter=counter):
                    recipe = parser.parse_wrapper(script)
                    self.assertEqual(recipe['index_key'], counter)
                    body = HEADER + '\n'.join(encode(settled('file' + str(i), i, counter)) for i in range(2))
                    parsed = parser.parse_prepared_result(body, recipe)
                    self.assertEqual(parsed['mode'], 'complete')
                    self.assertEqual([r['stdout_prefix'] for r in parsed['records']], [b'file0', b'file1'])

    def test_shorthand_exact_smoke023_loop_and_observed_prefix(self):
        script = ('const results = await Promise.allSettled([\n'
                  '  tools.exec_command({cmd:"cat Tasks.md Robot.md Tools.md",workdir:"/workspace",max_output_tokens:15000}),\n'
                  '  tools.exec_command({cmd:"cat live/activation.json live/state.json Continuity.md",workdir:"/workspace",max_output_tokens:8500})\n'
                  ']);\nfor (let i=0;i<results.length;i++) text({i,...results[i]});\n')
        recipe = parser.parse_wrapper(script)
        self.assertEqual(recipe['index_key'], 'i')
        fixed = 'Tasks complete\nRobot complete\n'
        first = fixed + 'long tools\n' * 3000
        body = encode(settled(first, 0, 'i')) + '\n' + encode(settled('live\n' * 7000, 1, 'i'))
        parsed = parser.parse_prepared_result(HEADER + truncate(body, 10000), recipe)
        record, = parsed['records']
        self.assertEqual(parsed['mode'], 'prefix')
        self.assertFalse(record['complete'])
        self.assertTrue(record['stdout_prefix'].startswith(fixed.encode()))
        self.assertTrue(first.encode().startswith(record['stdout_prefix']))
        self.assertFalse(parsed['truncation']['suffix_consumed_as_evidence'])
        self.assertLess(parser.encoded_span(record, 0, len(fixed.encode()))['end_byte'],
                        parsed['truncation']['marker_start_byte'])
        self.assertTrue(parser.validate_prefix_rounding(record, first.encode(), parsed['truncation'])['validated'])
        with self.assertRaises(ValueError):
            parser.encoded_span(record, 0, len(first.encode()))

    def test_shorthand_requires_exact_counter_and_single_original_spread(self):
        for emitter, spread in (('index', 'value'), ('part', 'r[i]')):
            script = wrapper(2, emitter).replace('index:i', 'i').replace('part:i', 'i')
            mutations = [script.replace('{i,', '{other,'), script.replace('{i,', '{"i",'),
                         script.replace('{i,', '{[i],'), script.replace('{i,', '{i:0,'),
                         script.replace('{i,', '{i:other,'), script.replace('{i,', '{i,i,'),
                         script.replace('{i,', '{i,extra:1,'),
                         script.replace('...' + spread, '...other'),
                         script.replace('...' + spread, '...' + spread + ',...other'),
                         script.replace('...' + spread, '...' + spread + ',i'),
                         script.replace('{i,...' + spread + '}', '{...' + spread + ',i}')]
            for candidate in mutations:
                with self.subTest(script=candidate), self.assertRaises(ValueError):
                    parser.parse_wrapper(candidate)

    def test_shorthand_rejects_colliding_result_or_native_field_names(self):
        import re
        for emitter in ('index', 'part'):
            for name in ('status', 'value', 'reason', 'chunk_id', 'wall_time_seconds',
                         'exit_code', 'original_token_count', 'output', 'session_id'):
                script = wrapper(2, emitter).replace('index:i', 'i').replace('part:i', 'i')
                script = re.sub(r'\bi\b', name, script)
                with self.subTest(emitter=emitter, counter=name), self.assertRaises(ValueError):
                    parser.parse_wrapper(script)

    def test_shorthand_actual_result_key_index_and_members_remain_exact(self):
        recipe = parser.parse_wrapper(wrapper(2, 'part').replace('part:i', 'i'))
        first, second = encode(settled('a', 0, 'i')), encode(settled('b', 1, 'i'))
        valid = first + '\n' + second
        mutations = [valid.replace('"i":0', '"index":0'), valid.replace('"i":0,', ''),
                     valid.replace('"i":0', '"i":false'), valid.replace('"i":0', '"i":1'),
                     valid.replace('"i":0', '"i":0,"i":0'),
                     valid.replace('"i":0', '"i":0,"extra":1'),
                     valid.replace('"i":0,"status":"fulfilled"', '"status":"fulfilled","i":0'),
                     second + '\n' + first, valid + '\n' + second]
        for body in mutations:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parser.parse_prepared_result(HEADER + body, recipe)

    def test_shorthand_truncated_prefix_rejects_wrong_key_and_index(self):
        recipe = parser.parse_wrapper(wrapper(1, 'index', 200).replace('index:i', 'i'))
        body = truncate(encode(settled('T' * 6000, 0, 'i')), 200)
        self.assertEqual(parser.parse_prepared_result(HEADER + body, recipe)['mode'], 'prefix')
        for old, new in (('"i":0', '"j":0'), ('"i":0', '"i":1'), ('"i":0', '"i":false')):
            # Equal-size wrong-key/index cases reach the native metadata check;
            # a different-length mutation must also fail the unchanged budget.
            with self.subTest(new=new), self.assertRaises(ValueError):
                parser.parse_prepared_result(HEADER + body.replace(old, new), recipe)

    def test_literal_options_and_pragma(self):
        script = '// @exec: {"max_output_tokens":2000,"yield_time_ms":50}\ntext(await tools.exec_command({cmd:"cat Tasks.md",workdir:"/workspace",shell:"/usr/bin/bash",login:true,tty:false,max_output_tokens:123,yield_time_ms:10}))'
        recipe = parser.parse_wrapper(script)
        self.assertEqual(recipe['max_output_tokens'], 2000)
        self.assertEqual(recipe['children'][0]['max_output_tokens'], 123)

    def test_wrapper_rejects_unbounded_or_unknown_javascript(self):
        baseline = wrapper()
        cases = [wrapper(9), baseline.replace('allSettled', 'all'),
                 baseline.replace('r.forEach(text)', 'r.forEach(console.log)'),
                 baseline.replace('r.forEach(text)', 'r.forEach(x=>text(x))'),
                 baseline + 'text("extra")', baseline.replace('const r', 'const text'),
                 baseline.replace('tools.exec_command', 'alias.exec_command'),
                 'text(await tools.exec_command({cmd:`cat Tasks.md`}))',
                 baseline.replace('"cmd":', '["cmd"]:'),
                 'text(await tools.exec_command({cmd:"cat Tasks.md",cmd:"cat Robot.md"}))',
                 baseline.replace('"cmd":', '...other,"cmd":'),
                 '// @exec: {"max_output_tokens":true}\n' + baseline,
                 '// @exec: {"unknown":1}\n' + baseline,
                 ' ' * 16385 + baseline, 'const r=await Promise.allSettled([]);r.forEach(text);']
        for script in cases:
            with self.subTest(script=script[:90]), self.assertRaises(ValueError):
                parser.parse_wrapper(script)

    def test_wrong_indexed_templates_fail(self):
        baseline = wrapper(emission='index'); loop = wrapper(emission='part')
        cases = [baseline.replace('value,i', 'value,value'),
                 baseline.replace('index:i', 'index:0'),
                 baseline.replace('index:i', 'unknown:other'),
                 baseline.replace('...value', '...r'),
                 baseline.replace('{index:i,...value}', '{...value,index:i}'),
                 baseline.replace('text({', 'console.log({'),
                 baseline.replace('=>text', '=>{text').replace('}));', '});});'),
                 loop.replace('i=0', 'i=1'), loop.replace('i<r.length', 'i<2'),
                 loop.replace('i++', '++i'), loop.replace('...r[i]', '...r[0]'),
                 loop.replace('part:i', 'part:r'), loop.replace('let i', 'let r'),
                 loop.replace('i<r.length', 'i<=r.length')]
        for script in cases:
            with self.subTest(script=script), self.assertRaises(ValueError):
                parser.parse_wrapper(script)

    def test_literal_index_labels_both_emitters_quotes_and_renaming(self):
        import re
        for emitter in ('index', 'part'):
            for key in ('source', 'unknown', '_slot', 'position7', 'toJSON', 'r', 'a' * 128):
                for label in (key, encode(key)):
                    script = wrapper(2, emitter).replace(emitter + ':i', label + ':i')
                    script = re.sub(r'\bi\b', 'counter7', script)
                    with self.subTest(emitter=emitter, label=label):
                        recipe = parser.parse_wrapper(script)
                        self.assertEqual(recipe['index_key'], key)
                        result = parser.parse_prepared_result(HEADER + '\n'.join(
                            encode(settled('file' + str(i), i, key)) for i in range(2)), recipe)
                        self.assertEqual([r['stdout_prefix'] for r in result['records']], [b'file0', b'file1'])

    def test_decoded_literal_labels_and_all_collision_classes(self):
        template = wrapper(1, 'index')
        recipe = parser.parse_wrapper(template.replace('index:i', r'"\u0073ource":i'))
        self.assertEqual(recipe['index_key'], 'source')
        good = encode(settled('complete', 0, 'source'))
        self.assertEqual(parser.parse_prepared_result(HEADER + good, recipe)['records'][0]['stdout_prefix'], b'complete')
        labels = ['status', 'value', 'reason', 'chunk_id', 'wall_time_seconds', 'exit_code',
                  'original_token_count', 'output', 'session_id', '__proto__', 'prototype',
                  'constructor', 'tools', 'text', 'console', 'await', 'const', 'Promise',
                  'for', 'true', 'false', 'return', 'class', 'new', 'null', 'yield',
                  'a' * 129, '0', 'name-with-hyphen', '', 'naïve']
        for key in labels:
            with self.subTest(key=key), self.assertRaises(ValueError):
                parser.parse_wrapper(template.replace('index:i', encode(key) + ':i'))
        for label in (r'"\u005f\u005fproto__"', r'"\u0073tatus"', r'"\u0030"'):
            with self.subTest(label=label), self.assertRaises(ValueError):
                parser.parse_wrapper(template.replace('index:i', label + ':i'))

    def test_literal_label_never_weakens_counter_or_spread(self):
        template = wrapper(2, 'part').replace('part:i', 'source:i')
        variants = [template.replace('source:i', value) for value in (
            'source:j', 'source:0', 'source:true', 'source:"i"', 'source:r', '["source"]:i',
            'source:i,extra:i', 'source:i,source:i', 'get source()', 'source=i')]
        variants += [template.replace('...r[i]', '...r[0]'), template.replace('...r[i]', '...other[i]'),
                     template.replace('{source:i,...r[i]}', '{...r[i],source:i}'),
                     template + 'text("extra");']
        for script in variants:
            with self.subTest(script=script), self.assertRaises(ValueError):
                parser.parse_wrapper(script)

    def test_literal_label_actual_record_key_integer_and_order_are_exact(self):
        recipe = parser.parse_wrapper(wrapper(2, 'part').replace('part:i', 'source:i'))
        first, second = encode(settled('a', 0, 'source')), encode(settled('b', 1, 'source'))
        good = first + '\n' + second
        cases = [good.replace('"source":0', replacement, 1) for replacement in (
            '"other":0', '"source":false', '"source":0.0', '"source":"0"', '"source":1',
            '"source":0,"source":0', r'"source":0,"\u0073ource":0')]
        cases += [good.replace('"source":1', '"source":0'),
                  good.replace('"source":0,"status":"fulfilled"', '"status":"fulfilled","source":0'),
                  good.replace('"status":"fulfilled"', '"status":"fulfilled","source":0', 1)]
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ValueError):
                parser.parse_prepared_result(HEADER + body, recipe)
        escaped = good.replace('"source":', r'"\u0073ource":')
        self.assertEqual(len(parser.parse_prepared_result(HEADER + escaped, recipe)['records']), 2)

    def test_source_label_prefix_keeps_complete_file_and_utf8_limits(self):
        script = wrapper(2, 'part', 200).replace('part:i', 'source:i')
        recipe = parser.parse_wrapper(script)
        text = 'TASKS complete\nROBOT complete\n' + 'λ雪 tools\n' * 2000
        body = encode(settled(text, 0, 'source')) + '\n' + encode(settled('live' * 3000, 1, 'source'))
        parsed = parser.parse_prepared_result(HEADER + truncate(body, 200), recipe)
        record, = parsed['records']
        self.assertEqual(record['command_index'], 0)
        self.assertFalse(record['complete'])
        self.assertTrue(record['stdout_prefix'].startswith(b'TASKS complete\nROBOT complete\n'))
        self.assertTrue(parser.validate_prefix_rounding(record, text.encode(), parsed['truncation'])['validated'])
        self.assertFalse(parsed['truncation']['suffix_consumed_as_evidence'])
        with self.assertRaises(ValueError):
            parser.encoded_span(record, 0, len(text.encode()))

    def test_shorthand_excludes_prototype_keywords_and_length(self):
        import re
        for key in ('__proto__', 'prototype', 'constructor', 'return', 'class', 'a' * 129):
            script = re.sub(r'\bi\b', key, wrapper(1, 'part').replace('part:i', 'i'))
            with self.subTest(key=key), self.assertRaises(ValueError):
                parser.parse_wrapper(script)

    def test_duplicate_commands_and_unqualified_execution_fail(self):
        duplicate = 'const r=await Promise.allSettled([tools.exec_command({cmd:"cat Tasks.md"}),tools.exec_command({cmd:"cat Tasks.md",workdir:"/workspace"})]);r.forEach(text)'
        with self.assertRaises(ValueError): parser.parse_wrapper(duplicate)
        for options in ({'cmd': 'cat /etc/passwd'}, {'cmd': 'cat Tasks.md; true'},
                        {'cmd': 'cat Tasks.md', 'tty': True}, {'cmd': 'cat Tasks.md', 'login': False},
                        {'cmd': 'cat Tasks.md', 'shell': 'sh'}, {'cmd': 'cat Tasks.md', 'workdir': '/'},
                        {'cmd': 'cat Tasks.md', 'max_output_tokens': False}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                parser.parse_wrapper('text(await tools.exec_command(' + encode(options) + '))')

    def test_result_rejects_metadata_mutations(self):
        recipe = parser.parse_wrapper(wrapper(1))
        for changes in ({'exit_code': False}, {'exit_code': 1}, {'session_id': 4},
                        {'wall_time_seconds': -1}, {'wall_time_seconds': True},
                        {'wall_time_seconds': float('nan')}, {'unknown': 1},
                        {'original_token_count': False}, {'chunk_id': ''}):
            value = settled('complete'); value['value'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parser.parse_prepared_result(HEADER + encode(value), recipe)
        for field in ('wall_time_seconds', 'exit_code', 'output'):
            value = settled('complete'); value['value'].pop(field)
            with self.assertRaises(ValueError): parser.parse_prepared_result(HEADER + encode(value), recipe)

    def test_result_rejects_duplicate_unknown_reordered_or_extra_records(self):
        recipe = parser.parse_wrapper(wrapper(1, 'index')); value = encode(settled('complete', 0))
        cases = [value.replace('"index":0', '"index":false'), value.replace('"index":0', '"index":1'),
                 value.replace('"index":0', '"index":-1'), value.replace('"index":0,', ''),
                 value.replace('"index":0', '"index":0,"index":0'),
                 value.replace('"fulfilled"', '"rejected"'), value + value,
                 value.replace('"status":"fulfilled","value":', '"other":"fulfilled","value":'),
                 value.replace('"exit_code":0', '"exit_code":0,"exit_code":0')]
        for body in cases:
            with self.subTest(body=body[:100]), self.assertRaises(ValueError):
                parser.parse_prepared_result(HEADER + body, recipe)
        recipe = parser.parse_wrapper(wrapper(2, 'index'))
        with self.assertRaises(ValueError):
            parser.parse_prepared_result(HEADER + encode(settled('b', 1)) + encode(settled('a', 0)), recipe)

    def test_rejects_nontext_bad_headers_redaction_and_output_cap(self):
        recipe = parser.parse_wrapper('text((await tools.exec_command({cmd:"cat Tasks.md"})).output)')
        cases = [HEADER.replace('completed', 'failed') + 'x', HEADER.replace('completed', 'running with cell ID 4') + 'x',
                 'x', HEADER + '[REDACTED_SECRET]', HEADER + '... 20 bytes omitted ...',
                 HEADER + '…2 tokens truncated…', HEADER + 'x' * parser.MAX_BYTES,
                 [{'type': 'input_image', 'text': 'x'}], [{'type': 'input_text', 'text': HEADER + 'x', 'extra': 1}]]
        for body in cases:
            with self.assertRaises(ValueError): parser.parse_prepared_result(body, recipe)

    def test_truncated_valid_json_is_never_parsed_as_complete(self):
        recipe = parser.parse_wrapper(wrapper(2, 'part', 100))
        first = encode(settled('A' * 3000, 0, 'part'))
        second = encode(settled('B' * 3000, 1, 'part'))
        truncated = truncate(first + '\n' + second, 100)
        spliced = truncated.split('\n\n', 1)[1]
        fabricated = json.loads(spliced)
        self.assertIn('tokens truncated', fabricated['value']['output'])
        parsed = parser.parse_prepared_result(HEADER + truncated, recipe)
        self.assertEqual(parsed['mode'], 'prefix')
        record, = parsed['records']
        self.assertFalse(record['complete']); self.assertEqual(record['command_index'], 0)
        self.assertTrue(record['stdout_prefix']); self.assertEqual(set(record['stdout_prefix']), {65})
        self.assertFalse(parsed['truncation']['suffix_consumed_as_evidence'])
        self.assertNotIn(b'B', record['stdout_prefix'])

    def test_native_prefix_budget_marker_and_count_mutations(self):
        recipe = parser.parse_wrapper(wrapper(1, 'index', 100))
        text = truncate(encode(settled('a' * 3000, 0)), 100)
        mutations = [text.replace('tokens truncated', 'chars truncated'),
                     text.replace('Total output lines: 1', 'Total output lines: 0'),
                     text.replace('…', '..', 1), text + 'x',
                     text.replace('"index":0', '"index":1'),
                     text.replace('"exit_code":0', '"exit_code":1'),
                     text.replace('output (original token count:', 'output (original count:'),
                     text.replace('a', 'aa', 1)]
        for body in mutations:
            with self.subTest(body=body[:90]), self.assertRaises(ValueError):
                parser.parse_prepared_result(HEADER + body, recipe)

    def test_marker_collision_is_rejected(self):
        recipe = parser.parse_wrapper(wrapper(1, 'index', 150))
        for literal in ('…1 tokens truncated…', 'Warning: truncated output', '[REDACTED_X]'):
            text = truncate(encode(settled(literal + 'a' * 3000, 0)), 150)
            with self.assertRaises(ValueError): parser.parse_prepared_result(HEADER + text, recipe)

    def test_plain_output_prefix_and_unicode_boundary(self):
        script = '// @exec: {"max_output_tokens":3}\ntext((await tools.exec_command({cmd:"cat Tasks.md"})).output)'
        recipe = parser.parse_wrapper(script)
        body = truncate('a😀b😀c😀d😀e', 3)
        record, = parser.parse_prepared_result(HEADER + body, recipe)['records']
        self.assertEqual(record['stdout_prefix'], 'a😀b'.encode())
        self.assertEqual(parser.encoded_span(record, 1, 5), {'start_byte': record['encoded_start_byte'] + 1,
                                                           'end_byte': record['encoded_start_byte'] + 5})
        with self.assertRaises(UnicodeError): parser.encoded_span(record, 1, 2)

    def test_json_escapes_and_exact_encoded_file_span(self):
        recipe = parser.parse_wrapper('text(await tools.exec_command({cmd:"cat Tasks.md"}))')
        value = native('line\n😀quote"slash\\end')
        body = HEADER + json.dumps(value, ensure_ascii=True, separators=(',', ':'))
        record, = parser.parse_prepared_result(body, recipe)['records']
        start = len('line\n'.encode()); end = start + len('😀'.encode())
        span = parser.encoded_span(record, start, end)
        self.assertEqual(body.encode()[span['start_byte']:span['end_byte']], b'\\ud83d\\ude00')
        self.assertEqual(record['stdout_prefix'], value['output'].encode())
        self.assertEqual(parser.encoded_span(record, 0, 0)['start_byte'], record['encoded_start_byte'])

    def test_partial_escape_units_are_uncredited_not_repaired(self):
        for partial in (b'\\', b'\\u', b'\\u1', b'\\u12', b'\\u123', b'\\ud83d', b'\\ud83d\\', b'\\ud83d\\u', b'\\ud83d\\ude'):
            cursor = parser.Result(b'"prefix' + partial)
            decoded, start, end, closed, fragment = cursor.string(True)
            self.assertEqual(decoded, b'prefix'); self.assertFalse(closed)
            self.assertEqual(fragment, partial); self.assertEqual(cursor.data[start:end], b'prefix')

    def test_malformed_escapes_and_surrogates_fail(self):
        for bad in (b'\\x', b'\\uQ', b'\\u000Q', b'\\udc00', b'\\ud800X', b'\\ud800\\u0041', b'\\ud800\\uXXXX', b'\x01'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parser.Result(b'"prefix' + bad).string(True)

    def test_truncation_inside_metadata_fails(self):
        recipe = parser.parse_wrapper(wrapper(1, 'index', 5))
        with self.assertRaises(ValueError):
            parser.parse_prepared_result(HEADER + truncate(encode(settled('a' * 1000, 0)), 5), recipe)

    def test_complete_first_child_before_truncation_does_not_infer_second(self):
        recipe = parser.parse_wrapper(wrapper(2, 'index', 300))
        output = encode(settled('first complete', 0)) + '\n' + encode(settled('Z' * 4000, 1))
        result = parser.parse_prepared_result(HEADER + truncate(output, 300), recipe)
        record, = result['records']
        self.assertTrue(record['complete']); self.assertEqual(record['stdout_prefix'], b'first complete')
        self.assertEqual(result['mode'], 'prefix')

    def test_complete_empty_non_target_child_retains_its_ordered_identity(self):
        recipe = parser.parse_wrapper(wrapper(2, 'index'))
        body = HEADER + encode(settled('whole fixed file', 0)) + '\n' + encode(settled('', 1))
        result = parser.parse_prepared_result(body, recipe)
        self.assertEqual(result['records'][1]['command_index'], 1)
        self.assertEqual(result['records'][1]['stdout_prefix'], b'')
        self.assertTrue(result['records'][1]['complete'])

    def test_multiline_outputs_preserve_complete_item_boundaries(self):
        recipe = parser.parse_wrapper(wrapper(2, 'part'))
        values = [settled('Tasks line1\nline2\n', 0, 'part'), settled('Robot\nTools\n', 1, 'part')]
        items = [{'type': 'input_text', 'text': HEADER}] + [
            {'type': 'input_text', 'text': encode(value)} for value in values]
        result = parser.parse_prepared_result(items, recipe)
        flat = ''.join(item['text'] for item in items).encode()
        for record, expected in zip(result['records'], ('Tasks line1\nline2\n', 'Robot\nTools\n')):
            self.assertEqual(record['stdout_prefix'], expected.encode())
            span = parser.encoded_span(record, 0, len(expected.encode()))
            self.assertEqual(json.loads(b'"' + flat[span['start_byte']:span['end_byte']] + b'"'), expected)

    def test_incomplete_output_closing_envelope_is_not_completed(self):
        recipe = parser.parse_wrapper(wrapper(1, 'index'))
        value = encode(settled('file', 0))
        for count in (1, 2, 3):
            with self.assertRaises(ValueError): parser.parse_prepared_result(HEADER + value[:-count], recipe)

    def test_prefix_rejects_determinably_invalid_partial_low_surrogate(self):
        for fragment in (b'\\ud800\\u0', b'\\ud800\\ud8', b'\\ud800\\uda'):
            with self.assertRaises(ValueError): parser.Result(b'"prefix' + fragment).string(True)
        self.assertEqual(parser.Result(b'"prefix\\ud800\\ud').string(True)[0], b'prefix')

    def test_native_utf8_rounding_does_not_allow_arbitrary_missing_head_bytes(self):
        recipe = parser.parse_wrapper('// @exec: {"max_output_tokens":3}\ntext((await tools.exec_command({cmd:"cat Tasks.md"})).output)')
        truncated = truncate('a😀😀😀😀😀', 3)
        record = parser.parse_prepared_result(HEADER + truncated, recipe)['records'][0]
        self.assertEqual(record['stdout_prefix'], 'a😀'.encode())
        # At most three bytes of a four-byte scalar can be lost at the cut.
        bad = truncated.replace('a😀', 'a', 1)
        with self.assertRaises(ValueError): parser.parse_prepared_result(HEADER + bad, recipe)

    def test_shortened_head_requires_authenticated_next_scalar(self):
        recipe = parser.parse_wrapper('// @exec: {"max_output_tokens":3}\ntext((await tools.exec_command({cmd:"cat Tasks.md"})).output)')
        stdout = 'a😀😀😀😀😀'.encode()
        result = parser.parse_prepared_result(HEADER + truncate(stdout.decode(), 3), recipe)
        record = result['records'][0]
        proof = parser.validate_prefix_rounding(record, stdout, result['truncation'])
        self.assertEqual(proof['mode'], 'authenticated_next_scalar')
        self.assertEqual(proof['remaining_budget_bytes'], 1)
        self.assertEqual(record['stdout_prefix'], 'a😀'.encode())
        for wrong in (record['stdout_prefix'] + b'ASCII', record['stdout_prefix'], b'other'):
            with self.assertRaises(ValueError): parser.validate_prefix_rounding(record, wrong, result['truncation'])

    def test_forged_short_ascii_head_and_closed_record_fail_rounding(self):
        recipe = parser.parse_wrapper('// @exec: {"max_output_tokens":3}\ntext((await tools.exec_command({cmd:"cat Tasks.md"})).output)')
        stdout = 'abcdefghijklmnopqrstuv'.encode()
        text = truncate(stdout.decode(), 3).replace('abcdef', 'abcde', 1)
        result = parser.parse_prepared_result(HEADER + text, recipe)
        record = result['records'][0]
        with self.assertRaises(ValueError): parser.validate_prefix_rounding(record, stdout, result['truncation'])
        for changes in ({'complete': True}, {'uncredited_trailing_escape': b'\\'},
                        {'encoded_end_byte': record['encoded_end_byte'] - 1}):
            changed = {**record, **changes}
            with self.assertRaises(ValueError):
                parser.validate_prefix_rounding(changed, record['stdout_prefix'] + '😀'.encode(), result['truncation'])

    def test_rounding_complete_and_exact_head_receipts_do_not_add_bytes(self):
        recipe = parser.parse_wrapper('text((await tools.exec_command({cmd:"cat Tasks.md"})).output)')
        result = parser.parse_prepared_result(HEADER + 'hello', recipe)
        record = result['records'][0]
        self.assertEqual(parser.validate_prefix_rounding(record, b'hello', None),
                         {'validated': True, 'mode': 'not_truncated'})
        recipe = parser.parse_wrapper('// @exec: {"max_output_tokens":3}\ntext((await tools.exec_command({cmd:"cat Tasks.md"})).output)')
        result = parser.parse_prepared_result(HEADER + truncate('abcdefghijklmnopqrstuv', 3), recipe)
        proof = parser.validate_prefix_rounding(result['records'][0], b'abcdefghijklmnopqrstuv', result['truncation'])
        self.assertEqual(proof['mode'], 'exact_head_budget')
        self.assertEqual(result['records'][0]['stdout_prefix'], b'abcdef')

    def test_json_prefix_rounding_uses_next_scalar_without_crediting_it(self):
        recipe = parser.parse_wrapper('// @exec: {"max_output_tokens":100}\ntext(await tools.exec_command({cmd:"cat Tasks.md"}))')
        prototype = encode(native('A' * 3000, original_token_count=900))
        source_start = prototype.index('"output":"') + len('"output":"')
        stdout = 'A' * (200 - source_start - 1) + '😀' + 'Z' * 3000
        text = encode(native(stdout, original_token_count=900))
        result = parser.parse_prepared_result(HEADER + truncate(text, 100), recipe)
        record = result['records'][0]
        proof = parser.validate_prefix_rounding(record, stdout.encode(), result['truncation'])
        self.assertEqual(proof['remaining_budget_bytes'], 1)
        self.assertEqual(proof['next_scalar_utf8_bytes'], 4)
        self.assertNotIn('😀'.encode(), record['stdout_prefix'])

    def test_source_archive_absent_changed_duplicate_rejected(self):
        campaign = Path(parser.__file__).parents[1]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'source.zip'
            entries = {}
            for suffix in {**parser.raw.SOURCE_HASHES, **parser.SOURCE_HASHES}:
                base = campaign.parent if suffix.startswith('/isolation-session-9/') else campaign
                prefix = 'integration' if base == campaign.parent else 'integration/campaign-002'
                entries[prefix + suffix] = (base / suffix.lstrip('/')).read_bytes()
            for source in (Path(parser.__file__), Path(parser.raw.__file__), campaign / 'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md'):
                entries['integration/campaign-002/' + source.relative_to(campaign).as_posix()] = source.read_bytes()
            def write(items):
                with zipfile.ZipFile(path, 'w') as archive:
                    for name, data in items.items(): archive.writestr(name, data)
            write(entries); self.assertGreater(len(parser.source_contract(path)), 10)
            key = next(k for k in entries if k.endswith('codex-rs__utils__string__src__truncate.rs'))
            missing = dict(entries); missing.pop(key); write(missing)
            with self.assertRaises(ValueError): parser.source_contract(path)
            changed = dict(entries); changed[key] += b'\n'; write(changed)
            with self.assertRaises(ValueError): parser.source_contract(path)
            ambiguous = dict(entries); ambiguous['other/' + key] = entries[key]; write(ambiguous)
            with self.assertRaises(ValueError): parser.source_contract(path)


if __name__ == '__main__':
    unittest.main()
