"""Refresh the exact previously qualified physical assets and environment."""
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PRIOR=HERE.parents[1]/'campaign-001/admission/asset-refresh-session12.json'
PRIOR_SHA='5b6963a30e5a3a9fd5eb905fa2f8df8c686f1ec733066147461e118db63450c5'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    if sha(PRIOR)!=PRIOR_SHA:raise ValueError('Original qualified asset manifest changed')
    original=json.loads(PRIOR.read_text(encoding='utf-8'));assets=[];packages=[]
    for row in original['assets']:
        path=Path(row['path']);actual=sha(path)
        assets.append({'path':str(path),'bytes':path.stat().st_size,'sha256':actual,
                       'matched':actual==row['sha256'] and path.stat().st_size==row['bytes']})
    for row in original['packages']:
        actual=importlib.metadata.version(row['name'])
        packages.append({'name':row['name'],'expected_version':row['expected_version'],'actual_version':actual,
                         'matched':actual==row['expected_version']})
    value={'schema':'rci-campaign-asset-refresh-1','created_at':datetime.now(timezone.utc).isoformat(),
       'source_sha256':sha(__file__),'prior_qualification_sha256':PRIOR_SHA,'assets':assets,'packages':packages,
       'qualified':len(assets)==80 and len(packages)==10 and all(row['matched'] for row in assets+packages),
       'scope':'Exact original physical asset set and Python dependencies; current file hashes, no model download or replacement'}
    with (HERE/'asset-refresh.json').open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({'qualified':value['qualified'],'assets':len(assets),'packages':len(packages)}))
    return 0 if value['qualified'] else 1

if __name__=='__main__':raise SystemExit(main())
