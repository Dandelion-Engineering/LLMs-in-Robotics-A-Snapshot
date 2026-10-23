"""Read-only documentation/reference and Git byte-roundtrip verification."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
from attempts import HERE, APP, REPO, read, sha

index = read(HERE / 'evidence-index.json')
sources = {}
for name, expected in index['final_source'].items():
    path = APP / name
    assert sha(path) == expected, path
    relative = path.relative_to(REPO).as_posix()
    raw = subprocess.check_output(['git', 'hash-object', '--no-filters', str(path)], text=True).strip()
    filtered = subprocess.check_output(['git', 'hash-object', '--path=' + relative, str(path)], text=True).strip()
    assert raw == filtered, relative
    sources[name] = dict(sha256=expected, git_blob=raw, clean_filter_preserves_bytes=True)

def references(value):
    if isinstance(value, dict):
        if value.get('state') == 'available' and 'uri' in value and value.get('sha256'):
            assert sha(Path(value['uri'])) == value['sha256'], value['uri']
        for child in value.values(): references(child)
    elif isinstance(value, list):
        for child in value: references(child)

references(index)
references(read(HERE / 'timings.json'))
documents = [HERE / name for name in ('DECISION.md', 'STATUS.md', 'SOURCE-REVIEW.md', 'RECOVERY-OPTIONS.md')]
documents += [APP / 'README.md', REPO / 'agents/Codex/README.md',
              REPO / 'agents/Codex/Session Summaries/HumanReport38.md',
              REPO / 'agents/Codex/Summary of Only Necessary Context.md',
              REPO / 'chats/Codex-Human/Apartment v3 Workspace Startup and Cleanup Repair/Summary.md']
links = 0
for path in documents:
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'): continue
        assert (path.parent / unquote(target.split('#')[0])).exists(), (path, target)
        links += 1
print(json.dumps(dict(passed=True, document_links=links, sources=sources), indent=2))
