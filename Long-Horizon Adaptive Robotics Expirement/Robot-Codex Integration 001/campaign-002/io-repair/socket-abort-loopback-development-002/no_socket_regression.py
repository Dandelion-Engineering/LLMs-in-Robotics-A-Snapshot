"""Exercise extracted original fixture call sites; no event loop or socket opens."""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

PARSER=argparse.ArgumentParser()
PARSER.add_argument('--source-dir',type=Path,required=True)
ARGS,REST=PARSER.parse_known_args()
SOURCE=ARGS.source_dir.resolve()
SPEC=importlib.util.spec_from_file_location('reviewed_loopback_fixture',SOURCE/'fixture.py')
FIXTURE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
TREE=ast.parse((SOURCE/'fixture.py').read_text(encoding='utf-8'))
RUN=next(node for node in TREE.body if isinstance(node,ast.AsyncFunctionDef) and node.name=='run_case')
PENDING=next(node for node in RUN.body if isinstance(node,ast.AsyncFunctionDef) and node.name=='observe_pending')
CASE_ERROR=next(node for node in ast.walk(RUN) if isinstance(node,ast.Expr)
    and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute)
    and node.value.func.attr=='emit' and node.value.args and isinstance(node.value.args[0],ast.Constant)
    and node.value.args[0].value=='case_error')


class LoggingRegression(unittest.TestCase):
    def setUp(self):
        self.folder=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.object(FIXTURE,'OUTPUT',self.folder))
        self.enterContext(mock.patch.object(FIXTURE.socket,'socket',side_effect=AssertionError('socket forbidden')))
        self.recorder=FIXTURE.Recorder()
        self.addCleanup(self.recorder.close)
        self.environment=dict(FIXTURE.__dict__, recorder=self.recorder,name='fixed_case',
            read_started=SimpleNamespace(set=lambda:None),state={'phase':'observation'},
            received=bytearray(),fragment_hashes=[],terminal_events=[])
        code=ast.fix_missing_locations(ast.Module(body=[PENDING],type_ignores=[]))
        exec(compile(code,str(SOURCE/'fixture.py'),'exec'),self.environment)

    def rows(self):
        self.recorder.stream.flush()
        return [json.loads(line) for line in self.recorder.path.read_text(encoding='utf-8').splitlines()]

    def observe(self, data=b'', error=None):
        class Reader:
            async def read(self,count):
                if count!=4096:raise AssertionError('read bound changed')
                if error is not None:raise error
                return data
        coroutine=self.environment['observe_pending'](Reader())
        try:
            with self.assertRaises(StopIteration) as done:
                coroutine.send(None)
            return done.exception.value
        finally:coroutine.close()

    def test_eof_keeps_outer_event_kind_and_nested_observation_kind(self):
        value=self.observe()
        row=self.rows()[-1]
        self.assertEqual(row['kind'],'receive_terminal')
        self.assertEqual(row['observation'],value)
        self.assertEqual(value['kind'],'eof')
        self.assertEqual(value['bytes'],0)
        self.assertEqual(self.environment['terminal_events'],[value])

    def test_data_retains_exact_counts_hash_and_nested_schema(self):
        value=self.observe(b'fixed synthetic bytes')
        self.assertEqual(self.rows()[-1]['observation'],value)
        self.assertEqual(value['kind'],'data')
        self.assertEqual(value['sha256'],FIXTURE.sha(b'fixed synthetic bytes'))
        self.assertEqual(bytes(self.environment['received']),b'fixed synthetic bytes')

    def test_os_error_retains_safe_metadata_without_message(self):
        value=self.observe(error=ConnectionAbortedError(1236,'PRIVATE-TEXT'))
        self.assertEqual(value['kind'],'error')
        self.assertEqual(value['error']['class'],'ConnectionAbortedError')
        self.assertEqual(self.rows()[-1]['observation'],value)
        self.assertNotIn('PRIVATE-TEXT',json.dumps(self.rows()))

    def test_cancellation_remains_distinct_from_eof(self):
        value=self.observe(error=FIXTURE.asyncio.CancelledError())
        self.assertEqual(value['kind'],'cancelled')
        self.assertEqual(value['error']['class'],'CancelledError')
        self.assertEqual(self.rows()[-1]['observation'],value)

    def test_case_error_call_site_preserves_nested_failure(self):
        observation={'kind':'setup_or_action_error','error':FIXTURE.error_metadata(TypeError('PRIVATE-TEXT')),
                     'phase':'observation'}
        self.environment['observation']=observation
        code=ast.fix_missing_locations(ast.Module(body=[CASE_ERROR],type_ignores=[]))
        exec(compile(code,str(SOURCE/'fixture.py'),'exec'),self.environment)
        self.assertEqual(self.rows()[-1]['kind'],'case_error')
        self.assertEqual(self.rows()[-1]['observation'],observation)
        self.assertNotIn('PRIVATE-TEXT',json.dumps(self.rows()))

    def test_type_error_is_finite_safe_class(self):
        value=FIXTURE.error_metadata(TypeError('PRIVATE-TEXT'))
        self.assertEqual(value,{'class':'TypeError','errno':None,'winerror':None})

    def test_every_emit_call_has_fixed_event_kind_and_no_expanded_fields(self):
        calls=[node for node in ast.walk(TREE) if isinstance(node,ast.Call)
               and isinstance(node.func,ast.Attribute) and node.func.attr=='emit']
        self.assertGreaterEqual(len(calls),15)
        for node in calls:
            self.assertEqual(len(node.args),1)
            self.assertIsInstance(node.args[0],ast.Constant)
            self.assertIs(type(node.args[0].value),str)
            self.assertTrue(all(keyword.arg is not None and keyword.arg!='kind' for keyword in node.keywords))

    def test_four_cases_and_original_bounds_unchanged(self):
        self.assertEqual(FIXTURE.CASES,('peer_graceful_send_shutdown','peer_abortive_close',
            'local_close_pending_receive','explicit_receive_task_cancel'))
        self.assertEqual((len(FIXTURE.PAYLOAD),FIXTURE.OBSERVATION_S,FIXTURE.CLEANUP_S,
                          FIXTURE.MAX_EVENT_BYTES,FIXTURE.MAX_RESULT_BYTES,FIXTURE.MAX_EVENTS),
                         (4096,5.0,2.0,512*1024,128*1024,256))


if __name__=='__main__':
    unittest.main(argv=[__file__,*REST])
