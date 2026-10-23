"""Correct optional staged links only; preserve the failed first plan and batch."""
import copy
import json
import stage_append as s


def main():
    old_path = s.STAGE / 'prerequisites-plan-001.json'
    old = s.read(old_path)
    new = copy.deepcopy(old)
    removed = []
    for row in new['rows']:
        before = row['diagnostic_analyses']
        omit = [v for v in before if 'smoke-024-read-diagnosis-001' in v['path']]
        s.require(len(omit) == 2 and {v['path'].split('\\')[-1] for v in omit} ==
                  {'analysis.json', 'analysis.md'}, 'Unexpected optional diagnosis links')
        row['diagnostic_analyses'] = [v for v in before if v not in omit]
        removed.append({'run_id': row['run_id'], 'links': omit})
    normalized = copy.deepcopy(new)
    for row, prior in zip(normalized['rows'], old['rows']):
        row['diagnostic_analyses'] = prior['diagnostic_analyses']
    s.require(normalized == old, 'Correction changed unrelated staging content')
    s.require(s.bind(s.HISTORY)['sha256'] == old['expected_history_sha256'], 'Canonical changed')
    plan = s.save(s.STAGE / 'prerequisites-plan-002.json', new)
    receipt = s.save(s.STAGE / 'prerequisites-plan-correction-001.json', {
        'schema': 'campaign002-history-staging-plan-correction-1', 'at': s.now(),
        'prior_plan': s.bind(old_path), 'corrected_plan': plan,
        'failed_command': s.bind(s.STAGE / 'stage-prerequisites-001.json'),
        'reason': 'Existing report rejects generic analysis.json/md basenames as separately indexed diagnostic links. Omit optional cross-run links only; do not rename original evidence or change report schema.',
        'removed_optional_links': removed,
        'all_other_plan_content_unchanged': True,
        'source': s.bind(__file__), 'canonical_written': False})
    print(json.dumps({'plan': plan, 'receipt': receipt}, indent=2))


if __name__ == '__main__':
    main()
