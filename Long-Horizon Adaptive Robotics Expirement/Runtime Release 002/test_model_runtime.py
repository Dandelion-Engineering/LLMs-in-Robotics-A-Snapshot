"""Adapter boundary tests; no server, weights, GPU, or network are used."""
import json
import unittest
from unittest.mock import MagicMock

from model_runtime import LocalModel,ModelConfig,gpu_buffer_report


class RuntimeTests(unittest.TestCase):
    def test_gpu_report_requires_all_allocation_roles_and_retains_scope(self):
        log='load_tensors: CUDA0 model buffer size = 8161.75 MiB\nllama_kv_cache: CUDA0 KV buffer size = 2560.00 MiB\nsched_reserve: CUDA0 compute buffer size = 306.75 MiB'
        value=gpu_buffer_report(log,12*1024**3)
        self.assertFalse(value['allocation_level_hard_cap'])
        self.assertEqual(value['reported_total_bytes'],int(11028.5*1024**2))
        with self.assertRaises(RuntimeError):gpu_buffer_report(log,10*1024**3)
        with self.assertRaises(RuntimeError):gpu_buffer_report('CUDA0 model buffer size = 100 MiB',12*1024**3)

    def model(self,count=20,actual=None):
        model=LocalModel(ModelConfig(context_tokens=64,max_output_tokens=16))
        model.process=MagicMock();model.process.poll.return_value=None
        model._manifest={'installed_files':[{'path':'server.exe','sha256':'test-only'}],'server_relative_path':'server.exe'}
        actual=count if actual is None else actual
        def request(path,payload,timeout):
            if path=='/apply-template':return {'prompt':'a complete templated prompt'}
            if path=='/tokenize':return {'tokens':list(range(count))}
            return {'choices':[{'message':{'content':json.dumps({'action':'hold'})},'finish_reason':'stop'}],
                    'usage':{'prompt_tokens':actual,'completion_tokens':8,'total_tokens':actual+8}}
        model._request=MagicMock(side_effect=request)
        return model

    def test_preflight_is_counted_and_no_text_is_truncated(self):
        model=self.model()
        reply=model.complete([{'role':'user','content':'hold'}],{'type':'object'},seed=8)
        self.assertEqual(reply['prompt_preflight_tokens'],20)
        self.assertFalse(reply['context_truncated'])
        self.assertEqual(reply['reserved_output_tokens'],16)
        self.assertEqual([call.args[0] for call in model._request.call_args_list],['/apply-template','/tokenize','/v1/chat/completions'])
        self.assertEqual(model._request.call_args_list[0].args[1],model._request.call_args_list[2].args[1])

    def test_oversized_context_never_starts_generation(self):
        model=self.model(count=50)
        with self.assertRaisesRegex(ValueError,'no text was truncated or generated'):
            model.complete([{'role':'user','content':'hold'}],{'type':'object'})
        self.assertEqual(model._request.call_count,2)

    def test_prompt_token_mismatch_withholds_action(self):
        model=self.model(actual=19)
        with self.assertRaisesRegex(RuntimeError,'response withheld'):
            model.complete([{'role':'user','content':'hold'}],{'type':'object'})

    def test_timeout_stops_owned_server(self):
        model=self.model();process=model.process
        model._request.side_effect=TimeoutError('timeout')
        with self.assertRaisesRegex(TimeoutError,'owned server stopped'):
            model.complete([{'role':'user','content':'hold'}],{'type':'object'})
        process.terminate.assert_called_once()
        self.assertIsNone(model.process)

    def test_busy_slot_timeout_does_not_kill_another_request(self):
        model=self.model();process=model.process
        model._lock.acquire()
        try:
            with self.assertRaisesRegex(TimeoutError,'waiting for the request slot'):
                model.complete([{'role':'user','content':'hold'}],{'type':'object'},timeout_s=.001)
        finally:model._lock.release()
        process.terminate.assert_not_called()


if __name__=='__main__':unittest.main()
