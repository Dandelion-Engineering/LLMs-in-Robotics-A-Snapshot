"""Development qualification entry refuses unverified input before run registration."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import experiment
import record_attempt
from restart_calibration_loader import CalibrationInputError


class DevelopmentQualificationTests(unittest.TestCase):
    def test_cli_rejects_implicit_legacy_input_without_running_an_episode(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'freeze.json';source.write_text('{}',encoding='utf-8')
            with patch('sys.argv',['experiment.py','--development-restart-freeze',str(source)]), \
                 patch.object(experiment,'run_episode') as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):experiment.main()
                run.assert_not_called()

    def test_cli_forwards_only_the_loader_issued_token(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'freeze.json';source.write_text('{"test": true}',encoding='utf-8')
            token=object()
            with patch('sys.argv',['experiment.py','--development-restart-freeze',str(source)]), \
                 patch('restart_calibration_loader.load_restart_qualification',return_value=token) as load, \
                 patch.object(experiment,'run_episode') as run:
                experiment.main()
                load.assert_called_once_with({'test':True},source)
                self.assertIs(run.call_args.kwargs['development_restart_qualification'],token)
                self.assertNotIn('evaluation_context',run.call_args.kwargs)

    def test_registration_rejects_bad_qualification_before_reading_or_mutating_map(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'freeze.json';source.write_text(json.dumps({'restart_matching_mode':'qualified_class'}),encoding='utf-8')
            args=SimpleNamespace(run_id='B01-dev-synthetic-only',kind='baseline',development_restart_freeze=source)
            with patch.object(record_attempt.am,'read_store') as read:
                with self.assertRaises(CalibrationInputError):record_attempt.prepare(args)
                read.assert_not_called()


if __name__=='__main__':unittest.main()
