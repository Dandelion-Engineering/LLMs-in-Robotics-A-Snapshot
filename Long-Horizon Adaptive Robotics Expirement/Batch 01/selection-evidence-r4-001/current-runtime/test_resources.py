"""Mocked resource-sampler checks; no GPU query or simulator executes."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from resources import GIB,ResourceSampler,missing_process,parse_gpu_csv


def process(pid):
    if pid is None:return missing_process(None,'No process')
    return {'pid':pid,'cpu_total_s':2.,'rss_bytes':5*GIB,'peak_rss_bytes':5*GIB,
            'private_commit_bytes':3*GIB,'creation_time_100ns':123,'missing_reason':None}


class ResourceTests(unittest.TestCase):
    def test_unavailable_gpu_values_remain_null(self):
        row=parse_gpu_csv('0, Example GPU, 16384, 2048, N/A, [Not Supported]\n')[0]
        self.assertIsNone(row['utilization_gpu_percent'])
        self.assertIsNone(row['temperature_c'])
        self.assertIn('utilization_gpu_percent',row['missing_reasons'])
        self.assertEqual(row['memory_used_bytes'],2*GIB)

    def test_malformed_gpu_rows_are_not_silently_zero_filled(self):
        with self.assertRaises(ValueError):parse_gpu_csv('0,too,few\n')

    def test_cpu_rate_requires_matching_identity_and_two_samples(self):
        values=iter([2.,4.,5.])
        def reader(pid):return {**process(pid),'cpu_total_s':next(values)}
        sampler=ResourceSampler('unused',process_reader=reader)
        first=sampler._process('harness',1,1.)
        second=sampler._process('harness',1,3.)
        recycled=sampler._process('harness',2,4.)
        self.assertIsNone(first['cpu_core_equivalents'])
        self.assertEqual(second['cpu_core_equivalents'],1.)
        self.assertIsNone(recycled['cpu_core_equivalents'])

    def test_budget_checks_do_not_claim_complete_candidate_memory(self):
        sampler=ResourceSampler('unused',model_pid=2,process_reader=process,gpu_reader=lambda **kw:{'devices':None,'missing_reason':'mock unavailable'})
        sampler._started=time.perf_counter()
        sample=sampler._capture();checks=sample['budget_observations']
        self.assertTrue(checks['harness_observed_rss_exceeds_budget'])
        self.assertIsNone(checks['complete_candidate_ram_bytes'])
        self.assertIsNone(checks['candidate_gpu_usage_bytes'])
        self.assertFalse(checks['enforced'])
        self.assertIsNone(sample['energy_joules'])

    def test_model_absence_is_missing_not_zero(self):
        sampler=ResourceSampler('unused',process_reader=process,gpu_reader=lambda **kw:{'devices':None,'missing_reason':'mock unavailable'})
        sampler._started=time.perf_counter()
        sample=sampler._capture()
        self.assertIsNone(sample['model']['rss_bytes'])
        self.assertTrue(sample['model']['missing_reason'])

    def test_background_gpu_wait_never_blocks_latest_and_close_is_bounded(self):
        entered=threading.Event();release=threading.Event()
        def gpu(**kwargs):
            entered.set();release.wait(1)
            return {'devices':None,'missing_reason':'mock unavailable'}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'resources.jsonl'
            sampler=ResourceSampler(path,process_reader=process,gpu_reader=gpu,period_s=60)
            sampler.start()
            try:
                self.assertTrue(entered.wait(1))
                before=time.perf_counter();self.assertIsNone(sampler.latest())
                self.assertLess(time.perf_counter()-before,.1)
            finally:release.set();sampler.close()
            report=sampler.summary();rows=[json.loads(line) for line in path.read_text().splitlines()]
            self.assertTrue(report['sampler_stopped'])
            self.assertEqual(report['sample_count'],1)
            self.assertEqual(len(rows),1)
            self.assertIn('capture_monotonic_s',rows[0])
            self.assertIsNone(rows[0]['gpu']['devices'])


if __name__=='__main__':unittest.main()
