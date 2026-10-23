"""Static artifact QA only; does not automate a browser or bypass URL policy."""
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.hrefs, self.dependencies = [], [], []
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if 'id' in attributes:
            self.ids.append(attributes['id'])
        if tag == 'a' and 'href' in attributes:
            self.hrefs.append(attributes['href'])
        if tag in {'script', 'link', 'img', 'iframe'} and any(k in attributes for k in ('src', 'href')):
            self.dependencies.append(attributes)


def main():
    html = (HERE / 'report.html').read_text(encoding='utf-8')
    data = json.loads((HERE / 'data.json').read_text(encoding='utf-8'))
    doc = Document()
    doc.feed(html)
    scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
    assert len(scripts) == 1
    assert len(doc.ids) == len(set(doc.ids)), 'Duplicate HTML IDs'
    assert not doc.dependencies, 'External dependency present'
    assert len(data['runs']) == 20
    assert [r['ordinal'] for r in data['runs']] == list(range(1, 21))
    preselected = [r['run_id'] for r in data['runs'] if any(x.startswith('Preselected') for x in r['examples'])]
    assert set(preselected) == {'RCI001-C02-stock-01','RCI001-C02-home-01','RCI001-C02-stock-10','RCI001-C02-home-10'}
    selectors = set(re.findall(r"\$\(['\"]#([\w-]+)", scripts[0]))
    assert selectors <= set(doc.ids), 'Script references missing HTML ID'
    links = [href for href in doc.hrefs if not href.startswith('#') and href != 'qa.json']
    links += [data['plan'],data['previous']['report_href'],data['previous']['data_href']]
    if data['qualification'].get('companion_href'):links.append(data['qualification']['companion_href'])
    for attempt in data['qualification']['attempts']:links.extend(x['href'] for x in attempt['links'])
    for run in data['runs']:
        links.extend(x['href'] for x in run['links'])
        links.extend(e['source'] for e in run['events'] + run['untimed'])
        links.extend(frame['href'] for frame in run.get('frames', []))
        assert all(a['t'] <= b['t'] for a, b in zip(run['events'], run['events'][1:])), 'Events not chronological'
        if run['execution_status'] == 'not_run':
            assert not run['events'] and not run.get('frames') and not run['scorable'], 'Unrun slot contains outcome display'
        if run['validity'] == 'invalid':
            assert not run['scorable'] and run['task_outcome'] == 'unknown', 'Invalid diagnostic promoted to score'
        assert len(run.get('frames', [])) <= 32, 'Run exceeds frame display bound'
        for frame in run.get('frames', []):
            raw = (HERE / unquote(frame['href'])).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == frame['rgb_sha256'], 'Displayed PNG hash differs from original'
    frames = [frame for run in data['runs'] for frame in run.get('frames', [])]
    png_bytes = sum(frame['rgb_bytes'] for frame in frames)
    assert png_bytes <= 128_000_000, 'Displayed PNGs exceed aggregate image bound'
    checked_links = set(links)
    missing = [href for href in checked_links if not (HERE / unquote(href)).resolve().is_file()]
    assert not missing, 'Missing linked artifact: ' + ', '.join(missing)
    node = shutil.which('node')
    assert node, 'Node required for JavaScript syntax validation'
    with tempfile.TemporaryDirectory(prefix='static-qa-', dir=HERE) as directory:
        template = (HERE / 'template.html').read_text(encoding='utf-8')
        template_scripts = re.findall(r'<script>(.*?)</script>', template, re.S)
        assert len(template_scripts) == 1
        for name, code in [('inline-script.js', scripts[0]), ('template-script.js', template_scripts[0])]:
            script = Path(directory) / name
            script.write_text(code, encoding='utf-8')
            result = subprocess.run([node, '--check', str(script)], capture_output=True, text=True, check=False)
            assert result.returncode == 0, result.stderr
    result = {'schema': 'campaign002-investigation-static-qa-1',
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'report_sha256': hashlib.sha256((HERE / 'report.html').read_bytes()).hexdigest(),
        'checks': {'inline_javascript_syntax': True, 'unique_html_ids': True,
            'script_target_ids_exist': True, 'self_contained_no_external_dependencies': True,
            'all20_fixed_slots': True, 'four_outcome_independent_preselected_examples': True,
            'all_local_links_exist': True, 'displayed_event_times_nondecreasing': True,
            'unrun_slots_have_no_outcome_display': True, 'invalid_observations_excluded_from_scores': True,
            'all_displayed_png_hashes_match_originals': True, 'image_caps_respected': True},
        'unique_linked_files': len(checked_links),
        'run_status_counts': dict(Counter(r['execution_status'] for r in data['runs'])),
        'displayed_event_count': sum(len(r['events']) for r in data['runs']),
        'displayed_original_pngs': len(frames), 'displayed_png_bytes': png_bytes,
        'browser_visual_and_interaction_qa': 'Not established by static QA; record an actual browser pass separately.',
        'limitations': ['Node --check is syntax verification, not rendering or live control testing.',
                       'Static link, source and syntax checks do not establish visual layout or interaction correctness.']}
    (HERE / 'qa.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
