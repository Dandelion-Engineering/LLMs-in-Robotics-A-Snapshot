"""UNAPPLIED local validation reuse proposal; never writes Runtime.

Do not execute tests or patch generation during the construction source hold.
Root will measure the actual compact representation before any integration.
"""
import difflib
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parents[1] / 'Runtime' / 'restart_state.py'
BASE_SHA256 = '324504b47198f46e1b33298708035ae6266f68f5a4a4eab655d81cf8ae43bb30'

OLD = "        blockers=sorted(o['id'] for o in snapshot['geometry']['objects'] if o['id']!=obj['id'] and any(overlaps(o['bounds'],box) for box in corridors))\n"
NEW = """        blockers=[]
        for other in snapshot['geometry']['objects']:
            if other['id']==obj['id']:continue
            bounds=other['bounds']
            if valid_box(bounds) and any(
                    all(min(bounds['max'][i],box['max'][i])-max(bounds['min'][i],box['min'][i])>1e-6
                        for i in range(3)) for box in corridors):
                blockers.append(other['id'])
        blockers.sort()
"""


def candidate_source(source):
    newline = '\r\n' if '\r\n' in source else '\n'
    old, new = OLD.replace('\n', newline), NEW.replace('\n', newline)
    if hashlib.sha256(source.encode('utf-8')).hexdigest() != BASE_SHA256 or source.count(old) != 1:
        raise ValueError('Exact route-validation proposal base changed')
    return source.replace(old, new, 1)


def patch_bytes():
    raw = TARGET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('Runtime base bytes changed')
    source = raw.decode('utf-8')
    relative = 'Long-Horizon Adaptive Robotics Expirement/Runtime/restart_state.py'
    return ''.join(difflib.unified_diff(source.splitlines(True), candidate_source(source).splitlines(True),
                                      fromfile=relative, tofile=relative)).encode('utf-8')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--write-patch']:
        raise SystemExit('Only --write-patch is supported; Runtime application is not implemented')
    output = HERE / 'pending-route-validation.patch'
    with output.open('xb') as stream:
        stream.write(patch_bytes())
    print(str(output))
