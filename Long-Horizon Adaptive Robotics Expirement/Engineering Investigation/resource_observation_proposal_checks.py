"""Synthetic review of an UNAPPLIED proposal; no Runtime imports or OS sampling.

Apply unified-diff hunks only to strings, then execute only the proposal's pure
policy/check/classification definitions. Original files are never written.
"""
import ast
import copy
import hashlib
import math
from pathlib import Path
import re
import sys
import unittest


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent.parent
PATCH = HERE / "resource-observation-fix.patch"
APPLIED = False


def proposed_sources():
    lines = PATCH.read_text(encoding="utf-8").splitlines(keepends=True)
    results = {}
    cursor = 0
    while cursor < len(lines):
        if not lines[cursor].startswith("--- a/"):
            raise AssertionError("Unexpected patch header")
        relative = lines[cursor][6:].strip()
        assert lines[cursor + 1] == "+++ b/" + relative + "\n"
        source = (REPOSITORY / relative).read_text(encoding="utf-8").splitlines(keepends=True)
        position = 0
        output = []
        cursor += 2
        while cursor < len(lines) and not lines[cursor].startswith("--- a/"):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[cursor])
            assert match, lines[cursor]
            origin = int(match[1]) - 1
            assert origin >= position
            output.extend(source[position:origin])
            position = origin
            cursor += 1
            old_count = new_count = 0
            while cursor < len(lines) and not lines[cursor].startswith(("@@", "--- a/")):
                line = lines[cursor]
                assert line[0] in " +-"
                if line[0] in " -":
                    assert source[position] == line[1:], (relative, position, line)
                    position += 1
                    old_count += 1
                if line[0] in " +":
                    output.append(line[1:])
                    new_count += 1
                cursor += 1
            assert old_count == int(match[2] or 1)
            assert new_count == int(match[4] or 1)
        output.extend(source[position:])
        results[Path(relative).name] = "".join(output)
    return results


class ResourceObservationProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [(HERE.parent / "Runtime" / name) for name in ("experiment.py", "test_experiment.py")]
        cls.before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        cls.sources = ({p.name: p.read_text(encoding="utf-8") for p in paths} if APPLIED else proposed_sources())
        tree = ast.parse(cls.sources["experiment.py"])
        wanted = []
        for item in tree.body:
            if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("GIB", "RESOURCE_POLICY") for t in item.targets):
                wanted.append(item)
            elif isinstance(item, ast.FunctionDef) and item.name in ("resource_breaches", "result_validity"):
                wanted.append(item)
        cls.namespace = {"math": math}
        exec(compile(ast.Module(body=wanted, type_ignores=[]), "<unapplied-resource-proposal>", "exec"), cls.namespace)
        cls.check = staticmethod(cls.namespace["resource_breaches"])

    @classmethod
    def tearDownClass(cls):
        assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in cls.before.items())

    def sample(self, captured=108.):
        return {"capture_monotonic_s": captured,
                "harness": {"rss_bytes": 1, "pid": 10},
                "model": {"private_commit_bytes": 1, "pid": 20},
                "gpu": {"devices": [{"index": 0, "memory_used_bytes": 1}]}}

    def run_check(self, sample, now=108., start=100., active=True, pid=20):
        return self.check(sample, now_monotonic_s=now, sampler_started_monotonic_s=start,
                          model_required=active, model_pid=pid)

    def test_grace_is_seven_seconds_from_sampler_origin(self):
        self.assertEqual(self.run_check(None, now=106.999), [])
        result = self.run_check(None, now=107.)
        self.assertEqual(result[0]["classification"], "infrastructure_failure")
        self.assertEqual(result[0]["sampler_elapsed_s"], 7.)

    def test_empty_or_malformed_sample_is_not_silent_after_grace(self):
        for sample in (None, [], "missing", {}):
            with self.subTest(sample=sample):
                self.assertTrue(self.run_check(sample))

    def test_fresh_complete_sample_passes_without_mutation(self):
        sample = self.sample()
        before = copy.deepcopy(sample)
        self.assertEqual(self.run_check(sample), [])
        self.assertEqual(sample, before)

    def test_seven_second_capture_age_boundary_and_stale_rejection(self):
        self.assertEqual(self.run_check(self.sample(101.), now=108.), [])
        result = self.run_check(self.sample(101.), now=108.001)
        self.assertEqual(result[0]["reason"], "latest completed resource sample is stale")
        self.assertAlmostEqual(result[0]["age_s"], 7.001)

    def test_future_or_previous_lifetime_capture_never_gets_grace(self):
        for stamp in (99., 102.):
            result = self.run_check(self.sample(stamp), now=101.)
            self.assertIn("outside sampler lifetime", result[0]["reason"])

    def test_bad_supervisor_and_sampler_monotonic_clocks_fail(self):
        for now, start in ((99., 100.), (float("nan"), 100.), (108., None), (108., True)):
            with self.subTest(now=now, start=start):
                result = self.run_check(self.sample(), now=now, start=start)
                self.assertEqual(result[0]["metric"], "monotonic_clock")

    def test_missing_or_nonfinite_capture_clock_is_required(self):
        for stamp in (None, True, float("nan"), float("inf"), -1):
            self.assertTrue(any(row["metric"] == "capture_monotonic_s"
                                for row in self.run_check(self.sample(stamp))))

    def test_each_required_process_metric_fails_independently(self):
        for role, key in (("harness", "rss_bytes"), ("model", "private_commit_bytes")):
            for value in (None, True, float("nan"), float("inf"), -1, "100"):
                sample = self.sample()
                sample[role][key] = value
                with self.subTest(role=role, value=value):
                    result = self.run_check(sample)
                    self.assertTrue(any(row["role"] == role and row["metric"] == key for row in result))
                    self.assertTrue(all(row["classification"] == "infrastructure_failure" for row in result))

    def test_absent_or_malformed_process_records_fail(self):
        for role in ("harness", "model"):
            sample = self.sample()
            sample[role] = []
            self.assertTrue(any(row["role"] == role for row in self.run_check(sample)))

    def test_inactive_model_commit_is_not_required_for_baseline(self):
        sample = self.sample()
        sample["model"] = {"pid": None, "private_commit_bytes": None}
        self.assertEqual(self.run_check(sample, active=False, pid=None), [])
        self.assertTrue(self.run_check(sample, active=True, pid=None))

    def test_old_model_process_sample_cannot_cover_active_model(self):
        result = self.run_check(self.sample(), pid=21)
        self.assertEqual(result[0]["metric"], "pid")
        self.assertEqual(result[0]["expected_pid"], 21)
        sample = self.sample()
        sample["model"]["pid"] = True
        self.assertTrue(self.run_check(sample, pid=1))

    def test_missing_empty_or_malformed_gpu_observations_fail(self):
        for devices in (None, [], {}, [None], [{}], [{"memory_used_bytes": None}]):
            sample = self.sample()
            sample["gpu"]["devices"] = devices
            self.assertTrue(any(row["role"] == "whole_gpu" for row in self.run_check(sample)))

    def test_one_valid_gpu_does_not_mask_another_missing_value(self):
        sample = self.sample()
        sample["gpu"]["devices"].append({"index": 1, "memory_used_bytes": None})
        result = self.run_check(sample)
        self.assertEqual(result[0]["device_index"], 1)
        self.assertEqual(result[0]["classification"], "infrastructure_failure")

    def test_gpu_unavailability_is_not_candidate_attributed(self):
        sample = self.sample()
        sample["gpu"] = {"devices": None, "missing_reason": "synthetic GPU timeout"}
        result = self.run_check(sample)
        self.assertEqual(result[0]["missing_reason"], "synthetic GPU timeout")
        self.assertEqual(result[0]["classification"], "infrastructure_failure")

    def test_observed_overages_apply_even_during_initial_grace(self):
        gib = self.namespace["GIB"]
        for role, key, limit in (("harness", "rss_bytes", 4), ("model", "private_commit_bytes", 12)):
            sample = self.sample(101.)
            sample[role][key] = limit * gib + 1
            self.assertEqual(self.run_check(sample, now=101.)[0]["classification"], "infrastructure_failure")
        sample = self.sample(101.)
        sample["gpu"]["devices"][0]["memory_used_bytes"] = 14 * gib + 1
        result = self.run_check(sample, now=101.)
        self.assertEqual(result[0]["classification"], "host_resource_invalid")
        self.assertIn("unknown", result[0]["attribution"])

    def test_exact_caps_and_zero_measurements_remain_valid(self):
        for factor in (0, 1):
            sample = self.sample()
            gib = self.namespace["GIB"]
            sample["harness"]["rss_bytes"] = factor * 4 * gib
            sample["model"]["private_commit_bytes"] = factor * 12 * gib
            sample["gpu"]["devices"][0]["memory_used_bytes"] = factor * 14 * gib
            self.assertEqual(self.run_check(sample), [])

    def test_missing_observations_exclude_infrastructure_without_changing_candidate_failures(self):
        classify = self.namespace["result_validity"]
        failure = self.run_check(None)[0]["classification"]
        self.assertTrue(classify(failure_class=failure, cleanup_errors=[], timing_failed=False,
                                 evaluation_authorized=True)["infrastructure_invalid"])
        self.assertFalse(classify(failure_class="candidate_contract_failure", cleanup_errors=[], timing_failed=False,
                                  evaluation_authorized=True)["infrastructure_invalid"])

    def test_policy_does_not_turn_sample_cadence_into_hard_cap(self):
        policy = self.namespace["RESOURCE_POLICY"]
        sampled = policy["sampled_watchdog"]
        self.assertFalse(policy["resource_caps_enforced"])
        self.assertEqual(sampled["initial_observation_grace_s"], sampled["observation_period_s"] + sampled["gpu_query_timeout_s"])
        self.assertEqual(sampled["maximum_sample_age_s"], 7.)
        self.assertNotIn("maximum_supervisor_check_interval_s", sampled)
        self.assertIn("not a measurement or detection bound", sampled["scope"])

    def test_supervisor_supplies_sampler_origin_active_model_and_current_clock(self):
        tree = ast.parse(self.sources["experiment.py"])
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "resource_breaches"]
        self.assertEqual(len(calls), 1)
        arguments = {item.arg: ast.unparse(item.value) for item in calls[0].keywords}
        self.assertEqual(arguments, {"now_monotonic_s": "resource_checked_at",
            "sampler_started_monotonic_s": "resource_started_counter",
            "model_required": "model is not None", "model_pid": "model_pid()"})
        ast.parse(self.sources["test_experiment.py"])


if __name__ == "__main__":
    if "--applied" in sys.argv:
        APPLIED = True
        sys.argv.remove("--applied")
    unittest.main(verbosity=2)
