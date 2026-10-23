from attempts import *
from prepare_suites import source_files

for name in ('workspace001','offline001','recorder001','physics001','core004','native001'):
    assert read(ROOT/name/'output/result.json')['passed'] is True,name
core=read(ROOT/'core003/output/result.json')
assert core['passed'] is False and all(core['checks'][n] for n in ('all_four_toy_pick_carry_release','usable_chargers_and_return_reserve','storage_and_million_frame_fidelity'))
source=APP/'operations/session-38/audit_workspace.py'
text=source.read_text(encoding='utf-8')
text=text.replace("QUALIFIED=BASE/'qualification008'","QUALIFIED=BASE/'workspace001'")
text=text.replace("QUALIFICATIONS=sorted(BASE.glob('qualification[0-9]*'))","QUALIFICATIONS=sorted(BASE.glob('workspace[0-9]*'))")
text=text.replace("PROFILE=BASE/'profile001'","PROFILE=Path('D:/Dandelion-Apartment-Experiment/engineering/workspace-session38/profile001')")
# The original retirement reader covered workspace qualification only. Its
# process/mount/log checks now cover every manifest-bound attempt in this
# integrated campaign, including offline fixtures and all native pilot roots.
text=text.replace("for root in (PROFILE,*QUALIFICATIONS,*sorted(BASE.glob('audit[0-9]*'))):", "for root in (PROFILE,*[p for p in sorted(BASE.iterdir()) if p.is_dir() and (p/'manifest.json').exists()]):")
target=HERE/'workspace_reader.py'
with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
register('audit001','commission_audit.py','Independent fresh-release certification: raw fixed-gate readback, source/environment/config, four native threads and image transport, inode/replay/checkpoints, adversarial failure retirement and all earlier history preservation.',source_files()+[(target,target.name)],['All protocol gates; no inherited certificate substituted for fresh execution'])
build()
