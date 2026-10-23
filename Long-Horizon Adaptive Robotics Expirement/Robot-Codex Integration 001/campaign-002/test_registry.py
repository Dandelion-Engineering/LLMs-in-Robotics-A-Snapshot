"""Metadata-only release/source lineage tests in an isolated synthetic directory."""
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

import registry
import prepare_scored
import admission


class RegistryTests(unittest.TestCase):
    def test_preparation_covers_all_twenty_fixed_slots_and_fresh_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = root / 'campaign-002'
            campaign.mkdir()
            (campaign / 'PLAN.md').write_bytes((prepare_scored.HERE / 'PLAN.md').read_bytes())
            snapshot = root / 'snapshot.json'
            snapshot.write_text(json.dumps({'revision': 'RCI001-C02-dev-synthetic', 'sources': {}}))
            output = campaign / 'predeclared'
            with patch.object(prepare_scored, 'HERE', campaign), \
                 patch.object(prepare_scored, 'RCI', root / 'integration'), \
                 patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'external-workspaces')}), \
                 patch.object(sys, 'argv', ['prepare_scored.py', '--snapshot', str(snapshot), '--output', str(output)]), \
                 redirect_stdout(io.StringIO()):
                prepare_scored.main()
            schedule = json.loads((output / 'schedule.json').read_text())
            attempts = json.loads((campaign / 'execution-plan.json').read_text())['attempts']
            # The independent admission validator checks exact old fixture/model
            # limits, alternating pair order, all20 identities and path uniqueness.
            admission.verify_schedule(schedule, attempts, 'RCI001-C02-dev-synthetic')
            self.assertEqual(len(attempts), 20)
            self.assertEqual(len({row['run_id'] for row in attempts}), 20)
            self.assertEqual([row['noise_seed'] for row in schedule['slots']], list(range(23001, 23021)))

    def test_scored_release_retains_distinct_source_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / 'releases/RCI001-C02-frozen-001'
            release.mkdir(parents=True)
            (release / 'snapshot.json').write_text(json.dumps({'revision': 'RCI001-C02-dev-synthetic'}))
            (release / 'code.zip').write_bytes(b'synthetic sealed archive')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'run_id': 'RCI001-C02-stock-01', 'family': 'misplaced-stock',
                'framework_revision': 'RCI001-C02-dev-synthetic'}))
            cert = root / 'certificate.json'
            cert.write_text('{}')
            records = []
            with patch.object(registry, 'MAP', root), patch.object(registry, 'append', side_effect=lambda kind, row: records.append((kind, row))):
                registry.add_run(manifest, 'RCI001-C02-frozen-001', 'evaluation', cert)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0][1]['revision_id'], 'RCI001-C02-frozen-001')
            self.assertEqual(records[0][1]['condition_details']['manifest']['framework_revision'], 'RCI001-C02-dev-synthetic')
            self.assertEqual(json.loads((release / 'snapshot.json').read_text())['revision'], 'RCI001-C02-dev-synthetic')

    def test_manifest_cannot_claim_metadata_revision_as_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / 'releases/RCI001-C02-frozen-001'
            release.mkdir(parents=True)
            (release / 'snapshot.json').write_text(json.dumps({'revision': 'RCI001-C02-dev-synthetic'}))
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'run_id': 'synthetic', 'framework_revision': 'RCI001-C02-frozen-001'}))
            with patch.object(registry, 'MAP', root), patch.object(registry, 'append') as append:
                with self.assertRaisesRegex(ValueError, 'source revision'):
                    registry.add_run(manifest, 'RCI001-C02-frozen-001', 'evaluation')
                append.assert_not_called()


if __name__ == '__main__':
    unittest.main()
