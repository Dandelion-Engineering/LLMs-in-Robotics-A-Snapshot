"""Index retained attempts and register the final interpretation; never reruns them."""
from attempts import HERE, ROOT, base, ref, read, save, append, build

names = ['matrix001', 'matrix002', 'history001', 'verification001',
         'history002', 'commissioning001', 'preservation001']
attempts = []
for name in names:
    q = read(HERE / (name + '-terminal.json'))
    result = read(ROOT / name / 'output/result.json')
    attempts.append(dict(name=name, run_id='APARTMENT-cup-' + name,
        queue_id=q['id'], execution_state=q['state'], exit_status=q['exit_status'],
        reported_passed=result.get('passed'),
        manifest=ref('Immutable attempt manifest', ROOT/name/'manifest.json'),
        output=ref('Retained result inventory', ROOT/name/'output/result.json'),
        terminal=ref('Terminal queue receipt', HERE/(name+'-terminal.json'))))
save(HERE/'evidence-index.json', dict(
    scope='Session 36 engineering only; original v2 histories are preserved',
    candidate_commissioned=False, official_prepared=False, official_launched=False,
    qualification_retried=False, attempts=attempts,
    distinction='verification001 passed its physics gates; commissioning001 failed retained endpoint; preservation001 checks only original evidence'))

append('note', base() | dict(id='APARTMENT-cup-investigation-session36',
    target_ids=['APARTMENT-v2-maps'] + ['APARTMENT-cup-'+n+'-result' for n in names],
    supersedes_note_id=None, claim_type='interpretation',
    body='Controlled isolated tests reproduce unforced cup acceleration and implicate convex support-contact precision plus missing rolling resistance. The retained two-attribute candidate preserves cylinder geometry and passes 29 fixed verification groups. Independent commissioning then fails: the planned 7200-second case last retains 7199.963999857391 seconds, a 36.000143 ms endpoint gap caused by the diagnostic sampling schedule. This is an evidence-recording failure, not a failed observed physics gate. Later commissioning source/environment gates were not reached; no certificate, pristine pair, official launch or retry occurred. Randy\'s explicit stop rule ends this session pending later direction. Original-history reconstruction identifies carry losses and two floor-motion bathroom trips, while distinguishing observed outputs from interpretation. Separate closeout preservation passes for all 42359 original condition files, 21 protected anchors and 266 frozen source files. Original Baseline remains completed at 21/21 in 36 sessions; Maps remains at checkpoint 22 with 2/21. No scientific condition comparison is performed.',
    evidence=[ref('Decision and next options', HERE/'DECISION.md'),
              ref('Original-history chronology and limitations', HERE/'HISTORY.md'),
              ref('All seven attempts', HERE/'evidence-index.json'),
              ref('Exact commissioning blocker', HERE/'commissioning-blocker.json'),
              ref('Controlled source delta', HERE/'source-delta.json'),
              ref('Contact geometry readback', HERE/'contact-geometry-readback.json')]))
build()
