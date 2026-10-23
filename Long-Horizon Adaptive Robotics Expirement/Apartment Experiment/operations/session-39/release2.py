"""Once-only release002 freeze and attempt registration configuration."""
import attempts as engine
from attempts import *

engine.RELEASE=ROOT/'release002'
engine.RID='APARTMENT-s39-release002'
RELEASE=engine.RELEASE
RID=engine.RID

def source_files():
    source=RELEASE/'frozen_repository'/APP.relative_to(REPO)
    origin=HERE/'source-origin002.json'
    if not origin.exists():save(origin,dict(repository=str(RELEASE/'frozen_repository')))
    return [(p,'source/'+p.name) for p in source.iterdir() if p.is_file() and p.suffix in ('.py','.html','.md','.json')]+[(origin,'source/source-origin.json')]

def freeze():
    assert not RELEASE.exists()
    assert not Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4').exists()
    sys.path.insert(0,str(APP))
    from run import source_identity
    from environment import identity
    from revision_config import CONFIG
    source=source_identity();env=identity();parent=read(ROOT/'release001/manifest.json')
    changed=sorted(k for k in source if source[k]!=parent['source_identity'].get(k))
    assert changed==['apartment/journal_service.py','apartment/native_runtime.py','apartment/workspace_lifecycle.py'],changed
    assert set(source)==set(parent['source_identity']) and env==parent['environment'] and CONFIG==parent['config']
    frozen=RELEASE/'frozen_repository';frozen.mkdir(parents=True)
    integration=Path('Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001')
    apartment=APP.relative_to(REPO)
    for key,digest in source.items():
        if key.startswith('apartment/'):relative=apartment/key.removeprefix('apartment/')
        elif key.startswith('inherited/'):relative=integration/key.removeprefix('inherited/')
        elif key.startswith('repository/'):relative=Path(key.removeprefix('repository/'))
        else:relative=Path(key.removeprefix('template/'))
        target=frozen/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(REPO/relative,target);assert sha(target)==digest,key
    docs=[APP/n for n in ('COMPARISON.md','ANALYSIS.md','CUP-PHYSICS-REVISION.md','RELIABILITY-REVISION.md','calibration.json','audit-inputs.json')]
    docs += [HERE/n for n in ('PROTOCOL.md','authority-original.md','RETIREMENT-REPAIR-PROTOCOL.md')]
    docs += [APP.parent/'Apartment Long-Lived Robot Experiment Design.md']
    for p in docs:
        target=frozen/p.relative_to(REPO);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    manifest=dict(schema='apartment-s39-release-1',revision_id=RID,source_identity=source,environment=env,config=CONFIG,
        parent_release_manifest_sha256=sha(ROOT/'release001/manifest.json'),changed_from_parent=changed,
        files=inventory(frozen),protocol_sha256={str(p.relative_to(APP)):sha(p) for p in docs if p.is_relative_to(APP)},
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),created_at=datetime.now(timezone.utc).isoformat(),official_prepared=False,official_launched=False,
        authority=ref('Randy ordered commissioning and Baseline authority',HERE/'authority-original.md'))
    save(RELEASE/'manifest.json',manifest)
    actual=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B','-c','import run,json;print(json.dumps(run.source_identity()))'],cwd=frozen/apartment,text=True,encoding='utf-8'))
    assert actual==source
    append('revision',base()|dict(id=RID,architecture_id='APARTMENT-001',parent_revision_id='APARTMENT-s39-release001',status='frozen',title='Cooperative native FUSE retirement candidate',summary='Exact release001 apparatus with guarded clean libfuse exit after outer unmount; full fresh commissioning mandatory.',mechanism='Controller ownership, absent mount and no-open-handle fences precede locked exit request. Harmless wake interrupts native FUSE read; actual destroy and zero native return remain mandatory. All science, time budgets, templates and parameters unchanged.',attachments=[],details={'manifest':ref('Frozen release002 candidate',RELEASE/'manifest.json'),'repair_protocol':ref('Predeclared retirement repair protocol',HERE/'RETIREMENT-REPAIR-PROTOCOL.md')}))
    build()

if __name__=='__main__':freeze()
