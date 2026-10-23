"""Generate an isolated candidate from the retained controller; no installation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / 'harness/native_quiescence.py'

REPLACEMENTS = [
    ("import native_exit_drain\n                self.bounded(lambda: native_exit_drain.before_stdin_close(self), self.graceful,\n                             'transport_pre_exit_drain_failed')",
     "import process_drain\n                self.bounded(lambda: process_drain.native_phase(self, 'prepare'), self.graceful,\n                             'transport_process_prepare_failed')"),
    ("                self.emit('stdin_closed')\n                self.bounded(lambda: self.client.process.wait",
     "                self.emit('stdin_closed')\n                if getattr(self.client.args, 'native_process_ready', None) is not None:\n                    self.bounded(lambda: process_drain.native_phase(self, 'finish'), self.graceful,\n                                 'transport_process_finish_failed')\n                self.bounded(lambda: self.client.process.wait"),
]

def render():
    raw = SOURCE.read_bytes()
    text = raw.decode('utf-8').replace('\r\n', '\n')
    for old, new in REPLACEMENTS:
        if text.count(old) != 1:
            raise ValueError('Retained controller no longer matches the declared change')
        text = text.replace(old, new)
    return raw, text.encode('utf-8')

if __name__ == '__main__':
    before, after = render()
    with (HERE/'candidate_native.py').open('xb') as stream:
        stream.write(after)
    with (HERE/'controller-derivation.json').open('x', encoding='utf-8') as stream:
        json.dump({'source': str(SOURCE), 'source_sha256': hashlib.sha256(before).hexdigest(),
                   'candidate_sha256': hashlib.sha256(after).hexdigest(),
                   'replacements': REPLACEMENTS, 'production_installed': False}, stream, indent=2)
        stream.write('\n')
