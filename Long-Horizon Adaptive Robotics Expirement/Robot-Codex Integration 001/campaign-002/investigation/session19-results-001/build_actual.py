"""Build terminal artifacts through the shared queue; preserve every build."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
I = HERE.parent
C = I.parent
REPO = I.parents[3]
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def binding(p):
    raw = p.read_bytes()
    return {'path':str(p.resolve()), 'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw)}

def run(args):
    out = HERE / args.directory
    assert out.parent == HERE and not out.exists()
    plan = load(C/'execution-plan.json')
    stop = load(C/'execution/campaign-stop.json')
    assert len(plan['attempts']) == 20 and stop['remaining_admission_authorized'] is False
    receipts = {}
    for row in plan['attempts']:
        folder = C/'execution'/row['run_id']
        disposition = load(folder/'disposition.json')
        assert disposition['execution_status'] in {'completed','failed','not_run','timed_out','aborted','cancelled','canceled'}
        if disposition['execution_status'] == 'not_run':
            assert not (folder/'queue-submit.json').exists()
            continue
        submitted = load(folder/'queue-submit.json')
        jid = submitted.get('job',submitted)['id']
        receipt = json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',jid], text=True,encoding='utf-8'))
        assert receipt['state'] in {'succeeded','failed','cancelled','canceled'}
        if disposition['execution_status'] == 'completed':
            assert receipt['state'] == 'succeeded' and type(receipt['exit_status']) is int and receipt['exit_status'] == 0
        receipts[jid] = receipt
    out.mkdir()
    (out/'official-terminal-jobs.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
    commands = []
    if args.export_frames:
        snapshot = REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-114/snapshot.json'
        commands.append([str(I/'export_frames.py'),'--plan',str(C/'execution-plan.json'),'--snapshot',str(snapshot)])
    commands += [[str(I/'build.py'),'--plan',str(C/'execution-plan.json'),'--qualification-index',str(I/'qualification-history.json'),'--qualification-companion',str(args.companion.resolve())], [str(I/'qa.py')]]
    for number, command in enumerate(commands,1):
        completed = subprocess.run([sys.executable,'-X','utf8','-B',*command],cwd=REPO,capture_output=True,text=True,encoding='utf-8')
        (out/f'stage-{number}.stdout').write_text(completed.stdout,encoding='utf-8')
        (out/f'stage-{number}.stderr').write_text(completed.stderr,encoding='utf-8')
        if completed.returncode:
            raise RuntimeError(f'Stage {number} failed with exit {completed.returncode}; logs preserved at {out}')
    exports = {}
    for name in ('report.html','data.json','provenance.json','qa.json'):
        target = out/name
        target.write_bytes((I/name).read_bytes())
        exports[name] = binding(target)
    result = {'schema':'campaign002-actual-build-receipt-1','completed_at':datetime.now(timezone.utc).isoformat(),'passed':True,'exports':exports,'companion':binding(args.companion),'commands':commands,'builder':binding(I/'build.py'),'template':binding(I/'template.html'),'failed_outcomes_consumed':False}
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'directory':str(out),'report':exports['report.html']}))

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',required=True)
    p.add_argument('--companion',type=Path,required=True)
    p.add_argument('--export-frames',action='store_true')
    run(p.parse_args())
