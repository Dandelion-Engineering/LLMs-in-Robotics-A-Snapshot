"""Freeze tested sources and a fresh session identity; never launches."""
import hashlib
import json
import uuid
import run_direct_coverage as h

out=h.OUTPUT_ROOT/'host-coverage-20260930-001'
h.validate_output(out)
test=h.HERE/'tests-001/receipt.json'
receipt=json.loads(test.read_text(encoding='utf-8'))
assert receipt['passed'] and receipt['etw_apis_simulated'] and receipt['model_calls']==0
tested={r['name']:r['sha256'] for r in receipt['sources']}
sources={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in h.source_paths().items()}
assert all(tested[name]==digest for name,digest in sources.items())
manifest={'output':str(out),'session':h.SESSION,'guid':str(uuid.uuid4()),'sources':sources,
    'sourcePaths':{name:str(path) for name,path in h.source_paths().items()},
    'testReceipt':str(test),'testReceiptSha256':hashlib.sha256(test.read_bytes()).hexdigest(),
    'launcherSha256':hashlib.sha256((h.HERE/'launch_elevated.ps1').read_bytes()).hexdigest(),
    'assessmentSha256':hashlib.sha256((h.HERE/'assess_direct.py').read_bytes()).hexdigest(),
    'model_calls':0,'scope':'PROPOSED host-scope six-event socket closure metadata; no packet contents;16MiB;30seconds;explicit human scope decision required.'}
h.base.save(h.HERE/'launch-source-manifest-001.json',manifest)
print(json.dumps({'prepared':True,'output':str(out),'guid':manifest['guid'],'source_count':len(sources)},indent=2))
