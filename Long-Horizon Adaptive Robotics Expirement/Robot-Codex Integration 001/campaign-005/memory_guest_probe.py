"""Deterministic guest fixture only; never installed in an actual robot workspace."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

number = int(sys.argv[1])
root = Path('/workspace')
checks = {}
index = json.loads((root/'ArtifactInventory.json').read_text())
checks['framework_index_identified'] = index['author'] == 'framework'
try:
    (root/'ArtifactInventory.json').write_text('agent cannot rewrite framework inventory')
    checks['inventory_read_only'] = False
except OSError:
    checks['inventory_read_only'] = True
artifact = root/'programs/format_label.py'
handoff = root/'.continuity/Continuity.md'
if number == 1:
    artifact.write_text('import sys\nprint(sys.argv[1].strip().lower())\n')
    (root/'notes/label-evidence.md').write_text('Synthetic string fixture only; no robot outcome.\n')
    (root/'notes/removed-between-sessions.txt').write_text('A deletion must appear in the next inventory.\n')
    (root/'programs/unfollowed-link').symlink_to('/absent-private-fixture')
    handoff.write_text('# Handoff map\n\n- programs/format_label.py: normalize text labels for a future text task. Assumes a string argument; does not validate robot state or grant authority. Evidence: notes/label-evidence.md.\n')
    checks['artifact_and_semantic_map_created'] = True
else:
    text = (root/'Continuity.md').read_text()
    checks['semantic_reference_encountered'] = all(s in text for s in ('programs/format_label.py','normalize text labels','Assumes','does not validate robot state'))
    entries = {e['path']: e for e in index['entries']}
    e = entries['programs/format_label.py']
    content = artifact.read_bytes()
    checks['inventory_binds_exact_prior_version'] = e['identity']['sha256'] == hashlib.sha256(content).hexdigest() and e['snapshot_version'] == 1
    checks['symlink_listed_without_following'] = entries['programs/unfollowed-link']['identity']['target'] == '/absent-private-fixture'
    output = subprocess.check_output([sys.executable,'-B',str(artifact),' Neutral '],text=True)
    checks['prior_artifact_executed'] = output == 'neutral\n'
    artifact.write_text('import sys\nprint(sys.argv[1].strip().casefold())\n')
    handoff.write_text(text+'\nUpdated programs/format_label.py to casefold Unicode; still text-only, with no robot authority.\n')
    (root/'notes/removed-between-sessions.txt').unlink()
    checks['artifact_materially_updated_and_indexed'] = True
print(json.dumps({'number':number,'checks':checks,'inventory':index,'handoff':handoff.read_text(),
                  'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
                  'pid':os.getpid(),'pid_namespace':os.readlink('/proc/self/ns/pid')}),flush=True)
assert all(checks.values()), checks
