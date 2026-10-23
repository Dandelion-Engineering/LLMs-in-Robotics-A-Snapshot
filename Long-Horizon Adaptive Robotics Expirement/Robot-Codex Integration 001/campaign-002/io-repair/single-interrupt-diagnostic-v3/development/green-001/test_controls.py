"""Fixed v3 wrapper contract tests; no native, socket, queue or host actions."""
import ast
import copy
import unittest

import common


class WrapperContractTests(unittest.TestCase):
    def manifest(self):
        value = common.read(common.REFERENCE)
        value.update(run_id=common.RUN, framework_revision=common.REVISION,
                     qualification_stage=common.STAGE, outer_campaign_protocol=common.PROTOCOL,
                     model_turns_max=1, runtime_workspace=str(common.WORKSPACE),
                     runtime_input_files=common.required_inputs())
        return value

    def test_fixed_v3_identity_and_original_smoke026_policy(self):
        self.assertEqual(common.RUN, 'RCI001-C02-shutdown-diagnostic-003')
        self.assertEqual(common.REVISION, 'RCI001-C02-dev-091')
        self.assertEqual(common.PROTOCOL, 'RCI001-Campaign002-single-interrupt-diagnostic-v3')
        self.assertEqual(common.STAGE, 'campaign002-single-interrupt-diagnostic')
        self.assertEqual(common.REFERENCE.name, 'smoke-026-manifest.json')
        self.assertEqual(common.REFERENCE_SHA256,
                         '0d6bfb4a1180f53dba8e784cdd4ef68d7d1fedef4ca7d74015b424a66380f142')
        self.assertEqual(common.sha(common.REFERENCE), common.REFERENCE_SHA256)
        self.assertEqual(common.ROOT.name, 'shutdown-diagnostic-003')
        self.assertEqual(common.METHOD.name, 'SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md')

    def test_only_exact_seven_manifest_fields_change(self):
        basis = common.read(common.CAMPAIGN / 'qualification/smoke-026-manifest.json')
        value = self.manifest()
        changed = {key for key in basis if not common.exact(value[key], basis[key])}
        self.assertEqual(set(value), set(basis))
        self.assertEqual(changed, {'run_id','framework_revision','qualification_stage',
            'outer_campaign_protocol','model_turns_max','runtime_workspace','runtime_input_files'})
        self.assertEqual(basis['model_turns_max'], 2)
        self.assertEqual(value['model_turns_max'], 1)
        self.assertEqual((value['seed'], value['noise_seed']), (173, 24101))
        self.assertEqual(value['bootstrap'], 'Follow the instructions in RobotAgentPrompt.md.')

    def test_run_and_launch_byte_identical_to_pinned_v2(self):
        expected = {'run.py':'3ec098c7aaee147adf3c6228e3330eb9322fdbf20f3738dca3af668db417c3ec',
                    'launch.py':'63af0d5c9e1383c7e51d52c30dab38043c707b9df42ba5dc01a247ce742cf79d'}
        for name, digest in expected.items():
            with self.subTest(name=name):
                old = common.HERE.parent / 'single-interrupt-diagnostic-v2' / name
                self.assertEqual((common.HERE/name).read_bytes(), old.read_bytes())
                self.assertEqual(common.sha(common.HERE/name), digest)

    def test_every_unrelated_common_function_is_ast_identical(self):
        def nodes(path):
            return {node.name:node for node in ast.parse(path.read_bytes()).body
                    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
        before = nodes(common.HERE.parent / 'single-interrupt-diagnostic-v2/common.py')
        after = nodes(common.HERE / 'common.py')
        self.assertEqual(set(before), set(after))
        for name in before:
            if name == 'required_inputs':
                continue
            original = copy.deepcopy(before[name])
            for item in ast.walk(original):
                if isinstance(item,ast.Constant) and item.value == 'Original Smoke019 policy basis changed':
                    item.value = 'Original Smoke026 policy basis changed'
            with self.subTest(name=name):
                self.assertEqual(ast.dump(original), ast.dump(after[name]))

    def test_declared_fixed_provenance_and_operator_sources_in_inventory(self):
        names = common.required_inputs()
        self.assertEqual(names, sorted(set(names)))
        for name in ['prepare_socket_abort_diagnostic.py','control_socket_abort_diagnostic.py',
                     'test_control_socket_abort_diagnostic.py','SOCKET_ABORT_DIAGNOSTICS_V1.md',
                     'SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md',
                     'smoke026-queue-failure-diagnosis-001/analysis.json',
                     'socket-abort-instrumentation-development-001/final-check-002/receipt.json',
                     'socket-abort-loopback-development-002/execution-001/receipt.json',
                     'socket-abort-loopback-development-002/execution-001/child/result.json',
                     'socket-abort-assessment-fixture-development-001/final-receipt.json',
                     'checks-033/test-execution.json','checks-033-source-state.json',
                     'checks-033-execution-001/receipt.json']:
            with self.subTest(name=name):
                self.assertIn((common.HERE.parent/name).relative_to(common.REPO).as_posix(), names)
        for path in common.HERE.glob('*.py'):
            self.assertIn(path.relative_to(common.REPO).as_posix(), names)
        self.assertNotIn((common.HERE/'development/receipt.json').relative_to(common.REPO).as_posix(), names)

    def test_each_required_provenance_item_cannot_be_omitted(self):
        value = self.manifest()
        for relative in common.PROVENANCE_INPUTS:
            with self.subTest(relative=relative):
                missing = copy.deepcopy(value)
                missing['runtime_input_files'].remove((common.HERE.parent/relative).relative_to(common.REPO).as_posix())
                with self.assertRaisesRegex(ValueError,'source inventory'):
                    common.validate_manifest(missing)

    def test_v2_and_other_attempt_identities_are_rejected(self):
        for key,value in [('run_id','RCI001-C02-shutdown-diagnostic-002'),
                          ('framework_revision','RCI001-C02-dev-062'),
                          ('outer_campaign_protocol','RCI001-Campaign002-single-interrupt-diagnostic-v2'),
                          ('model_turns_max',2),('model_turns_max',True)]:
            with self.subTest(key=key,value=value):
                candidate = self.manifest(); candidate[key] = value
                with self.assertRaisesRegex(ValueError,'caps, fixture'):
                    common.validate_manifest(candidate)

    def test_fixed_runtime_and_unchanged_assessor_sources_required(self):
        inputs = common.required_inputs()
        expected = {'harness/codehost_bridge_v3.py':'419c13a6761fa23bed0a06b540ffba3f327a2d86ff94ad55e1c9b8ece16b0a75',
            'harness/test_codehost_bridge_v3.py':'b0f9002e0740b5998b7c4e7c1d61cbbab143ea5e9bc348750cffeba1f113f2ef',
            'assessment/transport_integrity_v3.py':'758a936c2d1bfad6389589cdf80e83e92950353c47418e65abd47a432a88c18e',
            'assessment/test_transport_integrity_v3.py':'1f21e835e94e14ba253988bf23da7dcb9a285f7ffd4d7777ec03950f78c5c198'}
        for name,digest in expected.items():
            with self.subTest(name=name):
                path = common.CAMPAIGN/name
                self.assertIn(path.relative_to(common.REPO).as_posix(), inputs)
                self.assertEqual(common.sha(path), digest)


if __name__ == '__main__':
    unittest.main()
