"""Register this diagnostic's narrow verified result; no campaign admission."""
import json
import subprocess
import sys
import collect as a

def main():
    job = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B',
        str(a.common.QUEUE), 'status', a.JOB], text=True, encoding='utf-8'))
    assert job == a.common.read(a.HERE/'authentication.json')['official_job']
    assert job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
    a.common.validate(a.common.MANIFEST, a.common.SNAPSHOT)
    analysis = a.common.read(a.HERE/'analysis.json')
    assert analysis['full_transport_proof']['passed'] is True
    assert a.binding(a.HERE/'transport-proof.json') == analysis['full_transport_proof']['binding']
    root = a.common.SNAPSHOT.parents[2]
    prefix = {n:(root/n).read_bytes() for n in
              ('architectures.jsonl', 'revisions.jsonl', 'runs.jsonl', 'results.jsonl', 'notes.jsonl')}
    assert not any(json.loads(line)['run_id'] == a.common.RUN for line in prefix['results.jsonl'].splitlines())
    reason = ('One prospective graceful process-drain diagnostic passed complete independent native/transport '
        'and two-phase ordering checks, with genuine EOF, complete bytes and normal exit0 within the original '
        'deadline. No earlier10053 cause, repeatability, timing qualification, task success or campaign admission claim.')
    result = {'run_id': a.common.RUN, 'framework_revision': a.common.REVISION,
        'ended_at': job['ended_at'], 'diagnostic_only': True, 'scorable': False, 'task_outcome': 'unknown',
        'qualification_claim': False, 'assessment_state': 'infrastructure_only', 'reason': reason,
        'analysis': a.binding(a.HERE/'analysis.json'), 'transport_proof': a.binding(a.HERE/'transport-proof.json'),
        'findings': a.binding(a.HERE/'FINDINGS.md')}
    a.common.save(a.HERE/'terminal-result.json', result)
    registry = a.common.load(a.common.CAMPAIGN/'registry.py', 'diagnostic006_result_registry')
    original = registry.common
    def stamp(identifier):
        value = original(identifier); value['author'] = 'Codex session 19'; return value
    registry.common = registry.prior.common = stamp
    completed = registry.finish(a.common.RUN, a.HERE/'terminal-result.json',
        a.HERE/'official-status.json', 'valid', 'unknown', reason, 'completed')
    preserved = {}
    for name, raw in prefix.items():
        current = (root/name).read_bytes()
        assert current.startswith(raw)
        assert len(current[len(raw):].splitlines()) == (1 if name == 'results.jsonl' else 0)
        preserved[name] = {'prefix_bytes': len(raw), 'prefix_sha256': a.hashlib.sha256(raw).hexdigest(), 'preserved': True}
    a.common.save(a.HERE/'settlement.json', {'result': completed, 'preservation': preserved})
    print(json.dumps(completed))

if __name__ == '__main__': main()
