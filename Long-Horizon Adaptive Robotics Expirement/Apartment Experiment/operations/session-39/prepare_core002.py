"""Correct an obsolete v1 tour turn while preserving all current gates."""
import ast
from attempts import *
from prepare_suites import source_files

prior=read(ROOT/'core001/output/result.json')
assert prior['passed'] is False and prior['checks']['all_four_toy_pick_carry_release'] is True
original=HERE/'current_navigation_fixture.py';tree=ast.parse(original.read_text(encoding='utf-8'));changed=[]
class RouteCorrection(ast.NodeTransformer):
    def visit_For(self,node):
        if isinstance(node.iter,ast.List):
            route=ast.literal_eval(node.iter)
            if (9.1,4.05) in route:
                assert len(route)==15 and route[7:10]==[(9.1,5.6),(9.1,4.05),(9.85,4.05)]
                route[8]=(9.85,5.6);node.iter=ast.parse(repr(route),mode='eval').body
                changed.append(dict(old=[9.1,4.05],new=[9.85,5.6]))
        return self.generic_visit(node)
tree=RouteCorrection().visit(tree);assert len(changed)==1
target=HERE/'current_navigation_fixture002.py'
with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write('# Frozen fixture correction; see CORE-FIXTURE-CORRECTION.md.\n'+ast.unparse(tree)+'\n')
register('core002','core_suite.py','Same five applicable regression groups after correcting the obsolete v1 full-tour turn beside the current drawer bank. Only (9.1,4.05) becomes (9.85,5.6); all rooms, usable charger approaches, physical docking and exact 10x return-reserve gate retained. No production/scientific change.',source_files()+[(HERE/'current_toy_fixture.py','current_toy_fixture.py'),(target,'current_navigation_fixture.py'),(HERE/'CORE-FIXTURE-CORRECTION.md','CORE-FIXTURE-CORRECTION.md')],[dict(route_correction=changed,unchanged_gate='3600 > 10 * full_apartment_tour_duration',groups=5)],prior='APARTMENT-s39-core001')
build()
