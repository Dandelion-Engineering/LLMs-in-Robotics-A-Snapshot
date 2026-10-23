"""Once-only append of the final engineering decision after both final passes."""
from attempts import HERE, ROOT, base, append, read, ref

for name in ('qualification008', 'audit002'):
    terminal = read(HERE / (name + '-terminal.json'))
    assert terminal['state'] == 'succeeded' and type(terminal['exit_status']) is int and terminal['exit_status'] == 0
    assert read(ROOT / name / 'output/result.json')['passed'] is True

append('note', base() | dict(
    id='APARTMENT-workspace-engineering-decision-s38',
    target_ids=['APARTMENT-s38-qualification008-result', 'APARTMENT-s38-audit002-result',
                'APARTMENT-v3-baseline-infrastructure-stop-result'],
    claim_type='decision', supersedes_note_id=None,
    body='Isolated workspace startup/cleanup repair passed final qualification008 (14 startup/retirement cases, four construction/admission failures, original failure reproductions, deadline checks and six isolation gates) and separately implemented audit002 (seven groups). The audit independently rehashed all 75,407 official v2/v3 files unchanged, verified checkpoint 14 and the completed prefix, and found no matching live service/mount or retained log-handle leak. Original startup exceeded the 20-second gate with checkpoint-size state; native Windows preparation gives modest descriptive improvement, while verified slow progress is now bounded by no-progress and total admission budgets. Constructor ownership and the closed-journal follow-up race were reproduced and repaired. Qualifications 001-005 remain failed. Qualification001 was a fault-injector syntax error, correcting the earlier terse result description; the exact external owner of the progress-file rename conflict in qualifications003/004 was not established. Qualifications006/007 and audit001 are distinct earlier passes. The source is an engineering candidate with stale official commissioning. No model, official recovery/condition launch, comparison or monitor restart occurred. Recommend a fresh pristine matched pair only after later authority and full commissioning. Recovery requires a separately qualified source-transition policy and explicit scientific lineage/learning-continuation authority; preserve the original all_retired=false receipt and unchanged guard.',
    evidence=[ref(label, HERE / name) for label, name in (
        ('Decision and limitations', 'DECISION.md'),
        ('Source review', 'SOURCE-REVIEW.md'),
        ('Future lineage options', 'RECOVERY-OPTIONS.md'),
        ('Before/after timing definitions and evidence', 'timings.json'),
        ('Exact source, queues and retained attempts', 'evidence-index.json'),
        ('Final independent audit', 'audit002-result.json'))]))
