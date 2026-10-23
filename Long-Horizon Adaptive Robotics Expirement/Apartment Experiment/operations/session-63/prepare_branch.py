"""Explicit operator C: recovery; frozen recovery guard remains untouched."""
import uuid
from common63 import *
from common import copy_durable
from recording import copy_tree, verify_checkpoint, verify_prefix, verify_namespace

POLICY = 'operator-c-checkpoint5-branch-session63-1'

def safe_path(path, allowed):
    path=Path(path).resolve();allowed=Path(allowed).resolve()
    assert path.is_relative_to(allowed) and path!=allowed and path.drive.upper()==allowed.drive.upper(), 'Path outside explicit operator scope'
    for ancestor in [path,*path.parents]:
        if ancestor.exists(): assert not ancestor.is_symlink() and not ancestor.is_junction(), 'Path alias forbidden'
    return path

def verify_branch(root):
    root=Path(root); state=read(CP/'state.json'); run=read(root/'run.json')
    binding=run['recovery'];claim=read(binding['claim']);ready=read(root/'recovery-ready.json')
    assert Path(binding['source']).resolve()==PARENT.resolve() and Path(binding['destination']).resolve()==root.resolve()
    assert binding['checkpoint_sha256']==EXPECTED_CP and claim['checkpoint_sha256']==EXPECTED_CP
    assert claim['branch_id']==run['branch_id'] and Path(claim['destination']).resolve()==root.resolve()
    assert ready['claim_sha256']==sha(binding['claim']) and ready['passed'] is True
    expected=read(PARENT/'run.json');expected.update(branch_id=run['branch_id'],recovery=binding)
    assert run==expected, 'Scientific run metadata changed'
    for name in ('schedule.json','config.json','initial-filesystem.json'):assert sha(root/name)==sha(PARENT/name)
    for name in ('filesystem','filesystem-objects'):assert inventory(root/name)==inventory(CP/name),name
    assert sha(root/'filesystem-namespace.json')==sha(CP/'filesystem-namespace.json')
    verify_namespace(root)
    newcp=root/'checkpoints/session-00005'
    assert inventory(newcp)==inventory(CP)
    assert (root/'events.jsonl').stat().st_size==state['log_bytes']
    assert sha(root/'events.jsonl')==state['event_prefix_sha256']
    assert sha(root/'replay/index.json')==state['replay_index_sha256']
    index=read(CP/'replay-index.json')
    assert set(p.name for p in (root/'replay').iterdir())=={'index.json',*(r['file'] for r in index)}
    rows=[json.loads(l) for l in (root/'events.jsonl').read_bytes().splitlines()]
    sensors={}
    for r in rows:
        if r['kind']=='sensor_capture':
            name='frame-'+str(r['payload']['sequence']).zfill(7)+'.png';sensors[name]=r['payload']['image_sha256']
    assert set(p.name for p in (root/'sensors').iterdir())==set(sensors)
    for name,digest in sensors.items():assert sha(root/'sensors'/name)==digest
    assert set(p.name for p in (root/'sessions').iterdir())=={'session-'+str(n).zfill(5) for n in range(1,6)}
    assert set(p.name for p in (root/'checkpoints').iterdir())=={'session-'+str(n).zfill(5) for n in range(1,6)}
    for number in range(1,6):
        sid='session-'+str(number).zfill(5)
        for name in ('sessions/'+sid,'filesystem-before-'+sid,'checkpoints/'+sid):assert inventory(root/name)==inventory(PARENT/name),name
        verify_checkpoint(root/'checkpoints'/sid);verify_prefix(root,root/'checkpoints'/sid)
    pointer=read(root/'latest-checkpoint.json');assert Path(pointer['path']).resolve()==newcp.resolve()
    assert pointer['manifest_sha256']==EXPECTED_CP
    return dict(passed=True,files=len(inventory(root)),checkpoint=verify_checkpoint(newcp),prefix=verify_prefix(root,newcp),
        accepted_sessions=5,advancements=2,abandoned_parent_model_calls=1,sensors=len(sensors),replay_chunks=len(index),
        exact_inode_namespace=True,failed_session6_not_transferred=True)

def prepare(destination,claim_dir,*,qualification=False,fault=None):
    allowed=QUAL if qualification else BASE
    destination=safe_path(destination,allowed)
    assert qualification or destination==DEST.resolve()
    claim_dir=Path(claim_dir).resolve()
    parent_run=read(PARENT/'run.json')
    if qualification:safe_path(claim_dir,QUAL)
    else:assert claim_dir== (PAIR/'recovery-claims'/parent_run['branch_id']).resolve()
    assert not destination.exists(), 'Destination already exists'
    assert not claim_dir.exists(), 'Parent already claimed, including a partial failed claim'
    assert not (PARENT/'running.lock').exists() and not (PARENT/'completed.json').exists()
    from run import verify_run
    from recovery import terminal
    verify_run(PARENT,True)
    assert read(PARENT/'config.json')['recovery_policy']=='verified-boundary-branch-1'
    execution=terminal(PARENT)
    assert not execution['passed'] and execution['retirement']['all_retired'] is True
    assert sha(CP/'manifest.json')==EXPECTED_CP and sha(CP/'state.json')==EXPECTED_STATE
    verify_checkpoint(CP);verify_prefix(PARENT,CP)
    route=read(legacy.HERE/'storage-route.json')
    assert Path(route['active_storage_root']).resolve()==PARENT.resolve() and route['branch_id']==parent_run['branch_id']
    lineage=read(PAIR/'maps-lineage.json')
    assert Path(lineage['active_root']).resolve()==(PAIR/'maps').resolve() and lineage['history']==[]
    before=inventory(PARENT);state=read(CP/'state.json')
    branch_id=uuid.uuid4().hex
    binding=dict(source=str(PARENT),destination=str(destination),branch_id=branch_id,checkpoint=str(CP),checkpoint_sha256=EXPECTED_CP,
        reason='Randy authorized one same-apparatus operator C: checkpoint-5 restoration; original session 6 is abandoned, never silently retried.')
    claim_dir.parent.mkdir(parents=True,exist_ok=True);claim_dir.mkdir(exist_ok=False)
    save(claim_dir/'claim.json',binding)
    save(claim_dir/'operator-authority.json',dict(policy=POLICY,qualification_fixture=qualification,authority=ref(HERE/'authority-original.md'),
        operator_manifest=ref(HERE/'qualification-manifest.json'),storage_route=ref(legacy.HERE/'storage-route.json'),prior_lineage=ref(PAIR/'maps-lineage.json'),
        parent_inventory_sha256=hashlib.sha256(canonical(before)).hexdigest(),frozen_recovery_unmodified=ref(CODE/'recovery.py')))
    destination.mkdir(parents=True,exist_ok=False)
    try:
        if fault:fault('claimed')
        for name in ('schedule.json','config.json','initial-filesystem.json'):copy_durable(PARENT/name,destination/name)
        for name in ('filesystem','filesystem-objects'):copy_tree(CP/name,destination/name)
        copy_durable(CP/'filesystem-namespace.json',destination/'filesystem-namespace.json')
        with (PARENT/'events.jsonl').open('rb') as incoming,(destination/'events.jsonl').open('xb') as outgoing:
            left=state['log_bytes']
            while left:
                block=incoming.read(min(left,1024*1024));assert block,'Truncated event prefix'
                outgoing.write(block);left-=len(block)
            outgoing.flush();os.fsync(outgoing.fileno())
        for row in read(CP/'replay-index.json'):copy_durable(PARENT/'replay'/row['file'],destination/'replay'/row['file'])
        copy_durable(CP/'replay-index.json',destination/'replay/index.json')
        for line in (destination/'events.jsonl').read_bytes().splitlines():
            row=json.loads(line)
            if row['kind']=='sensor_capture':
                name='frame-'+str(row['payload']['sequence']).zfill(7)+'.png'
                assert sha(PARENT/'sensors'/name)==row['payload']['image_sha256']
                copy_durable(PARENT/'sensors'/name,destination/'sensors'/name)
        for number in range(1,6):
            sid='session-'+str(number).zfill(5)
            for name in ('sessions/'+sid,'filesystem-before-'+sid,'checkpoints/'+sid):copy_tree(PARENT/name,destination/name)
        newcp=destination/'checkpoints/session-00005'
        save(destination/'latest-checkpoint.json',dict(path=str(newcp),**verify_checkpoint(newcp)))
        verify_prefix(destination,newcp)
        save(destination/'run.json',dict(parent_run,branch_id=branch_id,recovery=dict(binding,claim=str(claim_dir/'claim.json'))))
        assert inventory(PARENT)==before,'Parent changed during preparation'
        save(destination/'recovery-ready.json',dict(passed=True,policy=POLICY,**binding,claim_sha256=sha(claim_dir/'claim.json'),
            parent_inventory_sha256=hashlib.sha256(canonical(before)).hexdigest(),source_unchanged=True,checkpoint_readback=verify_checkpoint(newcp),
            completed_sessions_preserved=5,assignments_preserved=2,interrupted_sessions_in_parent_tail=1,cumulative_interrupted_sessions=1,
            native_retry=False,model_calls=0,qualification_fixture=qualification,authority=ref(HERE/'authority-original.md')))
        result=verify_branch(destination)
        verify_run(destination,True)
        save(claim_dir/'prepared.json',dict(ready=ref(destination/'recovery-ready.json'),verification=result,created_utc=now()))
        return result
    except BaseException as error:
        save(destination/'recovery-preparation-failure.json',dict(error=repr(error),claim=str(claim_dir/'claim.json')))
        raise
