"""Add one failed development result, retaining the independent trace outcome."""
import json
from pathlib import Path
import subprocess
import sys
import collect_assess as a


def main():
    job = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B',
        str(a.common.QUEUE), 'status', a.JOB], text=True, encoding='utf-8'))
    assert job == a.common.read(a.HERE / 'authentication.json')['official_job']
    assert job['state'] == 'failed' and type(job['exit_status']) is int and job['exit_status'] == 1
    map_root = a.common.SNAPSHOT.parents[2]
    prefix = {n: (map_root / n).read_bytes() for n in
        ('architectures.jsonl', 'revisions.jsonl', 'runs.jsonl', 'results.jsonl', 'notes.jsonl')}
    assert not any(json.loads(line)['run_id'] == a.common.RUN for line in prefix['results.jsonl'].splitlines())
    assert not (a.HERE / 'settlement.json').exists()
    reason = ('The sole interruption diagnostic failed its native pre-exit drain deadline; '
        'genuine channel EOF was absent. The first matched OS abort followed forced owned retirement, '
        'not the earlier thread-closed notification. Trace collection independently passed11 checks '
        'with real helper exit0. Original10053 was not reproduced; no runtime qualification or task assessment.')
    result = {'run_id': a.common.RUN, 'framework_revision': a.common.REVISION,
        'ended_at': job['ended_at'], 'diagnostic_only': True, 'scorable': False, 'task_outcome': 'unknown',
        'assessment_state': 'infrastructure_only', 'reason': reason,
        'analysis': a.binding(a.HERE / 'analysis.json'), 'ordering': a.binding(a.HERE / 'ordered-analysis.json'),
        'findings': a.binding(a.HERE / 'FINDINGS.md'), 'elevation': a.binding(a.common.ROOT / 'observer-elevation-receipt.json')}
    a.save(a.HERE / 'official-status.json', job)
    a.save(a.HERE / 'terminal-result.json', result)
    registry = a.common.load(a.common.CAMPAIGN / 'registry.py', 'diagnostic005_registry')
    original = registry.common
    def record_common(identifier):
        record = original(identifier)
        record['author'] = 'Codex session 19'
        return record
    registry.common = registry.prior.common = record_common
    completed = registry.finish(a.common.RUN, a.HERE / 'terminal-result.json',
        a.HERE / 'official-status.json', 'invalid', 'unknown', reason, 'failed')
    preserved = {}
    for name, raw in prefix.items():
        current = (map_root / name).read_bytes()
        assert current.startswith(raw)
        if name != 'results.jsonl': assert current == raw
        else: assert len(current[len(raw):].splitlines()) == 1
        preserved[name] = {'prefix_bytes': len(raw), 'prefix_sha256': a.common.sha(map_root / name)
            if current == raw else __import__('hashlib').sha256(raw).hexdigest(), 'preserved': True}
    a.save(a.HERE / 'settlement.json', {'result': completed, 'preservation': preserved})
    print(json.dumps(completed))


if __name__ == '__main__':
    main()
