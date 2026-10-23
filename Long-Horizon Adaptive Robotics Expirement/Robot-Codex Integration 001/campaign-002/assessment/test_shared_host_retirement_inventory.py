"""Stage inventory must not omit the new independently verified host receipt."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import assess_smoke_v2 as subject


class SharedHostRetirementInventoryTests(unittest.TestCase):
    def inspect(self, host_name, qualified=True):
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        names=['executor-1-retirement.json','executor-2-retirement.json',host_name]
        for name in names:(root/name).write_text(json.dumps({'qualified':qualified if name==host_name else True}))
        def read(path):return json.loads(path.read_bytes()) if path.exists() else {}
        with patch.object(subject,'read_json',side_effect=read),patch.object(subject,'snapshot',return_value=({},[])), \
             patch.object(subject,'jsonl',return_value=[]),patch.object(subject,'valid_program_records',return_value=({},[])), \
             patch.object(subject,'check_retirement',side_effect=lambda value:value['qualified']), \
             patch.object(subject,'upgrade_stage',side_effect=lambda root,stage,**kw:stage):
            return subject.inspect_stage(root)

    def test_legacy_and_shared_host_receipts_each_complete_three_namespace_inventory(self):
        for host in ('codehost-1-retirement.json','codehost-owner-retirement-v3.json'):
            with self.subTest(host=host):
                stage=self.inspect(host)
                self.assertEqual(len(stage['retirements']),3)
                self.assertTrue(stage['checks']['all_namespace_retirements_observed'])

    def test_versioned_host_failure_is_included_and_fails_existing_gate(self):
        stage=self.inspect('codehost-owner-retirement-v3.json',False)
        self.assertIn('codehost-owner-retirement-v3.json',stage['retirements'])
        self.assertFalse(stage['checks']['all_namespace_retirements_observed'])


if __name__=='__main__':unittest.main()
