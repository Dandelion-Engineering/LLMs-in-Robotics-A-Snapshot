"""Freeze this already-tested one-shot diagnostic, without launching it."""
import hashlib
import json
from pathlib import Path
import run_event_coverage as helper

out=helper.OUTPUT_ROOT/'event-coverage-20260930-001'
helper.validate_output(out)
test=helper.HERE/'tests-001/receipt.json'
receipt=json.loads(test.read_text(encoding='utf-8'))
assert receipt['passed'] and receipt['admin_commands_simulated'] and receipt['model_calls']==0
tested={r['name']:r['sha256'] for r in receipt['sources']}
sources={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in helper.source_paths().items()}
assert all(tested[name]==digest for name,digest in sources.items())
manifest={'output':str(out),'session':helper.SESSION,'sources':sources,
          'sourcePaths':{name:str(path) for name,path in helper.source_paths().items()},
          'testReceipt':str(test),'testReceiptSha256':hashlib.sha256(test.read_bytes()).hexdigest(),
          'launcherSha256':hashlib.sha256((helper.HERE/'launch_elevated.ps1').read_bytes()).hexdigest(),
          'model_calls':0,'scope':'Exact-loopback-port and PID, ClosePath events, packet capture disabled,16MiB,30s,one owned named session.'}
helper.base.save(helper.HERE/'launch-source-manifest-001.json',manifest)
print(json.dumps(manifest,indent=2))
