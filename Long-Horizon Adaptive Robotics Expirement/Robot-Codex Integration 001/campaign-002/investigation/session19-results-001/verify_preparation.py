"""Queued report-only checks; never open an active scored attempt's output."""
from pathlib import Path
import difflib
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
INVESTIGATION = HERE.parent
REPO = INVESTIGATION.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / 'preparation-check-001'
    output.mkdir(exist_ok=False)
    tests = []
    for filename in ('test_build.py', 'test_frames.py'):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(INVESTIGATION / filename)],
                                cwd=REPO, capture_output=True, text=True, encoding='utf-8')
        (output / (filename + '.stdout')).write_text(result.stdout, encoding='utf-8')
        (output / (filename + '.stderr')).write_text(result.stderr, encoding='utf-8')
        tests.append({'test': filename, 'exit_status': result.returncode})
        if result.returncode:
            raise RuntimeError(f'{filename} failed: {result.returncode}')
    spec = importlib.util.spec_from_file_location('report_preparation', INVESTIGATION / 'build.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    index = INVESTIGATION / 'qualification-history.json'
    companion = INVESTIGATION / 'session19-history-001/candidate-004/html/qualification-report.html'
    history = report.qualification_history(index, INVESTIGATION, companion)
    assert len(history['attempts']) == 156
    unassessed = [r for r in history['attempts'] if r['status'] == 'completed']
    assert len(unassessed) == 2
    assert all(r['assessment_state'] == 'not_assessed' and r['task_outcome'] == 'unknown'
               and r['scorable'] is False for r in unassessed)
    assert {r['path'] for r in report.READS} == {str(index), str(companion)}
    scope = json.loads((HERE / 'report-edit-scope.json').read_text(encoding='utf-8'))
    snapshot_path = Path(scope['snapshot']['path'])
    assert sha(snapshot_path) == scope['snapshot']['sha256']
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    for name in ('build.py', 'test_build.py'):
        current = INVESTIGATION / name
        assert current.relative_to(REPO).as_posix() not in snapshot['sources']
        before = (HERE / 'original-report-sources' / name).read_text(encoding='utf-8')
        after = current.read_text(encoding='utf-8')
        (output / (name + '.diff')).write_text(''.join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile='before/' + name, tofile='after/' + name)), encoding='utf-8')
    verification = {'schema': 'campaign002-report-preparation-verification-1',
        'verified_at': datetime.now(timezone.utc).isoformat(), 'passed': True, 'tests': tests,
        'history_rows': len(history['attempts']), 'unassessed_rows': [r['run_id'] for r in unassessed],
        'scored_outcomes_consumed': 0, 'frozen_apparatus_changes': 0,
        'inputs': report.READS,
        'source_hashes': {n: sha(INVESTIGATION / n) for n in ('build.py', 'test_build.py', 'test_frames.py')},
        'scope': 'Presentation checks only. No model launch, outcome tuning or change to campaign admission.'}
    (output / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(verification, indent=2))


if __name__ == '__main__':
    main()
