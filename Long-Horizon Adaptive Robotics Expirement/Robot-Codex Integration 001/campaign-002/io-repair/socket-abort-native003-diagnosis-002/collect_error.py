"""Bounded terminal error notification metadata only."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native003_projection', HERE / 'collect.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def main():
    assert not (HERE / 'terminal-error-metadata.json').exists()
    spec = importlib.util.spec_from_file_location('native003_error_auth', m.C / 'qualification/run_final_qualification_v28.py')
    c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
    job = c.official(m.JOB)
    assert job['id'] == m.JOB and job['state'] == 'failed' and type(job['exit_status']) is int and job['exit_status'] == 1
    path = m.STAGE / 'client/events.jsonl'
    assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 16 * 1024 * 1024
    before = m.identity(path)
    selected, skipped_large, count, total = [], [], 0, 0
    prefix = re.compile(rb'^\{"kind": "notification", "method": "(error|turn/completed)"[,}]')
    with path.open('rb') as stream:
        for count, line in enumerate(stream, 1):
            total += len(line)
            assert count <= 20000 and total <= 16 * 1024 * 1024
            match = prefix.match(line[:128])
            if not match:
                continue
            if len(line) > 65536:
                skipped_large.append(count); continue
            value = json.loads(line)
            params = value.get('params') or {}
            turn = params.get('turn') or {}
            error = params.get('error') or turn.get('error') or {}
            info = error.get('codexErrorInfo') if isinstance(error, dict) else None
            allowed = ('usageLimitExceeded', 'rateLimitExceeded', 'contextWindowExceeded',
                       'modelCap', 'serverOverloaded', 'responseStreamConnectionFailed', 'httpConnectionFailed')
            code = info if isinstance(info, str) and info in allowed else None
            text = json.dumps(error).lower()
            selected.append({'line': count, 'line_sha256': hashlib.sha256(line).hexdigest(),
                'method': match.group(1).decode(), 'known_error_code': code,
                'unknown_error_code_present': info is not None and code is None,
                'usage_limit_phrase': 'usage limit' in text or 'usage_limit' in text,
                'rate_limit_phrase': 'rate limit' in text or 'rate_limit' in text,
                'turn_failed': turn.get('status') == 'failed'})
    assert m.identity(path) == before
    result = {'schema': 'campaign002-terminal-error-metadata-1', 'run_id': m.RUN, 'queue_job_id': m.JOB,
        'official_state': job['state'], 'official_exit_status': job['exit_status'],
        'source': before, 'selected': selected, 'skipped_selected_over_bound': skipped_large,
        'total_lines': count, 'total_bytes': total, 'input_unchanged': True,
        'collector': m.identity(Path(__file__)), 'method': m.identity(HERE / 'EVENT_ERROR_METHOD.md'),
        'task_outcome': 'unknown', 'diagnostic_only': True}
    m.save('terminal-error-metadata.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
