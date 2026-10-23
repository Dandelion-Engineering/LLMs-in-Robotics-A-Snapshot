"""Trusted startup inventory of public durable bytes; no semantic evaluation.

Runs before guest admission and never follows a guest-created symlink. Version
numbers count changed startup snapshots, not every intermediate write (the exact
filesystem journal retains those). No author, usefulness or outcome is inferred.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

NAME = 'ArtifactInventory.json'
SCHEMA = 'campaign005-artifact-inventory-1'


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('utf-8')


def publish(workspace, session_id):
    root = Path(workspace)
    target = root / NAME
    old_raw = target.read_bytes() if target.exists() else None
    old = json.loads(old_raw) if old_raw else {'entries': []}
    previous = {e['path']: e for e in old['entries']}
    entries = []
    pending = [root / name for name in ('notes', 'programs', '.continuity')]
    while pending:
        path = pending.pop()
        mode = path.lstat().st_mode
        rel = path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):
            pending.extend(sorted(path.iterdir(), reverse=True))
            continue
        if stat.S_ISREG(mode):
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
            identity = {'kind': 'file', 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}
        elif stat.S_ISLNK(mode):
            link = os.readlink(path)
            identity = {'kind': 'symlink', 'target': link,
                        'sha256': hashlib.sha256(link.encode('utf-8')).hexdigest()}
        else:
            raise ValueError('Unsupported durable artifact type: ' + rel)
        if rel == '.continuity/Continuity.md':
            rel = 'Continuity.md'
        prior = previous.get(rel)
        changed = prior is None or prior['identity'] != identity
        entries.append({'path': rel, 'identity': identity,
                        'snapshot_version': (prior['snapshot_version'] if prior else 0) + int(changed),
                        'first_observed_before_session': prior['first_observed_before_session'] if prior else session_id,
                        'last_change_observed_before_session': session_id if changed else prior['last_change_observed_before_session'],
                        'change_since_previous_snapshot': 'added' if prior is None else 'changed' if changed else 'unchanged'})
    entries.sort(key=lambda e: e['path'])
    value = {'schema': SCHEMA, 'author': 'framework', 'observed_before_session': session_id,
             'scope': 'Startup snapshot of durable writable artifacts. Intermediate versions remain in the filesystem journal. This inventory does not assert authorship, usefulness, safety, authority or physical outcome. Symlinks are listed, never followed.',
             'previous_inventory_sha256': hashlib.sha256(old_raw).hexdigest() if old_raw else None,
             'entries': entries,
             'removed_since_previous_snapshot': sorted(set(previous) - {e['path'] for e in entries})}
    raw = encode(value)
    if len(raw) > 16 * 1024**2:
        raise ValueError('Inventory exceeds inherited per-file bound')
    temp = root / (NAME + '.trusted-next')
    with temp.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, target)
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'entries': len(entries), 'observed_before_session': session_id}
