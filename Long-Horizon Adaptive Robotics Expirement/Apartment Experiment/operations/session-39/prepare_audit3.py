"""New immutable complete audit after an evidenced reader filename correction."""
from release2 import *

previous=ROOT/'audit002'
assert read(previous/'output/result.json')['passed'] is False
terminal=read(HERE/'audit002-terminal.json')
assert terminal['state']=='failed' and type(terminal['exit_status']) is int and terminal['exit_status']==1
assert not (previous/'output/certificate.json').exists()
source=previous/'commission_audit2.py'
original=source.read_text(encoding='utf-8')
changes=[
    ("failed={'preservation001','core001','core002','core003','native001'}", "failed={'preservation001','core001','core002','core003','native001','audit002'}"),
    ("'physics002','core005','native002']\n    for name in names:", "'physics002','core005','native002','audit002']\n    for name in names:"),
    ("r=read(root/name/'result.json');assert r['passed'] and len(r['checks'])==count and all(r['checks'].values())", "r=read(root/name/('geometry.json' if name=='geometry' else 'result.json'));assert r['passed'] and len(r['checks'])==count and all(r['checks'].values())"),
]
modified=original
for old,new in changes:
    assert modified.count(old)==1,old
    modified=modified.replace(old,new)
compile(modified,'commission_audit3.py','exec')
target=HERE/'commission_audit3.py'
with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write(modified)
assert sha(HERE/'workspace_reader2.py')==sha(previous/'workspace_reader.py')
geometry=ROOT/'offline002/output/geometry/geometry.json'
value=read(geometry)
assert value['passed'] and len(value['checks'])==5 and all(value['checks'].values())
save(HERE/'audit-reader-correction.json',dict(
    failed_attempt='audit002',failed_queue=terminal['id'],parent_audit_sha256=sha(source),new_audit_sha256=sha(target),
    correction='Read the existing geometry/geometry.json artifact instead of nonexistent geometry/result.json; retain the same five checks and every other gate.',
    additional_change='Include immutable failed audit002 source, result and actual queue receipt in the independent receipt audit.',
    replacement_count=len(changes),geometry_evidence=ref('Unchanged five-gate offline geometry result',geometry),
    apparatus_changed=False,gates_relaxed=False,qualified_attempts_rerun=False))
register('audit003','commission_audit3.py','Full independent release002 audit with corrected geometry artifact locator; same ten groups and gates, plus authentication of retained failed audit002. No model calls or official writes.',
    source_files()+[(HERE/'workspace_reader2.py','workspace_reader.py'),(HERE/'audit-reader-correction.json','audit-reader-correction.json')],
    ['All original integrated and guarded-retirement gates; complete original-root rehash; preserved failed audit002'],prior='APARTMENT-s39-audit002')
build()
