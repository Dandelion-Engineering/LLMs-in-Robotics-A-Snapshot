"""Bind completed no-model controls and verify unchanged dev097 source bytes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SNAPSHOT = HERE.parents[3]/'Architecture Map/releases/RCI001-C02-dev-097/snapshot.json'

def binding(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def main():
    frozen = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    for name, identity in frozen['sources'].items():
        if binding(REPO/name) != identity: raise ValueError('Prior source changed: '+name)
    controls = json.loads((HERE/'controls-001/receipt.json').read_text(encoding='utf-8'))
    if controls['all_controls_passed'] is not True or len(controls['cases']) != 8:
        raise ValueError('Windows socket controls differ')
    for name, count in (('tests-001.txt', 11), ('reader-tests-001.txt', 9)):
        text = (HERE/name).read_text(encoding='utf-8')
        if 'Ran '+str(count)+' tests' not in text or not text.rstrip().endswith('OK'):
            raise ValueError('Control result absent')
    paths = sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    result = {'schema': 'campaign002-graceful-process-drain-readiness-1',
              'windows_socket_controls': 8, 'harness_controls': 11, 'independent_reader_controls': 9,
              'all_passed': True, 'native_tested': False, 'qualification_claim': False,
              'prior_source_count': len(frozen['sources']), 'prior_sources_unchanged': True,
              'prior_snapshot': binding(SNAPSHOT),
              'inputs': {p.relative_to(HERE).as_posix(): binding(p) for p in paths}}
    with (HERE/'readiness.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'inputs'}))

if __name__ == '__main__': main()
