"""Source-bound synthetic captures; no model, native process or simulation."""
import base64
import copy
import json
from pathlib import Path
import shlex
import tempfile
import unittest
import zipfile

import prepared_startup_segments as proof
import prepared_result_segments as parser
import raw_tool_result_reads as raw
from retained_reads import canonical, process_reads, sha


class PreparedStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'stage'; (self.root / 'client').mkdir(parents=True)
        self.archive = Path(self.temp.name) / 'code.zip'
        self.static = {'Tasks.md': b'TASKS\n', 'Robot.md': b'ROBOT\n',
                       'RobotAgentPrompt.md': b'PROMPT\n', 'Tools.md': b'TOOLS ' * 300 + b'\n'}
        self.hashes = {name: sha(value) for name, value in self.static.items()}
        self.write('runtime-input-hashes.json', self.hashes)
        self.write('client/launch.json', {'experimental_raw_events_requested': True})
        self.write('client/preflight.json', {'experimental_raw_events_requested': True,
            'experimental_raw_events_thread_start_accepted': True, 'preflight_passed': True, 'thread_id': 'thread-1'})
        self.make_archive()
        self.configure(['cat Tasks.md Robot.md Tools.md'])

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def make_archive(self):
        campaign = Path(__file__).resolve().parents[1]
        entries = {}
        for name in ('assessment', 'io-repair/native-output-source-002', 'io-repair/native-output-source-003'):
            for p in (campaign / name).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:
                    entries['integration/campaign-002/' + p.relative_to(campaign).as_posix()] = p.read_bytes()
        for suffix in dict.fromkeys((*raw.SOURCE_HASHES, *parser.SOURCE_HASHES)):
            base = campaign.parent if suffix.startswith('/isolation-session-9/') else campaign
            prefix = 'integration' if base == campaign.parent else 'integration/campaign-002'
            entries[prefix + suffix] = (base / suffix.lstrip('/')).read_bytes()
        entries['integration/campaign-002/' + proof.METHOD] = (campaign / proof.METHOD).read_bytes()
        with zipfile.ZipFile(self.archive, 'w') as z:
            for name, data in entries.items(): z.writestr(name, data)

    @staticmethod
    def event(method, item, ms):
        return {'kind': 'notification', 'method': method, 'emittedAtMs': ms,
                'params': {'threadId': 'thread-1', 'turnId': 'turn-1', 'item': item}}

    def configure(self, commands, *, reverse=False, parallel=False, prefix=False):
        for path in self.root.glob('executor-*-capture.jsonl'): path.unlink()
        self.commands = commands; self.rows = []; self.ends = []; self.starts = []; self.stdout = []
        self.options = [{'cmd': command, 'workdir': '/workspace'} for command in commands]
        for n, command in enumerate(commands):
            output = b''.join(self.static[name] for name in command.split()[1:]); self.stdout.append(output)
            ident, pid = f'read-{n}', f'process-{n}'
            item = {'id': ident, 'type': 'commandExecution', 'command': shlex.join(['/usr/bin/bash', '-lc', command]),
                    'exitCode': 0, 'aggregatedOutput': output.decode()[-3:]}
            self.starts.append(self.event('item/started', copy.deepcopy(item), 100000))
            self.ends.append(self.event('item/completed', item, 110000))
            rows = []
            def append(kind, message=None, **extra):
                row = {'schema': 'campaign002-executor-capture-1', 'connection_id': str(n),
                       'kind': kind, 'wall_unix_s': 100.0 + len(rows) / 10, **extra}
                if message is not None: row.update(message=message, blobs=[])
                rows.append(row); return len(rows)
            def send(message):
                seq = append('response', message)
                if message.get('method') == 'process/output':
                    data = base64.b64decode(message['params']['chunk'])
                    rows[-1]['blobs'] = [{'path': ['params', 'chunk'], 'raw_bytes': len(data),
                        'retained_bytes': len(data), 'raw_sha256': sha(data), 'retained_sha256': sha(data)}]
                append('delivered', response_sequence=seq)
            append('open')
            append('request', {'id': n + 1, 'method': 'process/start', 'params': {'processId': pid,
                'argv': ['/usr/bin/bash', '-lc', command], 'arg0': None, 'cwd': 'file:///workspace',
                'tty': False, 'pipeStdin': False, 'metadata': {'toolCallId': ident}, 'env': {'LANG': 'C.UTF-8'},
                'envPolicy': {'inherit': 'none', 'ignoreDefaultExcludes': False, 'includeOnly': [], 'set': {}}}})
            send({'id': n + 1, 'result': {'processId': pid}})
            send({'method': 'process/output', 'params': {'processId': pid, 'seq': 1, 'stream': 'stdout',
                                                       'chunk': base64.b64encode(output).decode()}})
            send({'method': 'process/exited', 'params': {'processId': pid, 'seq': 2, 'exitCode': 0, 'sandboxDenied': False}})
            send({'method': 'process/closed', 'params': {'processId': pid, 'seq': 3}})
            append('closed', failures=[]); self.rows.append(rows)
        self.parallel = parallel or len(commands) > 1
        script = ('const results=await Promise.allSettled([' + ','.join('tools.exec_command(' + json.dumps(x) + ')' for x in self.options)
                  + ']);results.forEach(text);' if self.parallel else 'text(await tools.exec_command(' + json.dumps(self.options[0]) + '));')
        if prefix: script = '// @exec: {"max_output_tokens":100}\n' + script
        self.call = self.event('rawResponseItem/completed', {'type': 'custom_tool_call', 'call_id': 'outer-1', 'name': 'exec', 'input': script}, 99000)
        texts = []
        for output in self.stdout:
            value = {'chunk_id': 'chunk', 'wall_time_seconds': .1, 'exit_code': 0, 'original_token_count': 1, 'output': output.decode()}
            texts.append(json.dumps({'status': 'fulfilled', 'value': value} if self.parallel else value, separators=(',', ':')))
        if prefix:
            combined = '\n'.join(texts); budget = 400
            text = (f'Warning: truncated output (original token count: {(len(combined.encode()) + 3)//4})\n'
                    f'Total output lines: {len(texts)}\n\n' + combined[:budget//2]
                    + f'…{(len(combined.encode())-budget+3)//4} tokens truncated…' + combined[-budget//2:])
            texts = [text]
        body = [{'type': 'input_text', 'text': 'Script completed\nWall time 0.1 seconds\nOutput:\n'}]
        body.extend({'type': 'input_text', 'text': text} for text in texts)
        self.output = self.event('rawResponseItem/completed', {'type': 'custom_tool_call_output', 'call_id': 'outer-1', 'output': body}, 111000)
        self.events = [{'kind': 'request', 'method': 'thread/start', 'params': {'experimentalRawEvents': True}},
                       self.call, *self.starts, *(reversed(self.ends) if reverse else self.ends), self.output]
        self.save()

    def save(self):
        for n, rows in enumerate(self.rows):
            previous = None
            for i, row in enumerate(rows, 1):
                row.pop('record_sha256', None); row.update(sequence=i, previous_sha256=previous)
                if 'message' in row:
                    digest = sha(canonical(row['message'])); row.update(original_message_sha256=digest, retained_message_sha256=digest)
                previous = sha(canonical(row)); row['record_sha256'] = previous
            (self.root / f'executor-{n}-capture.jsonl').write_bytes(b''.join(canonical(x) + b'\n' for x in rows))
        (self.root / 'client/events.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in self.events), encoding='utf-8')

    def segments(self, index=0):
        offset, result = 0, []
        for name in self.commands[index].split()[1:]:
            value = self.static[name]; result.append({'path': name, 'start_byte': offset, 'end_byte': offset + len(value),
                                                     'bytes': len(value), 'sha256': sha(value)})
            offset += len(value)
        return result

    def prove(self, index=0, segments=None):
        self.save(); reads, _ = process_reads(self.root, self.events)
        return proof.prove_prepared_segments(self.root, self.ends[index], self.events, reads,
                                              self.archive, self.segments(index) if segments is None else segments)

    def rejected(self, **kwargs):
        with self.assertRaises((ValueError, KeyError, TypeError, OSError)): self.prove(**kwargs)

    def test_single_complete_does_not_repair_display(self):
        result = self.prove(); self.assertEqual(result['covered_segment_indices'], [0, 1, 2])
        self.assertFalse(result['app_projection_equals_executor']); json.dumps(result)
        self.assertGreaterEqual(result['evidence_complete_upper_wall_unix_s'], 111.001)

    def test_one_and_eight_parallel_children_with_reverse_completion(self):
        commands = ['cat Tasks.md', 'cat Robot.md', 'cat Tools.md', 'cat RobotAgentPrompt.md',
                    'cat Tasks.md Robot.md', 'cat Robot.md Tools.md', 'cat Tools.md Tasks.md', 'cat Tasks.md Tools.md']
        for count in (1, 8):
            with self.subTest(count=count):
                self.configure(commands[:count], parallel=True, reverse=True)
                result = self.prove(count-1); self.assertEqual(len(result['children']), count)
                self.assertEqual([c['native_tool_call_id'] for c in result['children']], [f'read-{n}' for n in range(count)])

    def test_prefix_credits_complete_files_only(self):
        self.configure(['cat Tasks.md Robot.md Tools.md'], prefix=True)
        result = self.prove(); self.assertEqual(result['covered_segment_indices'], [0, 1])
        self.assertEqual(result['match'], 'complete_fixed_file_in_prepared_result_prefix'); json.dumps(result)

    def test_short_ascii_head_cannot_impersonate_utf8_budget_rounding(self):
        self.configure(['cat Tasks.md Robot.md Tools.md'], prefix=True)
        item=self.output['params']['item']['output'][1]
        cut=item['text'].index('…')
        # Prefix still matches stdout, but its next ASCII byte would fit budget.
        item['text']=item['text'][:cut-1]+item['text'][cut:]
        self.rejected()

    def test_prefix_cannot_credit_later_child(self):
        self.configure(['cat Tasks.md Robot.md Tools.md', 'cat Robot.md'], prefix=True)
        self.rejected(index=1)

    def test_later_unresolved_raw_call_is_retained_without_poisoning_selected_pair(self):
        later = copy.deepcopy(self.call); later['params']['item']['call_id'] = 'later'; later['emittedAtMs'] = 112000
        self.events.append(later); self.assertEqual(self.prove()['call_id'], 'outer-1')
        self.events.insert(1, self.events.pop()); self.rejected()

    def test_duplicate_reordered_or_foreign_raw_identity(self):
        baseline = copy.deepcopy(self.events)
        for kind in ('duplicate', 'foreign', 'orphan', 'time'):
            self.events = copy.deepcopy(baseline); self.call = self.events[1]; self.output = self.events[-1]; self.ends=[self.events[-2]]
            if kind == 'duplicate': self.events.append(copy.deepcopy(self.output))
            elif kind == 'foreign': self.output['params']['turnId'] = 'other'
            elif kind == 'orphan': self.output['params']['item']['call_id'] = 'other'
            else: self.call['emittedAtMs'] = False
            with self.subTest(kind=kind): self.rejected()

    def test_overlapping_or_yielded_earlier_cell_rejected(self):
        a=copy.deepcopy(self.call); b=copy.deepcopy(self.output)
        for e in (a,b): e['params']['item']['call_id']='other'
        a['emittedAtMs']=97000; b['emittedAtMs']=98000
        b['params']['item']['output']='Script running with cell ID 1\nOutput:\n'
        self.events[1:1]=[a,b]; self.rejected()
        del self.events[1:3];a['emittedAtMs']=100000;b['emittedAtMs']=110000
        self.events[2:2]=[a,b];self.rejected()

    def test_hidden_capture_or_native_invocation_rejected(self):
        row=copy.deepcopy(self.rows[0][1]);row['wall_unix_s']=100.15
        row['message']['id']=99;row['message']['params'].update(processId='hidden',metadata={'toolCallId':'hidden'})
        self.rows[0].insert(2,row)
        for x in self.rows[0]:
            if x['kind']=='delivered': x['response_sequence']+=1
        self.rejected()

    def test_all_children_must_succeed_with_real_empty_stderr(self):
        self.configure(['cat Tasks.md','cat Robot.md'])
        self.rows[1][6]['message']['params']['exitCode']=1;self.rejected()
        self.rows[1][6]['message']['params']['exitCode']=0
        self.rows[1][4]['message']['params']['stream']='stderr';self.rejected()

    def test_environment_source_hash_and_metadata_changes_rejected(self):
        self.rows[0][1]['message']['params']['env']['BASH_ENV']='notes/inject';self.rejected()
        self.rows[0][1]['message']['params']['env'].pop('BASH_ENV')
        self.hashes['Tasks.md']='0'*64;self.write('runtime-input-hashes.json',self.hashes);self.rejected()

    def test_wrong_segment_hash_boundaries_and_empty_fixed_file_rejected(self):
        for key,value in [('sha256','0'*64),('start_byte',1),('end_byte',0),('bytes',True)]:
            segments=self.segments();segments[0][key]=value
            with self.subTest(key=key):self.rejected(segments=segments)

    def test_swapped_child_payloads_and_duplicate_commands_rejected(self):
        self.configure(['cat Tasks.md','cat Robot.md']);body=self.output['params']['item']['output']
        body[1],body[2]=body[2],body[1];self.rejected()
        self.configure(['cat Tasks.md','cat Tasks.md']);self.rejected()

    def test_missing_source_gate_rejects_before_evidence(self):
        with zipfile.ZipFile(self.archive) as z: data={n:z.read(n) for n in z.namelist() if not n.endswith('/prepared_startup_segments.py')}
        with zipfile.ZipFile(self.archive,'w') as z:
            for name,b in data.items():z.writestr(name,b)
        self.rejected()

    def test_forged_supplied_read_mapping_rejected(self):
        reads,_=process_reads(self.root,self.events);reads['read-0']['stdout']='forged'
        with self.assertRaises(ValueError):proof.prove_prepared_segments(self.root,self.ends[0],self.events,reads,self.archive,self.segments())

    def test_both_indexed_emission_templates_preserve_input_order(self):
        for suffix,key in [('results.forEach((r,i)=>text({index:i,...r}));','index'),
                           ('for(let i=0;i<results.length;i++)text({part:i,...results[i]});','part')]:
            with self.subTest(key=key):
                self.configure(['cat Tasks.md','cat Robot.md'],reverse=True)
                self.call['params']['item']['input']=self.call['params']['item']['input'].replace('results.forEach(text);',suffix)
                body=self.output['params']['item']['output']
                for index,item in enumerate(body[1:]):
                    item['text']=json.dumps({key:index,**json.loads(item['text'])},separators=(',',':'))
                self.assertEqual(self.prove(1)['covered_segment_indices'],[0])
                body[2]['text']=body[2]['text'].replace(f'"{key}":1',f'"{key}":0')
                self.rejected(index=1)

    def test_nonfixed_continuity_and_live_segments_are_never_credited(self):
        for name in ('Continuity.md','live/state.json'):
            with self.subTest(path=name):
                self.static[name]=b'{}';self.hashes[name]=sha(b'{}');self.write('runtime-input-hashes.json',self.hashes)
                self.configure(['cat '+name]);self.rejected()

    def test_empty_non_target_child_is_authenticated_but_not_credited(self):
        self.static['Continuity.md']=b''
        self.configure(['cat Tasks.md','cat Continuity.md'])
        result=self.prove();self.assertEqual(result['covered_segment_indices'],[0])
        self.assertEqual(result['children'][1]['executor_provenance']['stdout_bytes'],0)

    def test_raw_quantization_and_late_delivery_keep_conservative_bound(self):
        self.output['emittedAtMs']=110000
        self.rows[0][-2]['wall_unix_s']=111.25
        self.rows[0][-1]['wall_unix_s']=111.3
        result=self.prove()
        self.assertEqual(result['raw_output_emitted_at_ms'],110000)
        self.assertGreaterEqual(result['evidence_complete_upper_wall_unix_s'],111.25)

    def test_unknown_native_lifecycle_and_duplicate_child_ids_rejected(self):
        self.configure(['cat Tasks.md','cat Robot.md'])
        self.events.insert(3,copy.deepcopy(self.starts[0]));self.rejected()
        self.events.pop(3)
        self.ends[1]['params']['item']['id']='read-0';self.rejected()

    def test_unknown_raw_options_and_foreign_child_context_rejected(self):
        self.call['params']['item']['unknown']=True;self.rejected()
        self.call['params']['item'].pop('unknown')
        self.starts[0]['params']['turnId']='other';self.rejected()

    def test_complete_spliced_json_does_not_credit_tools(self):
        self.configure(['cat Tasks.md Robot.md Tools.md'],prefix=True)
        body=self.output['params']['item']['output'][1]['text']
        spliced=json.loads(body.split('\n\n',1)[1])
        self.assertNotEqual(spliced['output'].encode(),self.stdout[0])
        self.assertEqual(self.prove()['covered_segment_indices'],[0,1])

    def test_complete_earlier_unrelated_result_and_future_orphan_rules(self):
        a=copy.deepcopy(self.call);b=copy.deepcopy(self.output)
        for event in (a,b):event['params']['item']['call_id']='other'
        a['emittedAtMs']=97000;b['emittedAtMs']=98000
        b['params']['item']['output']='Script completed\nWall time 0.1 seconds\nOutput:\nUnrelated'
        self.events[1:1]=[a,b];self.assertEqual(self.prove()['call_id'],'outer-1')
        self.events.append(copy.deepcopy(b));self.events[-1]['params']['item']['call_id']='orphan'
        self.events[-1]['emittedAtMs']=112000;self.rejected()


if __name__ == '__main__':
    unittest.main()
