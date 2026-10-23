"""Preserve and correct the metadata-only diagnostic presentation."""
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import stage_rows as base

HERE = Path(__file__).resolve().parent
path = base.I / 'qualification_template.html'
before = path.read_bytes()
old = before.decode('utf-8')
new = old
changes = [
    ('<h3>Queue execution failed · no qualification assessment</h3>', '<h3 id="queueMetadataTitle">Queue execution failed · no qualification assessment</h3>'),
    ("const failure=row.queue_failure;$('queueFailurePanel')", "const failure=row.queue_failure||row.queue_completion;$('queueMetadataTitle').textContent=row.queue_completion?'Execution completed · no qualification assessment':'Queue execution failed · no qualification assessment';$('queueFailurePanel')"),
    ("row.status+(row.queue_failure?' · queue execution failure':", "row.status+(row.queue_completion?' · execution only; not assessed':row.queue_failure?' · queue execution failure':"),
    ("row.queue_failure?'No qualification checks were assessed; the queue execution failed.':", "row.queue_completion?'Execution completed. No qualification checks were assessed; no qualification pass or scientific outcome is inferred.':row.queue_failure?'No qualification checks were assessed; the queue execution failed.':"),
    ("row.status+(row.queue_failure?' · queue failure':", "row.status+(row.queue_completion?' · not assessed':row.queue_failure?' · queue failure':"),
]
for source, target in changes:
    assert new.count(source) == 1, source
    new = new.replace(source, target)
source = "DATA.history[selected].queue_failure?$('queueFailurePanel')"
assert new.count(source) == 2
new = new.replace(source, "(DATA.history[selected].queue_failure||DATA.history[selected].queue_completion)?$('queueFailurePanel')")
with (HERE / 'completion-template.before.html').open('xb') as f:
    f.write(before)
with (HERE / 'completion-template.diff').open('x', encoding='utf-8', newline='\n') as f:
    f.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='before/qualification_template.html', tofile='after/qualification_template.html'))
path.write_bytes(new.encode('utf-8'))
base.save(HERE / 'completion-presentation-correction.json', {
    'at': datetime.now(timezone.utc).isoformat(),
    'finding': 'Browser QA of candidate-002 showed completed unassessed diagnostics with an original-verdict label and visible empty timing controls.',
    'before_sha256': base.digest(HERE / 'completion-template.before.html'),
    'after_sha256': base.digest(path),
    'scope': 'Presentation only. Both metadata-only completion and failure use the existing metadata panel; timing remains hidden. No verdict, checks, measurements, source contracts or historical exports are changed.'
})
plan = base.read(HERE / 'candidate-plan-002.json')
plan['directory'] = 'candidate-003'
plan['current_status']['as_of'] = datetime.now(timezone.utc).isoformat()
plan['current_status']['summary'] = 'Smoke 030 completed execution but failed qualification (61 of 62 checks). V32 stopped before either pilot. The reader correction passed 2,731 regressions. Fresh qualification is running after transport, host timing, native reference and boundary checks passed. No scored attempts have started.'
plan['current_status']['engineering_context'] = 'The complete initial Continuity bytes were retained, but the reader did not recognize the exact two-root plain-print command. Its subsequent diagnostic replay leaves the original Smoke 030 verdict unchanged. Every qualification gate must pass on the fresh lineage.'
base.save(HERE / 'candidate-plan-003.json', plan)
print(json.dumps({'corrected': str(path), 'candidate_plan': 'candidate-plan-003.json'}))
