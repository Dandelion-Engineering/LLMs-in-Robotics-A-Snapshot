"""Static and data-integrity QA for the separate qualification companion."""
import argparse
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.urls = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('href', 'src'):
            if attrs.get(key):
                self.urls.append(attrs[key])
        if tag in ('script', 'link', 'img', 'iframe') and ('src' in attrs or 'href' in attrs):
            raise ValueError('Companion must have no external runtime dependencies')


def static_html(html, *, javascript=True):
    structure = Structure()
    structure.feed(html)
    if len(structure.ids) != len(set(structure.ids)):
        raise ValueError('Duplicate HTML identity')
    scripts = re.findall(r'<script>(.*?)</script>', html, flags=re.S)
    if len(scripts) != 1:
        raise ValueError('Exactly one inline script required')
    references = set(re.findall(r"\$\('([^']+)'\)", scripts[0]))
    if references - set(structure.ids):
        raise ValueError('Missing referenced UI identities: ' + str(references - set(structure.ids)))
    if javascript:
        node = shutil.which('node')
        if not node:
            raise ValueError('Node is required for static JavaScript syntax QA')
        with tempfile.TemporaryDirectory(prefix='qualification-js-') as tmp:
            script = Path(tmp) / 'script.js'
            script.write_text(scripts[0], encoding='utf-8')
            result = subprocess.run([node, '--check', str(script)], capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError('JavaScript syntax failed: ' + result.stderr)
    return {'unique_ids': len(structure.ids), 'script_references': len(references),
            'javascript_syntax': 'passed' if javascript else 'not_run', 'external_dependencies': 0}


def diagnostic_links_guard(items, output, source_links, *, context='Qualification'):
    """Verify diagnostic hyperlink bytes only; permit a distinct run identity."""
    if not isinstance(items, list):
        raise ValueError(context + ' diagnostics must remain separate hash-only links')
    source_paths = {(Path(output) / unquote(item['href'])).resolve() for item in source_links}
    source_labels = {item.get('label') for item in source_links} | {'Original assessment'}
    urls, seen, labels = [], set(), set()
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'label', 'href', 'sha256', 'bytes', 'basis'}
                or item.get('basis') != 'diagnostic_link_only' or not isinstance(item.get('label'), str)
                or not item['label'].strip() or item['label'] in labels | source_labels
                or type(item.get('bytes')) is not int or not 0 <= item['bytes'] <= 128 * 1024 * 1024
                or not isinstance(item.get('sha256'), str) or re.fullmatch('[0-9a-f]{64}', item['sha256']) is None
                or not isinstance(item.get('href'), str) or urlparse(item['href']).scheme
                or urlparse(item['href']).netloc or urlparse(item['href']).query or urlparse(item['href']).fragment
                or re.fullmatch(r'.+-(?:analysis|diagnosis)\.(?:md|json)', Path(unquote(item['href'])).name) is None):
            raise ValueError(context + ' diagnostics must remain separate hash-only links')
        path = Path(output) / unquote(item['href'])
        if (not path.is_file() or path.is_symlink() or path.resolve() in seen | source_paths
                or path.stat().st_size > 128 * 1024 * 1024):
            raise ValueError(context + ' diagnostic link unavailable or aliases source evidence')
        raw = path.read_bytes()  # Hash verification only; never parse diagnostic content.
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError(context + ' diagnostic document changed')
        seen.add(path.resolve())
        labels.add(item['label'])
        urls.append(item['href'])
    return urls


def failed_queue_guard(row, output):
    """Check the metadata-only failed-job branch without opening attempt outputs."""
    failure = row.get('queue_failure') or {}
    if (set(failure) != {'schema', 'basis', 'assessment_state', 'queue_job_id', 'official_queue_sha256',
                         'official_queue_href', 'manifest_sha256', 'snapshot_sha256', 'diagnostic_links', 'scope'}
            or failure.get('schema') != 'campaign002-failed-queue-diagnostic-1'
            or failure.get('basis') != 'official_terminal_execution_failure'
            or failure.get('assessment_state') != 'not_assessed'
            or row.get('assessment_state') != 'not_assessed' or row.get('assessment_schema') is not None
            or row.get('status') != 'failed' or row.get('validity') != 'unknown'
            or row.get('scorable') is not False or row.get('task_outcome') != 'unknown'
            or row.get('model_calls') is not None or row.get('queue_state') != 'failed'
            or type(row.get('queue_exit_status')) is not int or row['queue_exit_status'] == 0
            or failure.get('queue_job_id') != row.get('job_id')
            or any(row.get(k) is not None for k in ('timing', 'supervisory_timing', 'recorder_feasibility',
                'protected_io', 'pilot_admission', 'admission_disposition', 'preflight', 'native_reference'))
            or row.get('recorder_subphases_declared') is not False
            or any(row.get(k) != {} for k in ('checks', 'assessment_errors', 'declared_details'))
            or any(row.get(k) != [] for k in ('failed_checks', 'analyses'))
            or row.get('diagnostic_links', []) != []):
        raise ValueError('Failed queue acquired assessment, measurement or outcome evidence')
    try:
        start = datetime.fromisoformat(row['started_at'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(row['ended_at'].replace('Z', '+00:00'))
        if start.tzinfo is None or end.tzinfo is None or not start <= end:
            raise ValueError('Invalid interval')
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError('Failed queue lacks terminal official start/end interval') from error
    labels = {'Official queue receipt': 'official_queue_sha256',
              'Frozen attempt manifest': 'manifest_sha256', 'Frozen source snapshot': 'snapshot_sha256'}
    links = row.get('links', [])
    if len(links) != 3 or {x.get('label') for x in links} != set(labels):
        raise ValueError('Failed queue contains nonmetadata source links')
    paths, documents = {}, {}
    for item in links:
        digest = item.get('sha256')
        url = item.get('href')
        if (not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None
                or digest != failure.get(labels[item['label']]) or not isinstance(url, str)
                or urlparse(url).scheme):
            raise ValueError('Failed queue metadata hash/link binding mismatch')
        path = Path(output) / unquote(url)
        if not path.is_file() or path.is_symlink():
            raise ValueError('Failed queue metadata link unavailable or linked')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Failed queue metadata bytes changed')
        paths[item['label']] = path
        documents[item['label']] = json.loads(raw)
    official = next(x for x in links if x['label'] == 'Official queue receipt')
    if failure.get('official_queue_href') != official['href']:
        raise ValueError('Failed queue receipt link differs from source inventory')
    receipt = documents['Official queue receipt']
    job = receipt.get('job', receipt)
    if (job.get('id') != row['job_id'] or job.get('state') != 'failed'
            or type(job.get('exit_status')) is not int or job['exit_status'] != row['queue_exit_status']
            or job.get('started_at') != row['started_at'] or job.get('ended_at') != row['ended_at']):
        raise ValueError('Failed queue display differs from exact official terminal receipt')
    manifest, snapshot = documents['Frozen attempt manifest'], documents['Frozen source snapshot']
    argv = job.get('argv', [])
    if not isinstance(argv, list) or argv.count('--manifest') != 1 or argv.index('--manifest') + 1 >= len(argv):
        raise ValueError('Failed queue exact manifest dispatch unavailable')
    dispatched = Path(argv[argv.index('--manifest') + 1])
    if not dispatched.is_absolute():
        if not isinstance(job.get('cwd'), str) or not Path(job['cwd']).is_absolute():
            raise ValueError('Failed queue relative manifest lacks absolute working directory')
        dispatched = Path(job['cwd']) / dispatched
    if (dispatched.resolve() != paths['Frozen attempt manifest'].resolve()
            or not paths['Frozen attempt manifest'].name.endswith('-manifest.json')
            or paths['Frozen source snapshot'].name != 'snapshot.json'
            or manifest.get('run_id') != row['run_id'] or manifest.get('framework_revision') != row['revision']
            or snapshot.get('revision') != row['revision']):
        raise ValueError('Failed queue manifest/revision correspondence differs')
    return diagnostic_links_guard(failure.get('diagnostic_links', []), output, links, context='Failed queue')


def failed_queue_closeout_guard(closeout, rows):
    """A failed queue may bind ongoing/blocked engineering, never qualification."""
    basis = next((row for row in rows if row['run_id'] == closeout.get('basis_run_id')), None)
    if basis is None or basis.get('queue_failure') is None:
        return False
    failure = basis['queue_failure']
    if (closeout.get('state') not in ('qualification_failed_blocked', 'qualification_in_progress')
            or closeout.get('basis_assessment_sha256') is not None
            or closeout.get('basis_queue_sha256') != failure['official_queue_sha256']
            or closeout.get('basis_kind') != 'official_terminal_execution_failure_without_assessment'
            or basis is not next((r for r in reversed(rows) if r['status'] in ('passed', 'failed')), None)
            or not any(a.get('sha256') == failure['official_queue_sha256']
                       and a.get('href') == failure['official_queue_href'] for a in closeout.get('links', []))):
        raise ValueError('Failed queue closeout lacks exact latest unassessed receipt basis')
    return True


def verify(output):
    output = Path(output)
    html = (output / 'qualification-report.html').read_text(encoding='utf-8')
    data_raw = (output / 'qualification-data.json').read_bytes()
    data = json.loads(data_raw)
    proof = json.loads((output / 'qualification-provenance.json').read_bytes())
    if hashlib.sha256(html.encode()).hexdigest() != proof['report_sha256'] or hashlib.sha256(data_raw).hexdigest() != proof['data_sha256']:
        raise ValueError('Generated artifact hash mismatch')
    embedded = re.search(r'const DATA = (.*?);\nconst \$', html, flags=re.S)
    if embedded is None or json.loads(embedded.group(1)) != data:
        raise ValueError('Embedded report data differs from the data artifact')
    if (data.get('schema') != 'campaign002-qualification-investigation-1'
            or data.get('empirical_outcome_rows') != 0 or 'runs' in data):
        raise ValueError('Qualification report cannot contain fabricated scored rows')
    counts = data['previous']['counts']
    if [counts.get(k) for k in ('valid', 'successes', 'invalid', 'not_run')] != [6, 6, 4, 14]:
        raise ValueError('Campaign001 fixed counts changed')
    rows = data['history']
    if not rows or len({r['run_id'] for r in rows}) != len(rows):
        raise ValueError('Missing or duplicate history entries')
    urls = [data['previous']['report_href'], data['previous']['data_href'], data['history_href']]
    for row in rows:
        if row['status'] not in ('passed', 'failed', 'cancelled', 'not_run') or row['scorable'] is not False or row['task_outcome'] != 'unknown':
            raise ValueError('Invalid diagnostic classification')
        if row.get('queue_failure') is not None:
            urls.extend(failed_queue_guard(row, output))
        elif row['status'] == 'not_run':
            preflight = row.get('preflight') or {}
            if (row.get('validity') != 'unknown' or row.get('job_id') is not None or row.get('queue_state') is not None
                    or row.get('queue_exit_status') is not None or row.get('started_at') is not None
                    or preflight.get('queue_submitted') is not False or preflight.get('assessment_state') != 'not_assessed'
                    or row.get('timing') is not None or row.get('recorder_feasibility') is not None):
                raise ValueError('Unlaunched preflight acquired a queue result or assessment')
        elif row['status'] == 'cancelled':
            if row['started_at'] is not None or row['queue_state'] not in ('canceled', 'cancelled'):
                raise ValueError('Cancellation was executed')
        elif row['queue_state'] != 'succeeded' or type(row['queue_exit_status']) is not int or row['queue_exit_status'] != 0:
            raise ValueError('Unqualified official receipt')
        if row.get('queue_failure') is None:
            urls.extend(diagnostic_links_guard(row.get('diagnostic_links', []), output, row['links']))
        timing = row.get('timing')
        if timing and timing['basis'] == 'diagnostic_only' and (timing['strict_passed'] is not None or timing['strict_verification_available'] is not False):
            raise ValueError('Raw diagnostics promoted to a strict timing verdict')
        feasibility = row.get('recorder_feasibility')
        pilot = row.get('pilot_admission')
        admission = row.get('admission_disposition')
        if admission and (type(admission.get('admission_passed')) is not bool
                or admission['admission_passed'] is not (row['status'] == 'passed')
                or type(admission.get('original_raw_passed')) is not bool
                or (admission['admission_passed'] and not admission['original_raw_passed'])):
            raise ValueError('History promoted or changed original suite/admission decisions')
        if pilot and (type(pilot.get('admission_passed')) is not bool
                or pilot['admission_passed'] is not (row['status'] == 'passed')
                or (pilot['admission_passed'] and (pilot.get('original_validity') != 'valid'
                    or pilot.get('task_evidence_valid') is not True
                    or pilot.get('assessed_task_outcome') not in ('success','failure')))):
            raise ValueError('Pilot apparatus admission contradicts original task evidence')
        if feasibility and (feasibility.get('production_adopted') is not False
                or feasibility.get('scorable') is not False or feasibility.get('task_outcome') != 'unknown'
                or type(feasibility.get('model_calls')) is not int or feasibility['model_calls'] != 0
                or len(feasibility.get('rounds', [])) != 8 or len(feasibility.get('recovery_checks', [])) != 4
                or feasibility.get('mechanical_feasibility_passed') is not (row['status'] == 'passed')):
            raise ValueError('Synthetic mechanical evidence was pooled, truncated or promoted')
        urls.extend(link['href'] for link in row['links'])
        urls.extend(analysis['href'] for analysis in row['analyses'])
        if timing:
            urls.append(timing['metadata_href'])
            urls.extend(link['href'] for link in timing['samples'])
    for entry in proof['inputs']:
        raw = Path(entry['path']).read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Consumed evidence changed after build: ' + entry['path'])
    inv = data['scored_launch_inventory']
    if (inv['state'] == 'no_scored_launch_recorded') != (not inv['entries']):
        raise ValueError('Launch state contradicts inventoried records')
    closeout = data.get('qualification_closeout')
    if closeout:
        basis = next((row for row in rows if row['run_id'] == closeout['basis_run_id']), None)
        state = closeout.get('state')
        earlier = state in ('qualification_failed_blocked','qualification_in_progress')
        current = not inv['entries'] if earlier else True
        queue_basis = failed_queue_closeout_guard(closeout, rows)
        if (basis is None or state not in ('qualification_failed_blocked','qualification_in_progress',
                                          'qualified_campaign_in_progress','campaign_terminal')
                or (state == 'qualification_failed_blocked' and basis['status'] != 'failed')
                or (state != 'qualification_failed_blocked' and basis is not
                    next((r for r in reversed(rows) if r['status'] in ('passed','failed')),None))
                or (not queue_basis and not any(a['sha256'] == closeout.get('basis_assessment_sha256')
                           and (a['href'].endswith('-assessment.json') or
                                (basis.get('assessment_schema') == 'campaign002-boundary-suite-1'
                                 and a['href'].endswith('suite-result.json'))) for a in basis['links']))
                or closeout['current_for_launch_inventory'] != current
                or data['qualification_state'] != (state if current else 'preserved_qualification_history')):
            raise ValueError('Closeout state contradicts completed evidence or launch inventory')
        if not earlier and (len(set(closeout.get('final_qualification_run_ids', []))) != 5
                            or any(next((r['status'] for r in rows if r['run_id'] == identity),None) != 'passed'
                                   for identity in closeout['final_qualification_run_ids'])):
            raise ValueError('Qualified state lacks five passed final-stage bindings')
        if state == 'campaign_terminal' and (closeout.get('terminal_disposition_count') != 20
                                             or len(closeout.get('terminal_dispositions',[])) != 20):
            raise ValueError('Terminal state lacks twenty terminal disposition bindings')
        urls.extend(item['href'] for item in closeout.get('links', []))
    urls.append(inv['operator_href'])
    urls.extend(e['href'] for e in inv['entries'])
    if inv.get('registration'):
        urls.append(inv['registration']['href'])
    if data.get('empirical_report_href'):
        urls.append(data['empirical_report_href'])
    for url in urls:
        if urlparse(url).scheme or not (output / unquote(url)).is_file():
            raise ValueError('Missing or non-local evidence link: ' + url)
    result = static_html(html)
    result.update({'history_records': len(rows), 'scored_outcome_rows': 0, 'verified_input_records': len(proof['inputs']),
                   'evidence_links': len(urls), 'scope': 'Static syntax, local links and byte integrity; browser layout is a separate check.'})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    result = static_html((HERE / 'qualification_template.html').read_text(encoding='utf-8')) if args.source_only else verify(args.output)
    print(json.dumps(result, indent=2))
