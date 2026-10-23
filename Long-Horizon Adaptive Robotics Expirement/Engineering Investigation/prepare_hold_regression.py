"""Archive hash-exact original bytes and adapt checks to the applied hold module."""
import hashlib
import json
from pathlib import Path

from stage_hold_observation import BASES, HERE, PROJECT, STAGE, SAMPLER, NATIVE_METHOD


def prepare():
    integration = json.loads((STAGE / 'integration.json').read_text(encoding='utf-8'))
    archive = STAGE / 'original'
    for change in integration['changed']:
        path = PROJECT / change['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != change['staged_sha256']:
            raise ValueError('Applied source differs from reviewed proposal')
        text = path.read_text(encoding='utf-8')
        if path.name == 'measurement.py':
            if text.count(SAMPLER) != 1 or text.count(NATIVE_METHOD) != 1:
                raise ValueError('Exact original reconstruction anchors differ')
            text = text.replace(SAMPLER, '').replace(NATIVE_METHOD, '')
        else:
            text = text.replace('self.hold_window.native_snapshot(self.cells[0])', 'self.snapshot()')
        possibilities = (text.encode('utf-8'), text.replace('\n', '\r\n').encode('utf-8'))
        matches = [raw for raw in possibilities if hashlib.sha256(raw).hexdigest() == change['before_sha256']]
        if len(matches) != 1: raise ValueError('Reconstructed bytes do not match exact retained original identity')
        target = archive / change['path']; target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != matches[0]: raise ValueError('Archived original already differs')
        target.write_bytes(matches[0])
    text = (HERE / 'hold_observation_checks.py').read_text(encoding='utf-8')
    text = text.replace('Opt-in native static equivalence checks for the unapplied hold patch.',
                        'Native static regression checks for the applied hold patch and exact archived original.')
    text = text.replace('staged_sources()  # Exact held-source guard, read only.',
                        "ARCHIVE = STAGE / 'original'\nimport json\nINTEGRATION = json.loads((STAGE / 'integration.json').read_text())")
    text = text.replace('PROJECT / "Batch 01/Recovery Qualification/measurement.py"',
                        'ARCHIVE / "Batch 01/Recovery Qualification/measurement.py"')
    text = text.replace('STAGE / "Batch 01/Recovery Qualification/measurement.py"',
                        'PROJECT / "Batch 01/Recovery Qualification/measurement.py"')
    start = text.index('    def test_only_the_intended_two_sources_change_and_no_held_source_was_edited(self):')
    end = text.index("\n\nif __name__", start)
    text = text[:start] + '''    def test_applied_sources_and_archived_originals_match_exact_retained_guards(self):
        changed = {row['path']: row for row in INTEGRATION['changed']}
        for name, expected in BASES.items():
            if name in changed:
                self.assertEqual(digest(ARCHIVE / name), expected)
                self.assertEqual(digest(PROJECT / name), changed[name]['staged_sha256'])
            else:
                self.assertEqual(digest(PROJECT / name), expected)
        original_record = (ARCHIVE / 'Batch 01/Recovery Qualification/measurement.py').read_text(encoding='utf8').split('    def record(self, snapshot, sim, wall, *, tick):', 1)[1]
        applied_record = (PROJECT / 'Batch 01/Recovery Qualification/measurement.py').read_text(encoding='utf8').split('    def record(self, snapshot, sim, wall, *, tick):', 1)[1]
        self.assertEqual(original_record, applied_record)
        old = (ARCHIVE / 'Batch 01/Recovery Qualification/run_screen.py').read_text(encoding='utf8')
        new = (PROJECT / 'Batch 01/Recovery Qualification/run_screen.py').read_text(encoding='utf8')
        self.assertEqual(new.replace('self.hold_window.native_snapshot(self.cells[0])', 'self.snapshot()'), old)
''' + text[end:]
    destination = HERE / 'hold_observation_regression.py'
    compile(text, str(destination), 'exec')
    destination.write_text(text, encoding='utf-8', newline='\n')
    return str(destination)


if __name__ == '__main__': print(prepare())
