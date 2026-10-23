"""One bounded, current-state GPU query; no episode, policy, or source changes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime, timezone

out = Path(__file__).with_name('current-gpu-probe.json')
assert not out.exists()
executable = shutil.which('nvidia-smi')
assert executable
command = [executable, '--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits']
started = time.perf_counter()
record = {'schema_version': 'current-gpu-query-probe-1', 'captured_at_utc': datetime.now(timezone.utc).isoformat(),
          'command': command, 'timeout_s': 2.0, 'repetitions': 1,
          'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scope': 'Current isolated read-only GPU query, while no experiment runs. Does not prove past cause, future responsiveness, or readiness under load.'}
try:
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=2.0,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    record.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr, error=None)
except Exception as exc:
    record.update(returncode=None, stdout=None, stderr=None, error=f'{type(exc).__name__}: {exc}')
record['total_wall_duration_s'] = time.perf_counter() - started
record['completed_successfully'] = record['returncode'] == 0 and bool(record['stdout'])
with out.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(record, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps({'output': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
                  'completed_successfully': record['completed_successfully'], 'total_wall_duration_s': record['total_wall_duration_s']}))
