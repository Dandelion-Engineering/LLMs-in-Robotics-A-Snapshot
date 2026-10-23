from release2 import *

for name in ('retirement001','workspace002','offline002','recorder002','physics002','core005','native002'):
    assert read(ROOT/name/'output/result.json')['passed'] is True,name
    receipt=read(HERE/(name+'-terminal.json'))
    assert receipt['state']=='succeeded' and type(receipt['exit_status']) is int and receipt['exit_status']==0,name
text=(APP/'operations/session-38/audit_workspace.py').read_text(encoding='utf-8')
text=text.replace("QUALIFIED=BASE/'qualification008'","QUALIFIED=BASE/'workspace002'")
text=text.replace("QUALIFICATIONS=sorted(BASE.glob('qualification[0-9]*'))","QUALIFICATIONS=sorted(BASE.glob('workspace[0-9]*'))")
text=text.replace("PROFILE=BASE/'profile001'","PROFILE=Path('D:/Dandelion-Apartment-Experiment/engineering/workspace-session38/profile001')")
text=text.replace("for root in (PROFILE,*QUALIFICATIONS,*sorted(BASE.glob('audit[0-9]*'))):", "for root in (PROFILE,*[p for p in sorted(BASE.iterdir()) if p.is_dir() and (p/'manifest.json').exists()]):")
target=HERE/'workspace_reader2.py'
with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
register('audit002','commission_audit2.py','Independent complete fresh release002 audit: raw retirement/physics/workspace/core evidence, four native threads with image/journal/checkpoint/replay readback, actual retirement, and all 75 original roots rehashed. Preserve failed release001/native001 and preliminary outcomes.',source_files()+[(target,'workspace_reader.py')],['All original integrated gates and new guarded retirement gate; no stale certificates'])
build()
