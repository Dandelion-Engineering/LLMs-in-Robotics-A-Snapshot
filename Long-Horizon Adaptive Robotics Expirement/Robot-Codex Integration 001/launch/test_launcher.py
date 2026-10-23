import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("robot_launcher", Path(__file__).with_name("robot_codex_launcher.py"))
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_exact_authorized_bootstrap(self):
        self.assertEqual(launcher.BOOTSTRAP, "Follow the instructions in RobotAgentPrompt.md.")

    def test_credential_environment_filtered_by_name(self):
        with mock.patch.dict(os.environ, {"FAKE_SECRET": "synthetic", "OPENAI_API_KEY": "synthetic", "CODEX_DEBUG": "synthetic", "ROBOT_VISIBLE": "yes"}):
            clean = launcher.clean_environment(Path("C:/test/codex"))
        self.assertNotIn("FAKE_SECRET", clean)
        self.assertNotIn("OPENAI_API_KEY", clean)
        self.assertNotIn("CODEX_DEBUG", clean)
        self.assertEqual(clean["ROBOT_VISIBLE"], "yes")
        self.assertEqual(clean["CODEX_HOME"], str(Path("C:/test/codex")))

    def test_no_legacy_sandbox_override_or_bypass(self):
        import argparse
        args = argparse.Namespace(workspace=Path("C:/runtime"))
        config = launcher.configuration(args.workspace, Path("C:/research"), Path("C:/private/codex"), Path("C:/evidence"), False)
        command = launcher.execution_command(args, config)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertNotIn("--sandbox", command)
        self.assertFalse(any("sandbox_mode=" in argument for argument in command))
        self.assertFalse(any("bypass" in argument for argument in command))
        profile = config["permissions.robot_runtime"]
        self.assertEqual(profile["filesystem"][":root"], "deny")
        self.assertFalse(profile["network"]["enabled"])
        self.assertFalse(config["features.memories"])
        self.assertEqual(config["project_doc_max_bytes"], 0)

    def test_policy_digest_binds_access_not_log_directory(self):
        workspace, repo, home = Path("C:/runtime"), Path("C:/research"), Path("C:/private/codex")
        first = launcher.configuration(workspace, repo, home, Path("C:/evidence/1"), False)
        second = launcher.configuration(workspace, repo, home, Path("C:/evidence/2"), False)
        self.assertEqual(launcher.policy_digest(first, Path("C:/evidence/1")), launcher.policy_digest(second, Path("C:/evidence/2")))
        second["permissions.robot_runtime"]["filesystem"][":root"] = "read"
        self.assertNotEqual(launcher.policy_digest(first, Path("C:/evidence/1")), launcher.policy_digest(second, Path("C:/evidence/2")))

    def test_alternative_does_not_remove_explicit_denials(self):
        config = launcher.configuration(Path("C:/runtime"), Path("C:/research"), Path("C:/private/codex"), Path("C:/evidence"), False, "users-deny")
        filesystem = config["permissions.robot_runtime"]["filesystem"]
        self.assertEqual(filesystem[":root"], "read")
        self.assertEqual(filesystem["C:/Users"], "deny")
        self.assertEqual(filesystem[Path("C:/research").resolve().as_posix()], "deny")
        self.assertEqual(filesystem[Path("C:/private/codex").resolve().as_posix()], "deny")

    def test_model_evidence_rejects_self_report(self):
        header = "OpenAI Codex v0.157.1\n--------\nmodel: gpt-6-astra\nreasoning effort: max\nsandbox: restricted\nuser\nFollow the instructions in RobotAgentPrompt.md.\n"
        self.assertTrue(launcher.verify_header("", header)["matches_pinned_model"])
        self.assertFalse(launcher.verify_header(header, "")["matches_pinned_model"])
        self.assertFalse(launcher.verify_header("", "user\nrequest\nassistant\n" + header)["matches_pinned_model"])
        self.assertFalse(launcher.verify_header("", header.replace("effort: max", "effort: low"))["matches_pinned_model"])

    def test_timeout_kills_child_tree_and_retains_output(self):
        with tempfile.TemporaryDirectory(prefix="robot-launcher-test-") as folder:
            base = Path(folder).resolve()
            heartbeat = base / "heartbeat.txt"
            child_code = "from pathlib import Path; import time\np=Path(" + repr(str(heartbeat)) + ")\nwhile True:\n p.write_text(str(time.time()))\n time.sleep(0.03)"
            parent_code = "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c'," + repr(child_code) + "])\nprint('synthetic-child-started',flush=True)\ntime.sleep(20)"
            result = launcher.bounded_process([sys.executable, "-u", "-c", parent_code], base, base / "evidence", 0.6)
            self.assertEqual(result["termination_reason"], "timeout")
            self.assertIn("synthetic-child-started", (base / "evidence/stdout.txt").read_text())
            first = heartbeat.read_text()
            time.sleep(0.15)
            self.assertEqual(first, heartbeat.read_text())
            self.assertTrue((base / "evidence/stderr.txt").is_file())

    def test_missing_catalog_model_fails(self):
        with self.assertRaises(ValueError):
            launcher.selected_catalog({"models": [{"slug": "different", "supported_reasoning_levels": [{"effort": "max"}]}]})

    def test_output_limit_remains_a_failed_run(self):
        with tempfile.TemporaryDirectory(prefix="robot-launcher-limit-test-") as folder:
            base = Path(folder).resolve()
            result = launcher.bounded_process([sys.executable, "-c", "print('x'*100000)"], base, base / "evidence", 5, max_output=1024)
            self.assertEqual(result["termination_reason"], "output_limit")
            self.assertEqual((base / "evidence/stdout.txt").stat().st_size, 1024)


if __name__ == "__main__":
    unittest.main()
