"""Build an offline investigation from authenticated Campaign 001 evidence only."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
READS = []
MAX_TRACE_BYTES = 128 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(path, role, expected=None):
    path = Path(path)
    if path.stat().st_size > MAX_TRACE_BYTES:
        raise ValueError('Bounded report read exceeded: ' + str(path))
    raw = path.read_bytes()
    checksum = digest(raw)
    if expected is not None and checksum != expected:
        raise ValueError('Retained evidence hash mismatch: ' + str(path))
    READS.append({'path': str(path.resolve()), 'sha256': checksum, 'bytes': len(raw), 'role': role})
    return raw


def read(path, role, expected=None):
    return json.loads(capture(path, role, expected))


def link(path, output):
    return quote(Path(os.path.relpath(path, output)).as_posix(), safe='/.:')


def bounded(value, limit=10000):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + '\n[Display excerpt; open exact retained source for remaining text.]'


def number(value):
    return type(value) in (float, int) and math.isfinite(value)


def wilson(successes, total, z=1.959963984540054):
    if not total:
        return None
    p, zz = successes / total, z * z
    center = (p + zz / (2 * total)) / (1 + zz / total)
    half = z * math.sqrt(p * (1 - p) / total + zz / (4 * total * total)) / (1 + zz / total)
    return [max(0, center - half), min(1, center + half)]


def aggregate(runs):
    groups = {}
    for family in ['misplaced-stock', 'blocked-insert-home', 'all scheduled slots']:
        selected = runs if family == 'all scheduled slots' else [r for r in runs if r['family'] == family]
        valid = [r for r in selected if r['scorable']]
        successes = sum(r['task_outcome'] == 'success' for r in valid)
        failures = sum(r['task_outcome'] == 'failure' for r in valid)
        unresolved = len(selected) - successes - failures
        assessed = [r for r in selected if r.get('assessment_available') is True]
        observed_successes = sum(r.get('observed_task_outcome') == 'success' for r in assessed)
        observed_failures = sum(r.get('observed_task_outcome') == 'failure' for r in assessed)
        groups[family] = {'planned': len(selected), 'valid': len(valid), 'successes': successes,
            'failures': failures, 'invalid': sum(r['validity'] == 'invalid' for r in selected),
            'not_run': sum(r['execution_status'] == 'not_run' for r in selected),
            'pending': sum(r['execution_status'] == 'pending' for r in selected),
            'unresolved': unresolved, 'wilson95': wilson(successes, len(valid)),
            'all_planned_bounds': [successes / len(selected), (successes + unresolved) / len(selected)] if selected else None,
            'started': sum(r.get('started') is True for r in selected),
            'authenticated_assessments': len(assessed),
            'observed_evaluator_successes': observed_successes,
            'observed_evaluator_failures': observed_failures,
            'observed_evaluator_unknown': len(assessed) - observed_successes - observed_failures,
            'observed_successes_among_invalid': sum(r.get('observed_task_outcome') == 'success'
                                                     and r['validity'] == 'invalid' for r in assessed),
            'operational_completion_all_planned_fraction': observed_successes / len(selected) if selected else None}
    return groups


def trace(path, role, inventory, output):
    root, relative = role.split(':', 1)
    entry = inventory.get((root, relative))
    if entry is None:
        raise ValueError('Trace is absent from admitted evidence inventory: ' + relative)
    raw = capture(path, role, entry['sha256'])
    if len(raw) != entry['bytes']:
        raise ValueError('Trace byte length differs: ' + relative)
    return [(line, json.loads(text)) for line, text in enumerate(raw.decode('utf-8').splitlines(), 1) if text.strip()]


def compact_observation(payload):
    return {key: payload.get(key) for key in ('sequence', 'capture_sim_time_s', 'detections', 'station',
                                              'gripper', 'inspection', 'last_feedback')}


def extract_events(attempt, assessment, output):
    host, orchestrator = Path(attempt['host_evidence']), Path(attempt['evidence'])
    inventory = {(row['root'], row['path']): row for row in assessment['evidence_inventory']}
    history_path = host / 'public-history.jsonl'
    history = trace(history_path, 'protected_host:public-history.jsonl', inventory, output)
    starts = [r for _, r in history if r.get('type') == 'episode_started' and number(r.get('wall_unix_s'))]
    if len(starts) != 1:
        raise ValueError('Cannot align retained episode without a unique timestamped start')
    origin = starts[0]['wall_unix_s']
    events, untimed = [], []
    observations = [(line, row) for line, row in history if row.get('type') == 'observation']
    stride = max(1, math.ceil(len(observations) / 400))
    retained_observations = {line for line, _ in observations[::stride]}
    if observations:
        retained_observations.add(observations[-1][0])
    for line, row in history:
        if row.get('type') == 'observation' and line not in retained_observations:
            continue
        payload = row.get('payload', {})
        if row.get('type') == 'observation':
            payload = compact_observation(payload)
        item = {'lane': 'world', 'kind': row.get('type'), 'event_id': row.get('event_id'),
            'sim_s': row.get('sim_time_s'), 'owner': row.get('owner'), 'epoch': row.get('authority_epoch'),
            'detail': bounded(payload), 'source': link(history_path, output), 'line': line,
            'title': row.get('type', 'protected event') + ' · ' + str(row.get('source', 'unknown source'))}
        wall = row.get('wall_unix_s')
        item['t'] = wall - origin if number(wall) else None
        (events if item['t'] is not None else untimed).append(item)
    broker_path = orchestrator / 'pilot/broker-events.jsonl'
    if broker_path.is_file():
        broker = trace(broker_path, 'orchestrator:pilot/broker-events.jsonl', inventory, output)
        for line, row in broker:
            response = row.get('response', {})
            if isinstance(response, dict):
                summary = {key: response.get(key) for key in ('ok', 'request_id', 'status', 'owner', 'authority_epoch',
                    'sim_time_s', 'error', 'handback', 'verification', 'receipt') if key in response}
            else:
                summary = response
            item = {'lane': 'gateway', 'kind': 'broker', 'title': str(row.get('method')) + ' ' + str(row.get('path'))
                    + ' · HTTP ' + str(row.get('status')), 'detail': bounded({'request': row.get('request'), 'response_summary': summary}),
                'source': link(broker_path, output), 'line': line, 't': row['wall_unix_s'] - origin if number(row.get('wall_unix_s')) else None}
            (events if item['t'] is not None else untimed).append(item)
    client_path = orchestrator / 'pilot/client/events.jsonl'
    if client_path.is_file():
        client = trace(client_path, 'orchestrator:pilot/client/events.jsonl', inventory, output)
        for line, row in client:
            method = row.get('method')
            params = row.get('params') or {}
            item = params.get('item') or {}
            kind = item.get('type')
            if method != 'item/completed' or kind in ('reasoning', 'userMessage'):
                continue
            if kind == 'agentMessage':
                detail, title = item.get('text', ''), 'Model message · ' + str(item.get('phase', 'message'))
            else:
                # Tool requests/results are observed behavior; internal reasoning is never reconstructed.
                detail = {k: v for k, v in item.items() if k not in {'source_base64', 'content'}}
                title = 'Tool · ' + str(kind)
            emitted = row.get('emittedAtMs', params.get('completedAtMs'))
            item = {'lane': 'model', 'kind': kind, 'title': title, 'detail': bounded(detail),
                    'source': link(client_path, output), 'line': line,
                    't': emitted / 1000 - origin if number(emitted) else None}
            (events if item['t'] is not None else untimed).append(item)
    events.sort(key=lambda item: item['t'])
    return {'events': events, 'untimed': untimed, 'origin_wall_unix_s': origin,
        'history_events': len(history), 'history_observations': len(observations),
        'displayed_observations': len(retained_observations),
        'alignment': 'Recorded wall_unix_s and client emittedAtMs share the host wall-clock axis, relative to episode_started. '
            'Native client item completion time is a receipt time, not the start of reasoning or motion. '
            'No timestamp is invented for untimed events. Simulation timestamps are retained separately. '
            'Observations are sampled for display; all non-observation protected events and completed public model/tool items are retained.'}


def load_frames(run_id, assessment_path, receipt_path, output):
    index_path = HERE / 'frames/index.json'
    if not index_path.is_file():
        return {'frames': [], 'frame_status': 'not_exported',
                'frame_reason': 'Original sparse RGB frames have not been exported. No images are reconstructed for this report.'}
    index = read(index_path, 'derived original-frame export index')
    if index.get('schema') != 'campaign001-original-frame-export-1':
        raise ValueError('Wrong original-frame export index schema')
    item = next((row for row in index['runs'] if row['run_id'] == run_id), None)
    if item is None:
        return {'frames': [], 'frame_status': 'not_selected',
                'frame_reason': 'No original frames were exported for this run in the current bounded image package. Its retained event and program evidence remains inspectable.'}
    if item.get('queue_receipt', {}).get('sha256') != digest(receipt_path.read_bytes()) or item.get('assessment', {}).get('sha256') != digest(assessment_path.read_bytes()):
        raise ValueError('Frame export does not bind current authenticated queue and assessment')
    frames = []
    for frame in item.get('frames', []):
        path = Path(frame['rgb_path']).resolve(strict=True)
        if not path.is_relative_to((HERE / 'frames' / run_id).resolve()):
            raise ValueError('Frame export path escapes selected run')
        png = capture(path, 'original retained PNG export', frame['rgb_sha256'])
        if png[:8] != b'\x89PNG\r\n\x1a\n' or len(png) != frame['rgb_bytes']:
            raise ValueError('Frame is not the exact retained PNG')
        frames.append({**frame, 'href': link(path, output)})
    return {'frames': frames, 'frame_status': item['status'], 'frame_reason': item['reason'],
        'frame_coverage': {key: item.get(key) for key in ('capture_count', 'available_count', 'exported_count',
            'availability_counts', 'availability_reason_counts', 'first_capture_sim_s', 'last_capture_sim_s',
            'last_available_capture_sim_s', 'omitted_by_display_selection', 'omitted_by_export_budget')},
        'frame_index_href': link(index_path, output)}


def run_record(attempt, execution_root, output):
    folder = execution_root / attempt['run_id']
    row = {key: attempt[key] for key in ('ordinal', 'run_id', 'family')}
    row.update(execution_status='pending', validity='unknown', task_outcome='not_assessed', scorable=False,
        observed_task_outcome='not_assessed', started=False, assessment_available=False,
        reason='No terminal disposition available at build time.', queue_state='unavailable', events=[], untimed=[],
        commands=[], continuity={}, programs={}, links=[], warnings=[], examples=[], frames=[],
        frame_status='not_assessed', frame_reason='No original images consumed without a completed authenticated attempt.')
    parts = attempt['run_id'].split('-')
    for note in sorted(HERE.glob(''.join(parts[-2:]) + '*-investigation.md')):
        if note.is_file():
            row['links'].append({'label': 'Episode investigation: ' + note.stem,
                                 'href': link(note, output)})
    disposition_path = folder / 'disposition.json'
    if disposition_path.is_file():
        disposition = read(disposition_path, 'slot disposition')
        if disposition.get('run_id') != attempt['run_id']:
            raise ValueError('Disposition run identity mismatch')
        row.update({key: disposition[key] for key in ('execution_status', 'reason') if key in disposition})
        if disposition.get('validity') == 'invalid':
            row['validity'] = 'invalid'  # Diagnostic exclusion is not a task score.
        row['links'].append({'label': 'Slot disposition', 'href': link(disposition_path, output)})
        if row['execution_status'] == 'not_run':
            row['validity'] = 'unknown'
            row['reason'] = disposition.get('reason', 'Predeclared stop; slot not run')
    receipt_path = folder / 'storage/queue-receipt.json'
    if not receipt_path.is_file():
        if row['execution_status'] != 'not_run':
            row['warnings'].append('No official terminal queue receipt; assessment and outcome traces were not opened.')
        return row
    receipt = read(receipt_path, 'official queue receipt')
    job = receipt.get('job', receipt)
    row['queue_state'] = job.get('state', 'unknown')
    row['queue_job_id'] = job.get('id')
    try:
        started_at = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
        row['started'] = started_at.tzinfo is not None
    except (KeyError, ValueError, TypeError, AttributeError):
        pass
    row['links'].append({'label': 'Official queue receipt', 'href': link(receipt_path, output)})
    if job.get('state') != 'succeeded' or type(job.get('exit_status')) is not int or job['exit_status'] != 0:
        if job.get('state') in ('failed', 'cancelled', 'canceled'):
            row.update(validity='invalid', task_outcome='unknown', execution_status='failed')
        row['warnings'].append('Queue did not succeed with integer exit0. Diagnostic disposition only; task outcome and traces were not consumed.')
        return row
    row['queue_verified'] = True
    try:
        first = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
        last = datetime.fromisoformat(job['ended_at'].replace('Z', '+00:00'))
        row['queue_seconds'] = (last - first).total_seconds()
        row['queue_started_at'], row['queue_ended_at'] = job['started_at'], job['ended_at']
    except (KeyError, ValueError, TypeError, AttributeError):
        row['queue_seconds'] = None
    assessment_path = folder / 'assessment.json'
    if not assessment_path.is_file():
        row['warnings'].append('Official queue succeeded; admitted assessment has not been recorded. No score inferred.')
        return row
    assessment = read(assessment_path, 'admitted outcome assessment')
    bindings = assessment.get('bindings', {})
    if (assessment.get('schema') != 'robot-codex-campaign-admitted-assessment-1'
            or assessment.get('run_id') != attempt['run_id'] or assessment.get('queue_job_id') != job.get('id')
            or bindings.get('queue_receipt_sha256') != digest(receipt_path.read_bytes())
            or bindings.get('manifest_sha256') != attempt['manifest']['sha256']):
        raise ValueError('Admitted assessment identity/queue/manifest mismatch: ' + attempt['run_id'])
    row['links'].append({'label': 'Admitted assessment', 'href': link(assessment_path, output)})
    row['links'].append({'label': 'Immutable manifest', 'href': link(attempt['manifest']['path'], output)})
    row.update(validity=assessment['validity'], task_outcome=assessment['task_outcome'],
        observed_task_outcome=assessment.get('observed_task_outcome', 'unknown'), assessment_available=True,
        scorable=assessment.get('scorable') is True, execution_status='completed',
        failed_checks=assessment.get('failed_checks', []), model_disposition=assessment.get('model_disposition'),
        lifecycle=assessment.get('lifecycle'), timing=assessment.get('campaign_timing', assessment.get('time')),
        commands=assessment.get('robot_commands', []), continuity=assessment.get('continuity', {}),
        programs={key: {k: v for k, v in value.items() if k != 'source_base64'}
                  for key, value in assessment.get('program_records', {}).items()},
        outcome_evidence=assessment.get('recovery_and_task_outcome'), scientific_admission=assessment.get('scientific_admission'))
    if row['observed_task_outcome'] not in {'success', 'failure', 'unknown', 'not_assessed'}:
        raise ValueError('Unrecognized observed evaluator outcome')
    if row['scorable'] and (row['validity'] != 'valid' or row['task_outcome'] not in ('success', 'failure')):
        raise ValueError('Scorable assessment has incompatible validity/outcome')
    if not row['scorable']:
        row['task_outcome'] = 'unknown'
    if row['validity'] == 'invalid':
        row['warnings'].append('Infrastructure-invalid evidence: trace shows observed behavior only and is excluded from valid task scoring.')
    try:
        row.update(extract_events(attempt, assessment, output))
        for label, path in [('Protected history', Path(attempt['host_evidence']) / 'public-history.jsonl'),
                            ('Protected command registry', Path(attempt['host_evidence']) / 'command-registry.json'),
                            ('Native model/tool trace', Path(attempt['evidence']) / 'pilot/client/events.jsonl'),
                            ('Broker calls', Path(attempt['evidence']) / 'pilot/broker-events.jsonl'),
                            ('Storage receipt', Path(attempt['storage_receipt']))]:
            if path.is_file():
                row['links'].append({'label': label, 'href': link(path, output)})
    except (ValueError, OSError, KeyError) as error:
        row['events'], row['untimed'] = [], []
        row['warnings'].append('Timeline unavailable: ' + str(error))
    try:
        row.update(load_frames(attempt['run_id'], assessment_path, receipt_path, output))
    except (ValueError, OSError, KeyError) as error:
        row.update(frames=[], frame_status='unavailable_integrity', frame_reason=str(error))
        row['warnings'].append('Original frame panel unavailable: ' + str(error))
    return row


def select_examples(runs):
    for family in ('misplaced-stock', 'blocked-insert-home'):
        selected = [r for r in runs if r['family'] == family]
        if selected:
            selected[0]['examples'].append('Preselected first ' + family)
            selected[-1]['examples'].append('Preselected last ' + family)
        first_failure = next((r for r in selected if r['scorable'] and r['task_outcome'] == 'failure'), None)
        if first_failure:
            first_failure['examples'].append('Outcome-selected first valid failure')
    seen, behavior_seen = set(), set()
    for row in runs:
        if row['validity'] == 'invalid':
            category = tuple(sorted(row.get('failed_checks') or [row.get('reason', 'unknown infrastructure condition')]))
            if category not in seen:
                row['examples'].append('Outcome-selected first instance of infrastructure category')
                seen.add(category)
        # Observed categories select inspection targets, not causal explanations.
        categories = []
        if any(c.get('status') == 'rejected' or c.get('admission', {}).get('status') == 'rejected'
               for c in row.get('commands', [])):
            categories.append('rejected robot request')
        if row.get('continuity', {}).get('final_local_matches_last_commit') is False:
            categories.append('final local continuity differs from protected commit')
        programs = row.get('programs', {})
        program_ids = sorted({program['run_id'] for program in programs.values() if program.get('run_id')})
        row['program_summary'] = {'unique_invocation_count': len(program_ids),
            'invocation_ids': program_ids, 'receipt_count': len(programs),
            'scope': 'Program receipts alone do not establish robot actuation.'}
        if program_ids:
            categories.append('bounded program invocation')
            # This exact source was reviewed in the retained admitted assessment.
            reviewed_utility = '5ed894a33d7555ee5c4e5533885841e903b2ae210fdce69d6369226c66d0876e'
            if all(program.get('source_sha256') == reviewed_utility for program in programs.values()):
                row['program_summary']['scope'] = ('Reviewed exact source: public-history/status observation utility '
                    'with local JSON note writes; no robot actuation calls. This is not a program-control demonstration.')
        for program in programs.values():
            if program.get('record_kind') == 'admission' and program.get('final_record'):
                if not any(Path(name).name == program['final_record'] for name in programs):
                    categories.append('program admission without retained final receipt')
            if program.get('timed_out') is True or program.get('output_limit') is True:
                categories.append('bounded program time/output limit')
        row['inspection_categories'] = list(dict.fromkeys(categories))
        for category in row['inspection_categories']:
            if category not in behavior_seen:
                row['examples'].append('Outcome-selected first behavior: ' + category)
                behavior_seen.add(category)


def stop_summary(runs):
    unrun = [row for row in runs if row['execution_status'] == 'not_run']
    if not unrun:
        return None
    return {'reason': unrun[0]['reason'], 'first_unrun_ordinal': unrun[0]['ordinal'],
            'not_run_count': len(unrun), 'not_run_ids': [row['run_id'] for row in unrun],
            'last_started_ordinal': max((row['ordinal'] for row in runs if row.get('started')), default=None),
            'preselected_unrun_ids': [row['run_id'] for row in unrun
                if any(label.startswith('Preselected') for label in row['examples'])]}


def build(plan_path, output):
    READS.clear()
    output.mkdir(parents=True, exist_ok=True)
    plan = read(plan_path, 'fixed execution plan')
    if plan.get('campaign_id') != 'RCI001-Campaign001' or len(plan['attempts']) != 24:
        raise ValueError('Expected the approved fixed24 Campaign001 plan')
    if [a['ordinal'] for a in plan['attempts']] != list(range(1, 25)):
        raise ValueError('Attempt schedule is not in fixed ordinal order')
    runs = [run_record(a, plan_path.parent / 'execution', output) for a in plan['attempts']]
    select_examples(runs)
    counts = aggregate(runs)
    data = {'schema': 'campaign001-investigation-1', 'built_at': datetime.now(timezone.utc).isoformat(),
        'campaign_id': plan['campaign_id'], 'runs': runs, 'counts': counts,
        'stop': stop_summary(runs),
        'scope': 'Exact RCI001-wsl-010d, GPT-6 Astra Max. Two known development fixtures; 12 scheduled repeats each, world173, noise22001–22024. '
                 'Fresh invocations do not establish statistical independence or generalization.',
        'complete': all(r['execution_status'] != 'pending' for r in runs),
        'plan': link(plan_path, output), 'builder_sha256': digest(Path(__file__).read_bytes())}
    source = (HERE / 'template.html').read_text(encoding='utf-8')
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    rendered = source.replace('/*__REPORT_DATA__*/{}', encoded)
    if rendered == source:
        raise ValueError('Missing report data insertion point')
    (output / 'report.html').write_text(rendered, encoding='utf-8', newline='\n')
    (output / 'data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    provenance = {'schema': 'campaign001-investigation-provenance-1', 'built_at': data['built_at'],
        'builder': {'path': str(Path(__file__)), 'sha256': data['builder_sha256']},
        'template': {'path': str(HERE / 'template.html'), 'sha256': digest((HERE / 'template.html').read_bytes())},
        'report_sha256': digest((output / 'report.html').read_bytes()), 'inputs': READS,
        'verification': {'planned_slots': len(runs), 'scorable': sum(r['scorable'] for r in runs),
            'failed_queue_outcomes_consumed': 0,
            'trace_source_hashes_checked': True, 'historical_pilot_in_report': False},
        'limits': ['Inventory verification covers only the files actually consumed for this report, not all image/numerical bulk.',
            'No external calls or model launches. The report consumes admitted assessments; it does not independently rerun scientific qualification.',
            'Display observations are sampled and long item text is excerpted; exact original files and physical line numbers remain linked.']}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    return {'report': str(output / 'report.html'), 'planned': 24, 'counts': counts,
            'warnings': {r['run_id']: r['warnings'] for r in runs if r['warnings']}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=CAMPAIGN / 'execution-plan.json')
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    print(json.dumps(build(args.plan.resolve(), args.output.resolve()), indent=2))
