"""Independent byte preservation after the actual browser QA; no model calls."""
import json
from pathlib import Path
import sys
from urllib.request import urlopen

HOME = Path(__file__).resolve().parent
sys.path.insert(0, str(HOME.parent))
from common import sha, save


def run():
    root = HOME / 'replays/live-002-002'
    inputs = json.loads((root / 'inputs.json').read_text(encoding='utf-8'))
    build = json.loads((root / 'build.json').read_text(encoding='utf-8'))
    episode = Path(inputs['episode'])
    checks = {}
    checks['all_original_evidence_bytes_unchanged'] = all(
        (episode / name).stat().st_size == value['bytes']
        and sha(episode / name) == value['sha256']
        for name, value in inputs['files'].items())
    checks['all_built_output_bytes_unchanged'] = all(
        (root / name).stat().st_size == value['bytes']
        and sha(root / name) == value['sha256']
        for name, value in build['outputs'].items())
    links = {}
    for name in ('verification.json', 'inputs.json', 'build.json'):
        with urlopen('http://127.0.0.1:8918/' + name, timeout=10) as response:
            raw = response.read()
            links[name] = {'http_status': response.status,
                           'exact_local_bytes': raw == (root / name).read_bytes()}
    checks['three_provenance_links_exact_bytes'] = all(
        item['http_status'] == 200 and item['exact_local_bytes'] for item in links.values())
    receipt = dict(passed=all(checks.values()), checks=checks, links=links,
                   model_calls=0, source_sha256=sha(__file__),
                   original_files=len(inputs['files']), built_outputs=len(build['outputs']),
                   browser_boundary='All three links served HTTP 200 after actual clicks. The in-app browser retained the replay page instead of displaying raw JSON; exact allowlisted event details remain readable inside the replay.')
    save(HOME / 'replay-002-post-browser-check.json', receipt)
    print(json.dumps(receipt), flush=True)
    if not receipt['passed']:
        raise RuntimeError('Post-browser preservation failed')


if __name__ == '__main__':
    run()
