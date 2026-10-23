"""Fresh-process CLI module boundary regressions; no queue, model, physics or Map work."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
PAYLOAD = r'''
import argparse, json, runpy, sys, tempfile
from pathlib import Path
from unittest.mock import patch
runtime = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(runtime))
captured = {}
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    manifest = {'release_id':'synthetic-cli', 'run_id':'synthetic-cli-run', 'paired_block_id':'synthetic-block',
                'architecture':'baseline', 'parts':3, 'cap_s':300.0, 'condition':'persistent', 'scenario':'nominal',
                'seeds':{'world_seed':1, 'layout_seed':2, 'policy_seed':3, 'noise_seed':4}}
    def stop_before_dispatch(*args, **kwargs):
        main = sys.modules['__main__']
        # Exercise the actual direct-script class and private token. No release
        # or queue gate is invoked or claimed by this isolated boundary fixture.
        captured['context'] = main.VerifiedEvaluationContext(root, json.dumps(manifest), 'a'*64, 'b'*64,
                'synthetic-job', '2000-01-01T00:00:00+00:00', '{}', main._AUTHORITY)
        raise SystemExit(0)
    sys.argv = [str(runtime/'release_runner.py'), '--help']
    with patch.object(argparse.ArgumentParser, 'parse_args', side_effect=stop_before_dispatch):
        try: runpy.run_path(str(runtime/'release_runner.py'), run_name='__main__')
        except SystemExit as stop: assert stop.code == 0
    import release_runner as canonical
    import experiment
    context = captured['context']
    arguments = dict(kind='baseline', n=3, cap=300.0, condition='persistent', scenario='nominal',
                     run_id=manifest['run_id'], seeds=manifest['seeds'])
    report = {'same_class': type(context) is canonical.VerifiedEvaluationContext}
    try:
        path, provenance = experiment.authorized_evidence_path('evaluation', context, **arguments)
        report['accepted'] = path == root/'attempts'/'synthetic-cli-run'/'evidence'
        report['provenance_job'] = provenance['queue_job_id']
    except Exception as error:
        report.update(accepted=False, error=type(error).__name__ + ': ' + str(error))
    if report['accepted']:
        forged = canonical.VerifiedEvaluationContext(root, json.dumps(manifest), 'a'*64, 'b'*64,
                    'synthetic-job', '2000-01-01T00:00:00+00:00', '{}', object())
        for key, value, args in [('forged_rejected', forged, arguments),
                                 ('arguments_rejected', context, {**arguments, 'n':6})]:
            try: experiment.authorized_evidence_path('evaluation', value, **args)
            except canonical.ReleaseError: report[key] = True
            else: report[key] = False
    print(json.dumps(report))
'''


def check(runtime):
    completed = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', PAYLOAD, str(runtime)],
                               text=True, capture_output=True, timeout=30,
                               creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


class DirectEntrypointTests(unittest.TestCase):
    def test_original_frozen_script_reproduces_class_identity_failure(self):
        report = check(HERE.parent / 'Batch 01/selection-evidence-final-001/current-runtime')
        self.assertFalse(report['same_class'])
        self.assertFalse(report['accepted'])
        self.assertIn('Evaluation requires a verified release context', report['error'])

    def test_versioned_script_uses_same_authorization_class(self):
        report = check(HERE)
        self.assertTrue(report['same_class'])
        self.assertTrue(report['accepted'])
        self.assertEqual(report['provenance_job'], 'synthetic-job')

    def test_fix_preserves_private_authority_and_exact_arguments(self):
        report = check(HERE)
        self.assertTrue(report['forged_rejected'])
        self.assertTrue(report['arguments_rejected'])


if __name__ == '__main__':
    unittest.main()
