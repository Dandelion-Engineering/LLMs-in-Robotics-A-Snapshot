"""Bounded original Smoke030 diagnosis; never modifies an attempt or reader."""
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent; C=HERE.parents[1]; REPO=HERE.parents[4]
JOB='20260930T201324760129Z-39fdac3e'
ITEM='exec-132cc072-41fb-47a1-879f-6b900f199358'

def identity(p):
    p=Path(p); raw=p.read_bytes()
    return {'path':str(p.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def save(name,value):
    with (HERE/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')

def main():
    queue=REPO.parent/'tools/compute_queue/compute_queue.py'
    official=json.loads(subprocess.run([sys.executable,'-X','utf8','-B',str(queue),'status',JOB],
        cwd=REPO,capture_output=True,text=True,encoding='utf-8',check=True).stdout)
    assert official['id']==JOB and official['state']=='succeeded'
    assert type(official['exit_status']) is int and official['exit_status']==0
    save('official-status.json',official)
    disposition=C/'qualification/final-qualification-032/smoke-030/disposition.json'
    d=json.loads(disposition.read_text(encoding='utf-8')); entry=d['entry']
    for name in ('manifest','snapshot','assessment','queue'):
        assert identity(entry[name]['path'])['sha256']==entry[name]['sha256']
    a=json.loads(Path(entry['assessment']['path']).read_text(encoding='utf-8'))
    assert a['queue_job_id']==JOB and a['smoke_passed'] is False
    assert sum(v is True for v in a['checks'].values())==61 and len(a['checks'])==62
    archive=Path(entry['snapshot']['path']).with_name('source.zip')
    if not archive.is_file():
        candidates=list(archive.parent.glob('*.zip'));assert len(candidates)==1;archive=candidates[0]
    assert identity(archive)['sha256']==a['frozen_archive_sha256']
    receipts=[identity(disposition),identity(archive)]
    # Use unchanged source, authenticated to the exact attempt archive.
    with zipfile.ZipFile(archive) as z:
        for name in ('initial_read_composition.py','literal_read_segments.py','empty_startup_reads.py',
                     'retained_reads.py','completion_chronology.py'):
            p=C/'assessment'/name
            members=[n for n in z.namelist() if n.endswith('/campaign-002/assessment/'+name)]
            assert len(members)==1 and z.read(members[0])==p.read_bytes()
            receipts.append(identity(p))
    save('authentication.json',{'checked_at':datetime.now(timezone.utc).isoformat(),
        'official':identity(HERE/'official-status.json'),'entry':entry,'inputs':receipts,
        'failed_checks':[k for k,v in a['checks'].items() if v is not True],
        'passed_checks':61,'total_checks':62,'original_verdict_preserved':True})
    sys.path.insert(0,str(C/'assessment'))
    initial=importlib.import_module('initial_read_composition'); literal=initial.literal
    root=Path(entry['evidence'])/'resume'; host=Path(entry['host_evidence'])
    events=initial.load_json(root/'client/events.jsonl',receipts,lines=True)
    hashes=initial.load_json(root/'runtime-input-hashes.json',receipts)
    history=initial.load_json(host/'public-history.jsonl',receipts,lines=True)
    reads,integrity=initial.process_reads(root,events)
    assert integrity['verified'],integrity['errors']
    event,=[e for e in events if e.get('method')=='item/completed'
        and e.get('params',{}).get('item',{}).get('id')==ITEM]
    item=event['params']['item']; read=reads[ITEM]
    assert item['exitCode']==0 and read['provenance']['app_projection_equals_executor'] is True
    argv=shlex.split(item['command']); raw=read['stdout'].encode()
    execution=literal.execution_proof(root,event,events,read)
    static,static_proof=literal.static_sources(root,host,archive,hashes,history,
        ['Continuity.md'],execution['request_wall_unix_s'],receipts)
    expected=static['Continuity.md']
    assert initial.find_prefix_roots(argv) is None
    try:
        prefix=initial.prefix_attribution(expected,raw,initial.ROOT_PREFIXES); prefix_error=None
    except (ValueError,TypeError) as error:
        prefix=None;prefix_error=str(error)
    observations={'item_id':ITEM,'argv':argv,'stdout_bytes':len(raw),
        'stdout_sha256':hashlib.sha256(raw).hexdigest(),'expected_bytes':len(expected),
        'expected_sha256':hashlib.sha256(expected).hexdigest(),
        'expected_is_complete_output_prefix':raw.startswith(expected),
        'supported_original_recipe':False,'prefix_attribution':prefix,'prefix_error':prefix_error,
        'executor_provenance':read['provenance'],'execution':execution,'static_sources':static_proof,
        'inputs':receipts,'scope':'Diagnostic origin test only; original failed qualification unchanged.'}
    save('observations.json',observations)
    print(json.dumps({k:observations[k] for k in ('stdout_bytes','expected_bytes','expected_sha256',
        'expected_is_complete_output_prefix','supported_original_recipe','prefix_error')}))

if __name__=='__main__':main()
