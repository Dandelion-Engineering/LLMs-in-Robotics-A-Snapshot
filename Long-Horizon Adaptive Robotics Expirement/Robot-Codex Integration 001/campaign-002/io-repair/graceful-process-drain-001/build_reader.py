"""Generate a separate transport reader; preserve every existing transport check."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]/'assessment/transport_integrity_v3.py'
REPLACEMENTS = [
    ('import pre_exit_integrity', 'import process_integrity as pre_exit_integrity'),
    ('REPO = Path(__file__).resolve().parents[4]', 'REPO = Path(__file__).resolve().parents[5]'),
    ("result['native_pre_exit_drain'] = pre_exit", "result['native_process_drain'] = pre_exit"),
]

def render():
    raw = SOURCE.read_bytes(); text = raw.decode('utf-8').replace('\r\n', '\n')
    for old, new in REPLACEMENTS:
        if text.count(old) != 1: raise ValueError('Original reader differs')
        text = text.replace(old, new)
    return raw, text.encode('utf-8')

if __name__ == '__main__':
    before, after = render()
    with (HERE/'candidate_transport.py').open('xb') as stream: stream.write(after)
    with (HERE/'reader-derivation.json').open('x', encoding='utf-8') as stream:
        json.dump({'source': str(SOURCE), 'source_sha256': hashlib.sha256(before).hexdigest(),
                   'candidate_sha256': hashlib.sha256(after).hexdigest(),
                   'replacements': REPLACEMENTS, 'production_installed': False}, stream, indent=2)
        stream.write('\n')
