"""Summarize completed native fixtures after official queue success, without rerunning."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
RUNS = ['RCI001-stock-baseline-001', 'RCI001-stock-reference-001',
        'RCI001-home-baseline-001', 'RCI001-home-reference-001']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    rows = []
    for rid in RUNS:
        receipt_path = HERE/'records'/(rid+'-queue.json')
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        assert receipt['state'] == 'succeeded' and receipt['exit_status'] == 0
        assert any(rid+'.json' in arg for arg in receipt['argv'])
        root = HERE/'local-evidence'/rid
        result = json.loads((root/'result.json').read_text(encoding='utf-8'))
        assert result['run_id'] == rid and result['robot_invocations'] == 0
        registry = json.loads((root/'command-registry.json').read_text(encoding='utf-8'))
        selected = []
        for command in registry.values():
            selected.append({key: command.get(key) for key in
                             ('request_id','kind','actor','phase','status','native_action',
                              'verification','requested_sim_time_s','terminal_sim_time_s')})
        files = {}
        for name in ('manifest.json','result.json','command-registry.json','public-history.jsonl',
                     'frozen-source-verification.json','recorder-source-verification.json'):
            path = root/name
            files[name] = {'sha256':sha(path),'bytes':path.stat().st_size}
        copy = HERE/'records'/(rid+'-result.json')
        if copy.exists():
            assert copy.read_bytes() == (root/'result.json').read_bytes()
        else:
            with copy.open('xb') as f: f.write((root/'result.json').read_bytes())
        rows.append({'run_id':rid,'queue_id':receipt['id'],'result':result,
                     'commands':selected,'raw_directory':str(root),'core_files':files,
                     'total_native_evidence_bytes':sum(p.stat().st_size for p in root.rglob('*') if p.is_file())})
    output = {'scope':'Four development fixtures; one placement/seed each. No model, scored inference, or general success rate.',
              'runs':rows}
    with (HERE/'records/native-development-evidence.json').open('x',encoding='utf-8') as f:
        json.dump(output,f,indent=2); f.write('\n')
    for row in rows:
        r = row['result']
        print(row['run_id'],r['terminal'],'success='+str(r['independent_outcome']['success']),
              'handbacks='+str(r['handbacks']),'bytes='+str(row['total_native_evidence_bytes']))

if __name__ == '__main__': main()
