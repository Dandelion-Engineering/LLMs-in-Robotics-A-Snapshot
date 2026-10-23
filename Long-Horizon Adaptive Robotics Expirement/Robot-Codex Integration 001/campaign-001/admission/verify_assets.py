"""Bounded read-only asset/package identity refresh; no simulator/model launch."""
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RCI = HERE.parents[1]
EXP = RCI.parent
REPO = EXP.parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    prior_path = RCI / 'host/session10-verification/assets-001.json'
    prior = json.loads(prior_path.read_text(encoding='utf-8'))
    assets = []
    for row in prior['panda']['entries']:
        path = EXP / 'Runtime 004/vendor/panda' / row['path']
        actual = sha(path)
        assets.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': actual,
                       'matched': actual == row['sha256'] and path.stat().st_size == row['bytes']})
    packages = []
    for row in prior['dependencies']['entries']:
        actual = importlib.metadata.version(row['name'])
        packages.append({'name': row['name'], 'expected_version': row['installed_version'],
                         'actual_version': actual, 'matched': actual == row['installed_version']})
    result = {'schema': 'rci-campaign-asset-refresh-1', 'created_at': datetime.now(timezone.utc).isoformat(),
              'source_sha256': sha(Path(__file__)), 'prior_qualification_sha256': sha(prior_path),
              'assets': assets, 'packages': packages,
              'qualified': all(x['matched'] for x in assets + packages),
              'scope': '80 Panda resources and declared package versions. Generic templates and requirements are independently in the 624-source freeze. Each invocation verifies runtime executables and boundary canaries.'}
    output = HERE / 'asset-refresh-session12.json'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({'qualified': result['qualified'], 'assets': len(assets), 'packages': len(packages)}))
    return 0 if result['qualified'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
