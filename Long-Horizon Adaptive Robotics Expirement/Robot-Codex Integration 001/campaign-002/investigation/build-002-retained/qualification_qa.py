"""Static and data-integrity QA for the separate qualification companion."""
import argparse
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
        if row['status'] == 'not_run':
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
        timing = row.get('timing')
        if timing and timing['basis'] == 'diagnostic_only' and (timing['strict_passed'] is not None or timing['strict_verification_available'] is not False):
            raise ValueError('Raw diagnostics promoted to a strict timing verdict')
        feasibility = row.get('recorder_feasibility')
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
