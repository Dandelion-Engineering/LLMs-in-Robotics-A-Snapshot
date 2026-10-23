"""Prepare a source-hash-guarded unapplied patch; never edit Runtime."""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parents[1] / 'Runtime' / 'restart_physical_class.py'
ORIGINAL_SHA256 = '9ce69d9df5b543b832cc52d7124e1d436a78e5ca377070a7bc12a7b069a4db91'
ANCHOR = "    result['seal_sha256'] = digest(result)\n    return result\n"
REPLACEMENT = """    result['seal_sha256'] = digest(result)
    # Build the exact-byte memo at compilation, before the physics clock.
    # Every later capture still reads and compares the complete live model.
    if _model_surface_sha(model, result) != result['compiled_surface_sha256']:
        raise UnsupportedEvidence('compiled model changed during seal initialization')
    return result
"""


def proposal():
    raw = TARGET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Runtime exporter differs from the reviewed original; do not apply this patch')
    original = raw.decode('utf-8').replace('\r\n', '\n')
    if original.count(ANCHOR) != 1:
        raise ValueError('Seal return anchor is not unique')
    return original, original.replace(ANCHOR, REPLACEMENT)


def prepare():
    original, proposed = proposal()
    stage = HERE / 'seal-memo-stage'
    stage.mkdir(exist_ok=False)
    for name, value in (('original.py', original), ('proposed.py', proposed)):
        (stage / name).write_text(value, encoding='utf-8', newline='\n')
    relative = 'Long-Horizon Adaptive Robotics Expirement/Runtime/restart_physical_class.py'
    patch = ''.join(difflib.unified_diff(original.splitlines(True), proposed.splitlines(True),
                                       fromfile='a/' + relative, tofile='b/' + relative))
    patch_path = HERE / 'seal-memo-initialization.patch'
    with patch_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(patch)
    manifest = {'schema_version': 'unapplied-seal-memo-initialization-1',
        'target': str(TARGET), 'original_byte_sha256': ORIGINAL_SHA256,
        'staged_original_lf_sha256': hashlib.sha256(original.encode()).hexdigest(),
        'proposed_lf_sha256': hashlib.sha256(proposed.encode()).hexdigest(),
        'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
        'status': 'unapplied', 'runtime_modified': False,
        'scope': 'Initialize existing exact-byte native-model memo during sealed construction; no boundary-state capture moved.'}
    with (HERE / 'seal-memo-initialization.manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2); stream.write('\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps(prepare(), indent=2))
