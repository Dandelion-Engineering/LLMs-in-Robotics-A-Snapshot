from pathlib import Path
import sys,shutil,json
import test_transport
t=test_transport.TransportChecks('test_actual_queued_status_loses_epoch_after_operator_retirement')
t.setUp()
try:
 t.test_actual_queued_status_loses_epoch_after_operator_retirement()
 for name in ['mirror-requests.jsonl','mirror-replies.jsonl','authority-revocation.json','broker-requests.jsonl','broker-events.jsonl','stage-result.json','runtime-input-hashes.json','paired-history.json','paired-registry.json']:
  shutil.copyfile(t.value.evidence/name,Path(sys.argv[1])/name)
 print(json.dumps({'fixture':'actual queued HTTP GET and source Supervisor retirement','passed':True}))
finally:t.doCleanups()
