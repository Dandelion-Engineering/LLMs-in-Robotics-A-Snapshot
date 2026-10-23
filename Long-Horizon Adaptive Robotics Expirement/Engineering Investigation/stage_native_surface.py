"""Create an unapplied exact-source-bound exporter patch; never edit Runtime."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
STAGE = HERE / 'Native surface optimization'
RELATIVE = 'Runtime/restart_physical_class.py'
BASE_SHA = '5973b8c43d5fdbdef501dd44e8c2f3094f0c58d38528de01eb9b884f647ee822'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage():
    source = PROJECT / RELATIVE
    if sha(source) != BASE_SHA:
        raise ValueError('Original exporter source guard differs')
    original_bytes = source.read_bytes()
    # read_text normalizes the original CRLF without changing retained bytes.
    original = source.read_text(encoding='utf-8')
    text = original.replace('import math\n', 'import math\nimport struct\nimport weakref\n')
    fragment = (HERE / 'native_surface_memo_fragment.py').read_text(encoding='utf-8').split('\n', 1)[1]
    anchor = '\ndef _mass_properties(model, body_id):\n'
    if text.count(anchor) != 1:
        raise ValueError('Surface insertion anchor differs')
    text = text.replace(anchor, '\n' + fragment + '\n' + anchor)
    old = "        surface = _model_surface(model, seal['mark_indices'])\n        if digest(surface) != seal['compiled_surface_sha256']:\n"
    if text.count(old) != 1:
        raise ValueError('Export replacement anchor differs')
    text = text.replace(old, "        if _model_surface_sha(model, seal) != seal['compiled_surface_sha256']:\n")
    compile(text, str(STAGE / RELATIVE), 'exec')
    target, archived = STAGE / RELATIVE, STAGE / 'original' / RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_bytes(original_bytes)
    target.write_text(text, encoding='utf-8', newline='\n')
    patch = STAGE / 'native-surface.patch'
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
        fromfile='a/' + RELATIVE, tofile='b/' + RELATIVE)), encoding='utf-8', newline='\n')
    manifest = {'schema_version': 'unapplied-native-surface-patch-1', 'applied': False,
        'changed': [{'path': RELATIVE, 'before_sha256': BASE_SHA, 'staged_sha256': sha(target)}],
        'patch_sha256': sha(patch), 'archived_original_sha256': sha(archived),
        'scope': 'Fresh complete model-field comparison with exact bytes; all rich capture call sites and fields unchanged',
        'memo_lifetime': 'Weak model keys; values retain no model reference',
        'performance_measured': False}
    (STAGE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if sha(source) != BASE_SHA:
        raise ValueError('Original exporter changed during staging')
    return manifest


if __name__ == '__main__': print(json.dumps(stage(), indent=2))
