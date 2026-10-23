"""One prospective Campaign 004 block; no successful-model-pilot selection gate."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import zipfile
AREA=Path(__file__).resolve().parent
sys.path.insert(0,str(AREA.parent))
from common import HERE,REPO,MAP,sha,save
from register import append,mapcmd,ref,state
from runtime_limits import apply_limits
from scheduler import Schedule
from archive_location import PUBLIC_EXPORT_ROOT

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()
def fields(identity):return dict(schema_version='architecture-map-1.0',id=identity,recorded_at=now(),author='Codex session 26',tags=['campaign-004','frozen','one-block'],details={})

def freeze(final_receipt,final_status):
    final_receipt=Path(final_receipt).resolve();final_status=Path(final_status).resolve()
    checked=read(final_receipt);assert checked['passed']
    for name,digest in checked['runtime_sources'].items():assert sha(HERE/name)==digest,name
    for name,digest in checked['template_sources'].items():assert sha(HERE/name)==digest,name
    identity='RCI001-C04-final-001';run_id=identity+'-block-001'
    output=HERE/'scored-evidence'/run_id
    assert not output.exists()
    assert not any((HERE/'scored-evidence').glob('*'))
    gates=[]
    for receipt,status,scope in (
        (HERE/'qualification/identity-001/receipt.json',MAP/'releases/RCI001-C04-dev/RCI001-C04-dev-001/official-status.json','432 rendered stable-face identity and unchanged physical model checks'),
        (final_receipt,final_status,'Exact final system: same-world continuation, three-session ceiling, isolation, journal, image and success paths'),
        (HERE.parent/'campaign-003/qualification/live-audit-005/assessment/receipt.json',HERE.parent/'campaign-003/qualification/live-audit-005/official-status.json','Inherited live-qualified byte-identical client/executor/task interface')):
        r=read(receipt);s=read(status)
        assert r['passed'] and s['state']=='succeeded' and type(s['exit_status']) is int and s['exit_status']==0
        gates.append(dict(receipt=str(receipt),receipt_sha256=sha(receipt),status=str(status),status_sha256=sha(status),scope=scope))
    c3=HERE.parent/'campaign-003'
    for name in ('bootstrap_client.py','executor_capture.py'):assert sha(HERE/name)==sha(c3/name)
    for p in (HERE/'template').rglob('*'):
        if p.is_file():assert sha(p)==sha(c3/p.relative_to(HERE))
    folder=MAP/'releases/RCI001-C04'/identity;folder.mkdir(parents=True,exist_ok=False)
    authority_path=REPO/'chats/Codex-Human/Robot-Codex Campaign 004/Robot-Codex Campaign 004 - Active.md'
    authority=dict(path=authority_path.relative_to(REPO).as_posix(),bytes=authority_path.stat().st_size,sha256=sha(authority_path))
    allocation=dict(schema='campaign004-allocation-1',id='Campaign004-one-persistent-block',blocks=1,
        independent_unit='persistent_block',encounters_per_block=3,max_sessions_per_occurrence=3,max_model_sessions=9,
        no_replacements=True,no_model_pilot=True,seed=173,noise_seed=440101,schedule_seed=440103,
        task_failure_policy='stop_block_later_occurrences_not_run',infrastructure_failure_policy='stop_invalid_no_replacement',
        protocol_sha256=sha(AREA/'PROTOCOL.md'),limits_sha256=sha(HERE/'limits.json'),
        rationale='Director authorized one bounded Campaign 004 continuity experiment; fixed descriptive block before outcomes.')
    save(folder/'allocation.json',allocation);save(folder/'qualification-gates.json',gates)
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))+[HERE/'limits.json']+list(AREA.glob('*.py'))+list(AREA.glob('*.md'))
    for area in ('template','vendor','protocol'):
        paths.extend(p for p in (HERE/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    sources={p.relative_to(REPO).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(set(paths))}
    inherited=read(MAP/'releases/RCI001-C02-dev-114/snapshot.json')['sources']
    for name,value in inherited.items():assert sha(REPO/name)==value['sha256'],name
    with zipfile.ZipFile(folder/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(sources):archive.write(REPO/name,name)
    save(folder/'snapshot.json',dict(schema='campaign004-final-snapshot-1',source=sources,inherited=inherited,
        qualified_system_snapshot_sha256=checked['qualified_system_snapshot_sha256']))
    apparatus=apply_limits(dict(run_id=run_id,seed=173,noise_seed=440101,schedule_seed=440103,encounters=3,
        initial_order=Schedule(440103,3).current,mode='serve',stage='reviewed_campaign'),'reviewed_campaign')
    model=dict(name='gpt-6-astra',effort='max',bootstrap='Follow the instructions in RobotAgentPrompt.md.',fresh_ephemeral_thread=True)
    manifest=dict(stage='reviewed_campaign',run_id=run_id,revision_id=identity,created_at=now(),encounter_limit=3,
        description='One prospective Campaign 004 persistent block with at most three fresh sessions per C occurrence',
        human_approval_reference='Randy 2026-10-04 10:12 PDT: complete Campaign 004 without routine approval',authority=authority,
        model=model,source_snapshot_path='snapshot.json',source_snapshot_sha256=sha(folder/'snapshot.json'),
        apparatus_manifest=apparatus,output=str(output),no_replacement=True,scientific_prompt_unchanged=True,
        qualification_gates=gates,public_archive_root=str(PUBLIC_EXPORT_ROOT),
        allocation_reference=dict(path=str(folder/'allocation.json'),sha256=sha(folder/'allocation.json')),
        model_calls_at_freeze=0,live_qualification_rationale='Exact prior live-qualified client/executor/template; all changed apparatus qualified deterministically without model outcome selection.')
    save(folder/'manifest.json',manifest)
    system_job=read(final_receipt.parent/'system-audit/source-job.json')
    system_declaration=read(Path(system_job['cwd'])/system_job['argv'][-1])
    revision={**fields(identity),'architecture_id':'RCI001','parent_revision_id':system_declaration['revision_id'],'status':'frozen',
        'title':'Campaign 004 six-face identity and bounded fresh-session continuation',
        'summary':'One three-occurrence persistent block; at most three fresh GPT-6 Astra / max sessions per occurrence, hidden allowance, no replacements.',
        'mechanism':(HERE/'CONTRACT.md').read_text()+'\n\n'+(AREA/'PROTOCOL.md').read_text(),
        'attachments':[ref(folder/'source.zip','Exact final sources'),ref(folder/'snapshot.json','Source identities'),
            ref(folder/'allocation.json','Prospective allocation'),ref(folder/'qualification-gates.json','Independent qualification gates')]}
    append('revision',revision,folder/'revision-record.json')
    run={**fields(run_id),'revision_id':identity,'stage':'evaluation','condition_id':'fresh-session-persistent-filesystem',
        'protocol_id':allocation['id'],'scenario_id':'three-C-with-separated-AB','paired_block_id':run_id,'replicate':1,
        'started_at':None,'rerun_of_run_id':None,'condition_details':dict(declared_occurrences=3,max_sessions_per_occurrence=3,max_sessions=9),
        'seeds':state(folder/'manifest.json','Protected prospective seeds'),
        'frozen_refs':{role:state(folder/name,label) for role,name,label in (
            ('code','snapshot.json','Exact source identities'),('environment','qualification-gates.json','Qualified apparatus'),
            ('models','manifest.json','Fixed fresh model and bootstrap'),('protocol','allocation.json','Fixed bounded block'),
            ('scenario','manifest.json','Seeded world and schedule'))},
        'evidence':[ref(folder/'manifest.json','Pre-outcome block declaration')]}
    append('run',run,folder/'run-record.json');mapcmd('build');print(mapcmd('validate','--output','validation.json'))
    save(folder/'freeze-receipt.json',dict(created_at=now(),manifest_sha256=sha(folder/'manifest.json'),
        allocation_sha256=sha(folder/'allocation.json'),source_snapshot_sha256=sha(folder/'snapshot.json'),model_calls_at_freeze=0))
    print(json.dumps(dict(manifest=str(folder/'manifest.json'),run_id=run_id)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('final_receipt');p.add_argument('final_status');a=p.parse_args();freeze(a.final_receipt,a.final_status)
