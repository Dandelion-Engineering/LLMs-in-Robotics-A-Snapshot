"""Compact the successful read-only audit and authenticate local source receipts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
AUDIT=Path('D:/Dandelion-Apartment-Experiment/investigations/restart001-session32-audit002')
FIRST=Path('D:/Dandelion-Apartment-Experiment/investigations/restart001-session32-audit001')
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v1-restart001')
QUEUE=Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(name,x):
    with (HERE/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def ref(p):return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}

jobs={}
for name,jid in [('first_baseline','20261007T045828061579Z-37c81eac'),('second_baseline','20261007T152810664605Z-1b6c57b1'),
                ('audit001','20261007T174453199890Z-0efd7ee3'),('audit002','20261007T174758541852Z-b6a03c0c')]:
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(QUEUE),'status',jid],capture_output=True,text=True,encoding='utf-8',check=True)
    d=json.loads(p.stdout);jobs[name]=d
save('queue-statuses.json',jobs)
assert jobs['audit002']['state']=='succeeded' and type(jobs['audit002']['exit_status']) is int and jobs['audit002']['exit_status']==0
d=read(AUDIT/'result.json');assert d['audit_passed']
preservation={}
for name in ['restart001','original','original_preservation']:
    same=read(FIRST/(name+'-before.json'))==read(AUDIT/(name+'-after.json'));assert same
    preservation[name]={'from_first_audit_through_final_audit_unchanged':same,**d['preservation'][name]}
frozen=PAIR/'frozen_repository';manifest=read(frozen/'source-manifest.json');prepared=read(PAIR/'prepared.json')
assert sha(frozen/'source-manifest.json')==prepared['source_manifest_sha256']
for relative,item in manifest.items():
    p=frozen/relative;assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],relative
source={'frozen_manifest_files_verified':len(manifest),'frozen_manifest':ref(frozen/'source-manifest.json'),
    'runtime_template_identities_match':d['source_identity_matches'],'runtime_template_identity_count':d['source_identity_files']}
sessions=[]
for s in d['sessions']:
    j=s['journal'];timeline=s['native']['terminal']
    sessions.append({k:v for k,v in s.items() if k not in ['native','journal']}|{
        'journal':{k:v for k,v in j.items() if k not in ['writes','rejected']},
        'rejected_mutation_count':len(j['rejected']),
        'largest_write_paths':sorted(j['writes'].items(),key=lambda x:x[1]['input_bytes'],reverse=True)[:3],
        'full_copy_write_bytes_counterfactual':sum(v['full_version_bytes_counterfactual'] for v in j['writes'].values()),
        'native_terminal':timeline,'native_errors':s['native']['errors'],
        'completed_item_counts':s['native']['completed_item_counts'],
        'last_rate_notification':s['native']['rate_notifications'][-1] if s['native']['rate_notifications'] else None})
result={'observed_utc':datetime.now(timezone.utc).isoformat(),'read_only_audit':ref(AUDIT/'result.json'),
    'first_audit_error':ref(FIRST/'audit-error.json'),'queue_receipt':ref(HERE/'queue-statuses.json'),
    'source':source,'preservation':preservation,'sessions':sessions,
    'original_journal':{k:v for k,v in d['original_journal'].items() if k!='writes'},
    'maps':d['maps'],'boundary':d['boundary'],'checkpoints':d['checkpoint_state'],'replay':d['replay'],
    'event_counts':d['events']['counts'],'event_chain_verified':d['events']['chain_passed'],
    'sensor_images_verified':d['events']['verified_sensor_images'],
    'session6_export_equals_persistent_files':d['last_export_matches_persistent_filesystem'],
    'session6_initial_namespace_equals_session5_final':d['session5_namespace_equals_session6_initial'],
    'disk_free_at_audit':d['disk_free'],
    'limitations':['Remote server internals and raw HTTP status were not available.',
        'Raw native stderr text was not retained; hashes and lexical markers cannot recover its content.',
        'No historical process peak RAM or system-wide free-memory trace; current resources cannot prove past peaks.',
        'This is a forensic readback, not repair commissioning or a scored experiment comparison.']}
save('evidence.json',result)
save('documentation.json',{'fetched_utc':datetime.now(timezone.utc).isoformat(),
    'sources':[{'url':'https://learn.chatgpt.com/docs/app-server','use':'Terminal status and error lifecycle; native record remains decisive.'},
               {'url':'https://developers.openai.com/api/docs/guides/rate-limits','use':'General overload/backoff guidance, bounded retries, caution after output; not proof of the ChatGPT-authenticated request HTTP status.'}],
    'boundary':'Documentation guidance is not authorization to retry this frozen run or switch models.'})
print(json.dumps({'verified':True,'frozen_files':len(manifest),'protected_files':sum(x['files'] for x in preservation.values()),'evidence':str(HERE/'evidence.json')}))
