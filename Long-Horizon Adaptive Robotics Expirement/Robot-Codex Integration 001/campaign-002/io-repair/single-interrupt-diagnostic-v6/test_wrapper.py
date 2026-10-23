"""Fixed candidate wrapper has one invocation and the original guarded launcher."""
import ast
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import common
import launch

class Tests(unittest.TestCase):
    def manifest(self):
        value = common.read(common.REFERENCE)
        value.update(run_id=common.RUN, framework_revision=common.REVISION, qualification_stage=common.STAGE,
                     outer_campaign_protocol=common.PROTOCOL, model_turns_max=1,
                     runtime_workspace=str(common.WORKSPACE), runtime_input_files=common.required_inputs())
        return value

    def test_exact_policy_and_source_closure(self):
        common.validate_manifest(self.manifest())
        self.assertEqual(common.RUN, 'RCI001-C02-shutdown-diagnostic-006')
        self.assertEqual(common.REVISION, 'RCI001-C02-dev-098')
        self.assertEqual(len(common.read(common.PREVIOUS)['sources']), 986)
        self.assertTrue(set(common.read(common.PREVIOUS)['sources']) <= set(common.required_inputs()))

    def test_no_looser_caps_prompt_or_invocation_count(self):
        for field, changed in (('invocation_wall_cap_s', 601), ('bootstrap', 'altered'),
                               ('model_turns_max', 2), ('effort', 'low'), ('model', 'different')):
            value = self.manifest(); value[field] = changed
            with self.assertRaises(ValueError): common.validate_manifest(value)

    def test_one_invocation_inside_candidate_scope_and_original_launcher(self):
        source = (common.HERE/'run.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Attribute) and n.func.attr == 'run_invocation']
        self.assertEqual(len(calls), 1); self.assertEqual(calls[0].args[0].value, 'interrupt')
        scopes = [n for n in ast.walk(tree) if isinstance(n, ast.With) and any(
            isinstance(item.context_expr, ast.Call) and isinstance(item.context_expr.func, ast.Attribute)
            and item.context_expr.func.attr == 'installed' for item in n.items)]
        self.assertEqual(len(scopes), 1); self.assertIn(calls[0], list(ast.walk(scopes[0])))
        self.assertEqual((common.HERE/'launch.py').read_bytes(),
                         (common.HERE.parent/'single-interrupt-diagnostic-v4/launch.py').read_bytes())

    def test_existing_footprint_prevents_all_process_and_queue_calls(self):
        with patch.object(common, 'validate'), patch.object(common, 'output_paths', side_effect=ValueError('used')), \
             patch.object(launch.subprocess, 'Popen') as process, patch.object(launch.subprocess, 'check_output') as queue:
            with self.assertRaisesRegex(ValueError, 'used'): launch.launch(common.MANIFEST, common.SNAPSHOT)
            process.assert_not_called(); queue.assert_not_called()

if __name__ == '__main__': unittest.main()
