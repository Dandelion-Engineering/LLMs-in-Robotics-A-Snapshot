"""Explicit immutable continuation from a verified clean boundary.

The failed root is read only. Its later actions, model calls, journals and replay
remain there. No native request is retried by this module. A separate authorized
launch resumes the newly authenticated branch.
"""
import hashlib
import json
import os
from pathlib import Path
import uuid
from common import canonical,copy_durable,inventory,read,save,sha
from recording import copy_tree,verify_checkpoint,verify_prefix

POLICY='verified-boundary-branch-1'


def terminal(root):
    pointer=read(Path(root)/'latest-execution.json');path=Path(pointer['path'])
    if path.parent.resolve()!=Path(root).resolve() or sha(path)!=pointer['sha256']:
        raise ValueError('Execution result pointer is not authentic')
    return read(path)


def best_checkpoint(root):
    candidates=[];rejections=[]
    for folder in (Path(root)/'checkpoints').iterdir():
        if not folder.is_dir():continue
        try:
            receipt=verify_checkpoint(folder);verify_prefix(root,folder);state=read(folder/'state.json')
            candidates.append((state['sessions'],state['event_sequence'],folder,receipt,state))
        except Exception as error:rejections.append(dict(path=str(folder),error=repr(error)))
    if not candidates:raise ValueError('No verified clean checkpoint; an initial restart is not recovery')
    selected=max(candidates,key=lambda c:(c[0],c[1]))
    return selected[2],selected[3],selected[4],rejections


def check_branch_authority(root,run):
    if 'recovery' not in run:return
    binding=run['recovery'];claim=read(binding['claim'])
    if Path(claim['destination']).resolve()!=Path(root).resolve() or claim['branch_id']!=run['branch_id']:
        raise ValueError('Recovery branch has no exclusive continuation claim')
    if not (Path(root)/'recovery-ready.json').is_file():raise ValueError('Recovery branch was not fully prepared')


def completed_baseline(pair,maps_run):
    pair=Path(pair).resolve();lineage=pair/'baseline-lineage.json'
    root=pair/'baseline'
    if lineage.exists():root=Path(read(lineage)['active_root']).resolve()
    if not root.is_relative_to(pair):raise ValueError('Baseline lineage escaped the official pair')
    result=read(root/'completed.json');run=read(root/'run.json')
    for key in ('source_identity','schedule_sha256','config_sha256'):
        if run[key]!=maps_run[key]:raise ValueError('Baseline/Maps comparison identity differs')
    if result.get('assignments')!=21:raise ValueError('Official baseline must complete before Maps starts')
    checkpoint=Path(result['checkpoint']['path'])
    if not checkpoint.resolve().is_relative_to(root):raise ValueError('Completed checkpoint outside its branch')
    verify_checkpoint(checkpoint);verify_prefix(root,checkpoint);state=read(checkpoint/'state.json')
    if state['position']!=21 or len(state['completed'])!=21:raise ValueError('Baseline endpoint is incomplete')
    if not terminal(root).get('passed'):raise ValueError('Baseline endpoint execution did not retire successfully')
    return dict(root=str(root),checkpoint=str(checkpoint),sessions=state['sessions'])


def prepare_recovery(source,destination,reason,official=False):
    from run import verify_run
    source=Path(source).resolve();destination=Path(destination).resolve()
    if not reason.strip():raise ValueError('Explicit infrastructure recovery reason required')
    if (source/'running.lock').exists():raise ValueError('Cannot recover a running or unretired root')
    run=verify_run(source,official)
    if read(source/'config.json').get('recovery_policy')!=POLICY:raise ValueError('This lineage has no prospective recovery policy')
    if (source/'completed.json').exists():raise ValueError('Completed condition needs no recovery')
    execution=terminal(source)
    if execution.get('passed'):raise ValueError('Clean hibernation uses ordinary resume, not failure recovery')
    if execution.get('retirement',{}).get('all_retired') is not True:raise ValueError('Recorded runtime retirement is required before recovery')
    if destination.exists() or source==destination or destination.is_relative_to(source):
        raise ValueError('Recovery requires a distinct new sibling lineage')
    if destination.drive.upper()!='D:':raise ValueError('Recovery evidence must remain on D:')
    pair=Path(run.get('official_pair_root',source.parent)).resolve()
    if run['stage']=='official':
        if run['condition'] not in ('baseline','maps'):raise ValueError('Unknown official condition')
        if not destination.is_relative_to(pair/'recoveries'):raise ValueError('Official recovery must remain inside the paired recovery directory')
        lineage_path=pair/(run['condition']+'-lineage.json')
        lineage=read(lineage_path)
        if Path(lineage['active_root']).resolve()!=source:raise ValueError('Only the active lineage may continue')
    before=inventory(source)
    checkpoint,receipt,state,rejected=best_checkpoint(source)
    if state['config']!=read(source/'config.json') or state['schedule_sha256']!=__import__('schedule').validate(read(source/'schedule.json')):
        raise ValueError('Checkpoint comparison inputs differ')
    if state['condition']!=run['condition']:raise ValueError('Checkpoint condition differs')
    branch_id=uuid.uuid4().hex
    claim=pair/'recovery-claims'/str(run['branch_id'])
    claim.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive directory creation also refuses a partially written claim. That
    # state requires explicit inspection, never a second successful continuation.
    claim.mkdir(exist_ok=False)
    binding=dict(source=str(source),destination=str(destination),branch_id=branch_id,
        checkpoint=str(checkpoint),checkpoint_sha256=receipt['manifest_sha256'],reason=reason)
    save(claim/'claim.json',binding)
    destination.mkdir(parents=True,exist_ok=False)
    try:
        for name in ('schedule.json','config.json','initial-filesystem.json'):copy_durable(source/name,destination/name)
        for name in ('filesystem','filesystem-objects'):
            if (checkpoint/name).exists():copy_tree(checkpoint/name,destination/name)
        if (checkpoint/'filesystem-namespace.json').exists():copy_durable(checkpoint/'filesystem-namespace.json',destination/'filesystem-namespace.json')
        with (source/'events.jsonl').open('rb') as incoming,(destination/'events.jsonl').open('xb') as outgoing:
            left=state['log_bytes']
            while left:
                block=incoming.read(min(left,1024*1024))
                if not block:raise ValueError('Event prefix truncated during copy')
                outgoing.write(block);left-=len(block)
            outgoing.flush();os.fsync(outgoing.fileno())
        index=read(checkpoint/'replay-index.json')
        for row in index:copy_durable(source/'replay'/row['file'],destination/'replay'/row['file'])
        copy_durable(checkpoint/'replay-index.json',destination/'replay/index.json')
        for line in (destination/'events.jsonl').read_bytes().splitlines():
            row=json.loads(line)
            if row['kind']=='sensor_capture':
                item='frame-'+str(row['payload']['sequence']).zfill(7)+'.png'
                if sha(source/'sensors'/item)!=row['payload']['image_sha256']:raise ValueError('Sensor prefix corrupt')
                copy_durable(source/'sensors'/item,destination/'sensors'/item)
        # Completed session evidence is part of the copied prefix, including the
        # full namespace history needed for the existing replay inspector.
        for number in range(1,state['sessions']+1):
            sid='session-'+str(number).zfill(5)
            for relative in ('sessions/'+sid,'filesystem-before-'+sid):
                if (source/relative).exists():copy_tree(source/relative,destination/relative)
        new_checkpoint=destination/'checkpoints'/('session-'+str(state['sessions']).zfill(5))
        copy_tree(checkpoint,new_checkpoint)
        save(destination/'latest-checkpoint.json',dict(path=str(new_checkpoint),**verify_checkpoint(new_checkpoint)))
        verify_prefix(destination,new_checkpoint)
        rows=[json.loads(line) for line in (source/'events.jsonl').read_bytes().splitlines()]
        tail=[row for row in rows if row['sequence']>state['event_sequence']]
        interrupted=sum(row['kind']=='session_started' for row in tail)
        prior=read(source/'recovery-ready.json') if (source/'recovery-ready.json').exists() else {}
        cumulative=prior.get('cumulative_interrupted_sessions',0)+interrupted
        run={**run,'branch_id':branch_id,'launched':True,'recovery':dict(**binding,claim=str(claim/'claim.json'))}
        save(destination/'run.json',run)
        after=inventory(source)
        if after!=before:raise ValueError('Failed source changed during recovery preparation')
        proof=dict(passed=True,policy=POLICY,**binding,parent_inventory=before,
            parent_inventory_sha256=hashlib.sha256(canonical(before)).hexdigest(),source_unchanged=True,
            checkpoint_readback=receipt,rejected_checkpoint_candidates=rejected,
            completed_sessions_preserved=state['sessions'],assignments_preserved=state['position'],
            interrupted_sessions_in_parent_tail=interrupted,cumulative_interrupted_sessions=cumulative,
            abandoned_tail_simulation_seconds=max(0,max([r['sim_time'] for r in tail]+[r['last'] for r in read(source/'replay/index.json')])-state['world']['sim_time']),
            recovery_rule='Restore last verified clean boundary. Preserve and separately count abandoned attempts; never count them as successful closed sessions.',
            native_retry=False,model_calls=0)
        save(destination/'recovery-ready.json',proof)
        if run['stage']=='official':
            lineage['history'].append(dict(source=str(source),destination=str(destination),receipt_sha256=sha(destination/'recovery-ready.json')))
            lineage['active_root']=str(destination);save(lineage_path,lineage)
        return {k:v for k,v in proof.items() if k!='parent_inventory'}
    except BaseException as error:
        save(destination/'recovery-preparation-failure.json',dict(error=repr(error),claim=str(claim/'claim.json')))
        raise
