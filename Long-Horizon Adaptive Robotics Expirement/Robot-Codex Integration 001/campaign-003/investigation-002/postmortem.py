"""Read recovered pilot bytes without turning postmortem closure into qualification."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import shutil
import sys
import tarfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from common import HERE,MAP,save,sha
from verify_journal import verify
from analyze import artifact_history

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def extract(archive,out):
    out.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive) as tar:
        for m in tar.getmembers():
            assert (out/m.name).resolve().is_relative_to(out.resolve())
            assert not m.issym() and not m.islnk() and (m.isfile() or m.isdir())
        tar.extractall(out,filter='data')

def run(out):
    out=Path(out).resolve();out.mkdir(exist_ok=False)
    assert shutil.disk_usage(out).free>=104*1024**3
    repair=HERE/'retirement-revision-001';episode=HERE/'live-evidence/RCI001-C03-pilot-002-attempt'
    source=MAP/'releases/RCI001-C03-live/RCI001-C03-pilot-002';manifest=read(source/'manifest.json')
    official=read(source/'official-status.json');audit=read(HERE/'qualification/pilot-audit-002/assessment/receipt.json')
    assert official['state']=='failed' and type(official['exit_status']) is int and official['exit_status']==1
    assert audit['passed'] is False and audit['task_outcome']=='unknown'
    before=repair/'capture-before-shutdown';after=repair/'capture-after-shutdown-002'
    for capture in (before,after):
        job=read(capture/'official-status.json');receipt=read(capture/'receipt.json')
        assert job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0
        assert receipt['passed'] and sha(capture/'journal.tar.gz')==receipt['archive_sha256']
    original=read(HERE/'qualification/pilot-audit-002/assessment/input-identities.json')
    changes=read(repair/'postmortem-windows-change.json')['changed'];assert set(changes)=={'workspace-block/fuse-server.log'}
    expected={n:(changes[n]['after'] if n in changes else value) for n,value in original.items()}
    assert all(sha(episode/n)==v['sha256'] for n,v in expected.items())
    for capture,name in ((before,'before'),(after,'after')):extract(capture/'journal.tar.gz',out/'raw'/name)
    prefix=(out/'raw/before/journal/mutations.jsonl').read_bytes();complete=(out/'raw/after/journal/mutations.jsonl').read_bytes()
    assert complete.startswith(prefix)
    added=complete[len(prefix):].splitlines();assert len(added)==1 and json.loads(added[0])['type']=='final'
    prefix_last=json.loads(prefix.splitlines()[-1]);final=json.loads(added[0]);assert prefix_last['type']=='checkpoint'
    replay=verify(out/'raw/after/journal',manifest['run_id'])
    assert prefix_last['state_sha256']==replay['final_state_sha256']==final['state_sha256']
    rows=[json.loads(l) for l in complete.splitlines()]
    assert all(r['source_revision']==manifest['revision_id'] and r['source_snapshot_sha256']==manifest['source_snapshot_sha256'] for r in rows)
    artifacts=artifact_history(rows);save(out/'raw/artifact-history.json',artifacts)
    reads=defaultdict(list)
    for r in artifacts['reads']:
        if r['after_model_boundary'] and r['matches_content_at_session_start'] and r['process'].get('namespace_role')=='isolated-runtime':
            reads[(r['session_id'],r['path'],r['content_sha256'])].append(r)
    candidates=[dict(session_id=sid,path=path,sha256=digest,count=len(rs),first_sequence=rs[0]['sequence'],last_sequence=rs[-1]['sequence'],bytes=sum(r['bytes'] for r in rs)) for (sid,path,digest),rs in sorted(reads.items())]
    registry=list(read(episode/'host/command-registry.json').values())
    sessions=read(episode/'receipt.json')['attempted_sessions'];public_items=[]
    for session in sessions:
        sid=session['session_id'];path=episode/sid/'client/events.jsonl'
        with path.open(encoding='utf-8') as stream:
            for number,line in enumerate(stream,1):
                row=json.loads(line)
                if row.get('method')!='item/completed':continue
                item=row.get('params',{}).get('item',{})
                if item.get('type') not in ('agentMessage','commandExecution'):continue
                public_items.append(dict(session_id=sid,source=f'{sid}/client/events.jsonl:{number}',
                    item={k:item[k] for k in ('type','id','text','command','exitCode') if k in item}))
    save(out/'raw/public-items.json',public_items)
    assert all(sha(episode/n)==v['sha256'] for n,v in expected.items())
    result=dict(postmortem_integrity_passed=True,model_calls=0,original_validity='invalid',original_task_outcome='unknown',
        original_queue_state=official['state'],original_queue_exit_status=official['exit_status'],original_reader_passed=False,
        scope='Exact recovered bytes and observable behavior only. Added final record is postmortem cleanup; this cannot authorize a pilot pass, scoring or useful-transfer claim.',
        original_manifest_sha256=sha(source/'manifest.json'),prefix_records=prefix_last['sequence'],postmortem_final_sequence=final['sequence'],
        reconstructed_journal={k:v for k,v in replay.items() if k not in ('state','states','read_events')},
        observed_accepted_handbacks=[r['request_id'] for r in registry if r['kind']=='handback' and r['status']=='completed'],
        physical_statuses=dict(Counter(r['status'] for r in registry if r['kind']=='command' and r.get('actor')=='robot')),
        prior_content_read_candidates=candidates,final_inventory=artifacts['final_inventory'],
        semantic_use='requires direct program/content/action readback',useful_transfer='unqualified because original pilot remains invalid',
        causal_contribution='unknown; no matched withholding intervention',
        preserved_original_windows_files=len(original)-len(changes),known_postmortem_log_change=changes,
        source_hashes={str(p):sha(p) for p in [Path(__file__),Path(__file__).with_name('analyze.py'),HERE/'verify_journal.py']})
    save(out/'receipt.json',result)
    print(json.dumps({k:result[k] for k in ('postmortem_integrity_passed','original_validity','original_task_outcome','prefix_records','postmortem_final_sequence','physical_statuses')}))

if __name__=='__main__':run(sys.argv[1])
