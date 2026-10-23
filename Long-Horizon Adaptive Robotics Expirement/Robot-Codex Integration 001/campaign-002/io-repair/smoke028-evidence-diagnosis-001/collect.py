"""Read-only original Smoke028 diagnosis after fresh official terminal gate."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]
REPO=HERE.parents[4]
JOB='20260930T183719742147Z-06b11f8b'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'

def identity(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def save(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')

def main():
    status=subprocess.run([sys.executable,'-X','utf8','-B',str(QUEUE),'status',JOB],
                          cwd=REPO,capture_output=True,text=True,encoding='utf-8',check=True)
    official=json.loads(status.stdout)
    assert official['id']==JOB and official['state']=='succeeded'
    assert type(official['exit_status']) is int and official['exit_status']==0
    save('official-status.json',official)
    disposition=C/'qualification/final-qualification-030/smoke-028/disposition.json'
    result=json.loads(disposition.read_text(encoding='utf-8'));entry=result['entry']
    for name in ('manifest','snapshot','assessment'):
        assert identity(entry[name]['path'])['sha256']==entry[name]['sha256']
    assessment=json.loads(Path(entry['assessment']['path']).read_text(encoding='utf-8'))
    assert assessment['queue_job_id']==JOB and assessment['smoke_passed'] is False
    snapshot=Path(entry['snapshot']['path']);archive=snapshot.with_name('source.zip')
    if not archive.is_file():
        candidates=list(snapshot.parent.glob('*.zip'));assert len(candidates)==1;archive=candidates[0]
    assert identity(archive)['sha256']==assessment['frozen_archive_sha256']
    root=Path(entry['evidence']);receipts=[identity(disposition),identity(archive)]
    save('authentication.json',{'checked_at':datetime.now(timezone.utc).isoformat(),
        'official_status':identity(HERE/'official-status.json'),'entry':entry,'archive':identity(archive),
        'original_failed_checks':[k for k,v in assessment['checks'].items() if v is not True],
        'passed_checks':sum(v is True for v in assessment['checks'].values()),
        'total_checks':len(assessment['checks']),'scope':'Original verdict preserved; diagnostic only.'})
    # Load the exact frozen capture validator without changing production readers.
    with zipfile.ZipFile(archive) as z:
        names=[n for n in z.namelist() if n.endswith('/campaign-002/assessment/retained_reads.py')]
        assert len(names)==1
        module={'__name__':'frozen_retained_reads'};exec(compile(z.read(names[0]),names[0],'exec'),module)
    targets={'interrupt':['exec-3c0ba3cc-07a2-460a-bb7e-26df782fde2b'],
             'resume':['exec-e5fa7fcf-c9ac-403e-b9a7-d7544a75c063','exec-63fbd134-37b5-410b-8331-f95db27ce075']}
    records=[]
    for stage,ids in targets.items():
        events_path=root/stage/'client/events.jsonl';receipts.append(identity(events_path))
        events=[json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
        items={e['params']['item']['id']:e for e in events if e.get('method')=='item/completed'
               and ((e.get('params') or {}).get('item') or {}).get('id') in ids}
        assert set(items)==set(ids)
        for path in sorted((root/stage).glob('executor-*-capture.jsonl')):
            rows,delivered,binding=module['load_capture'](path);receipts.append(identity(path))
            for request in rows:
                msg=request.get('message') or {};p=msg.get('params') or {}
                item_id=(p.get('metadata') or {}).get('toolCallId')
                if request.get('kind')!='request' or msg.get('method')!='process/start' or item_id not in ids:continue
                pid=p['processId'];stream=[];stdout=bytearray()
                import base64
                for row in rows:
                    m=row.get('message') or {};params=m.get('params') or {}
                    if row.get('kind')!='response' or m.get('method') not in ('process/output','process/exited','process/closed') or params.get('processId')!=pid:continue
                    stream.append({'capture_sequence':row['sequence'],'native_sequence':params.get('seq'),
                        'method':m['method'],'delivered':row['sequence'] in delivered,
                        'unredacted':row.get('original_message_sha256')==row.get('retained_message_sha256'),
                        'wall_unix_s':row['wall_unix_s'],'exit_code':params.get('exitCode')})
                    if m['method']=='process/output' and params.get('stream')=='stdout':stdout.extend(base64.b64decode(params['chunk'],validate=True))
                item=items[item_id]['params']['item'];projection=item.get('aggregatedOutput')
                records.append({'stage':stage,'item_id':item_id,'argv':p['argv'],'capture':binding,
                    'process_id':pid,'request_capture_sequence':request['sequence'],'stream':stream,
                    'stdout':stdout.decode('utf-8'),'stdout_bytes':len(stdout),
                    'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'app_exit_code':item.get('exitCode'),
                    'app_output_equals_executor':projection==stdout.decode('utf-8'),
                    'app_emitted_at_ms':items[item_id].get('emittedAtMs')})
    assert len(records)==3
    save('observations.json',{'records':records,'inputs':receipts,
         'scope':'Captured bytes and order only; no new qualification verdict.'})
    print(json.dumps({'authenticated':True,'original_passed':59,'original_total':62,'observations':len(records)}))

if __name__=='__main__':main()
