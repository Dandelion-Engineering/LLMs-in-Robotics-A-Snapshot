"""Adapt only obsolete v1 fixture scope to the unchanged current v3 apparatus."""
import ast
from attempts import *
from prepare_suites import source_files

assert read(ROOT/'preservation002/output/result.json')['passed']
source=RELEASE/'frozen_repository'/APP.relative_to(REPO)
generated=[]
for name,destination in [('task_engineering.py','current_toy_fixture.py'),('navigation_engineering.py','current_navigation_fixture.py')]:
    tree=ast.parse((source/name).read_text(encoding='utf-8'));changed=[]
    class CurrentFixture(ast.NodeTransformer):
        def visit_For(self,node):
            if name=='task_engineering.py' and isinstance(node.target,ast.Name) and node.target.id=='drawer':
                assert ast.literal_eval(node.iter)==('A','B');changed.append('old_kitchen_fixture_replaced_by_current_geometry_suite');return None
            if name=='navigation_engineering.py' and ast.unparse(node.iter)=='enumerate(CHARGERS)':
                node.iter=ast.parse('[(i, CHARGERS[i]) for i in (0, 2)]',mode='eval').body
                changed.append('current_usable_chargers_only_bedroom_barrier_checked_separately')
            return self.generic_visit(node)
    tree=CurrentFixture().visit(tree);assert len(changed)==1,(name,changed)
    path=HERE/destination
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write('# Current apparatus fixture scope; see immutable attempt manifest.\n'+ast.unparse(tree)+'\n')
    generated.append((path,destination))
register('core001','core_suite.py','Fresh complete applicable regression groups: all four toy pick/carry/release cycles and bedroom success; living-room/kitchen charger approaches and the full four-room return tour with unchanged 10x reserve gate; original high-write/content, million-frame metadata and native-stream failure checks; exact frozen-layout native preflight. Historical v1 kitchen coordinates are replaced by the mandatory current both-drawer geometry suite already in offline/physics; the intentionally blocked bedroom charger is checked there as blocked, not falsely required to dock.',source_files()+generated,[
    'No production/scientific change. Fixture scope adaptations fixed before execution to match the established v3 geometry.',
    'Both drawers, inaccessible bedroom charger and other sensor/physics gates remain mandatory in offline001 and physics001.',
    'Storage and stream bounded stress and real frozen-layout preflight; no provider calls.'])
build()
