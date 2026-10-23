"""Targeted supplement: compare mapping values, not only binding keys."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent.parent


def identity(path):
    raw = path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


if __name__ == '__main__':
    output = HERE / 'binding-objects-supplement.json'
    if output.exists():
        raise RuntimeError('Already verified; do not overwrite')
    old_path = C / 'registration/session14-accounting.json'
    new_path = C / 'registration/session15-accounting.json'
    before = [identity(old_path), identity(new_path)]
    old = json.loads(old_path.read_text(encoding='utf-8'))['source_bindings']
    new = json.loads(new_path.read_text(encoding='utf-8'))['source_bindings']
    assert type(old) is dict and type(new) is dict
    assert len(old) == 913 and len(new) == 960
    missing = sorted(set(old) - set(new))
    changed = sorted(key for key, value in old.items() if key in new and new[key] != value)
    assert not missing and not changed, (missing, changed)
    assert before == [identity(old_path), identity(new_path)]
    record = {'passed':True,'at':datetime.now(timezone.utc).isoformat(),
              'correction':'The first final validator iterated a dict as keys while its comment described whole binding objects. That check only established key preservation. This targeted supplement independently compares every prior mapping value, including all fields. Original validation and accounting artifacts remain unchanged.',
              'prior_validator':identity(HERE / 'validate_handoff.py'),
              'prior_validation':identity(HERE.parent / 'session15-final-validation.json'),
              'accounting_inputs':before,'prior_objects_equal':913,'current_objects':960,
              'missing_keys':missing,'changed_objects':changed,'inputs_unchanged':True}
    with output.open('x',encoding='utf-8') as stream:
        json.dump(record,stream,indent=2);stream.write('\n')
    print(json.dumps({'passed':True,'prior_objects_equal':913,'current_objects':960,'receipt':identity(output)}))
