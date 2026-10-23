"""Use the jointly clear doorway/drawer corridor; retain every prior failure."""
import ast
import math
from attempts import *
from prepare_suites import source_files

assert read(ROOT/'core002/output/result.json')['passed'] is False
tree=ast.parse((HERE/'current_navigation_fixture.py').read_text(encoding='utf-8'));changed=[]
radius=math.hypot(.28,.24);clearance=min(9.35-8.79,9.9-9.35)-radius
assert clearance>.18
class RouteCorrection(ast.NodeTransformer):
    def visit_For(self,node):
        if isinstance(node.iter,ast.List):
            route=ast.literal_eval(node.iter)
            if (9.1,4.05) in route:
                assert len(route)==15 and route[7:10]==[(9.1,5.6),(9.1,4.05),(9.85,4.05)]
                route[7:9]=[(9.35,5.6),(9.35,4.05)]
                node.iter=ast.parse(repr(route),mode='eval').body;changed.append('joint_doorway_drawer_corridor')
        return self.generic_visit(node)
tree=RouteCorrection().visit(tree);assert len(changed)==1
target=HERE/'current_navigation_fixture003.py'
with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write('# Frozen joint-clearance fixture; see CORE-FIXTURE-CORRECTION-002.md.\n'+ast.unparse(tree)+'\n')
register('core003','core_suite.py','Five unchanged applicable regression groups with a jointly clear doorway/drawer tour: only the original two x=9.1 waypoints at y=5.6/4.05 move to x=9.35. All rooms, ordinary physical docking and 3600 > 10 * tour_duration retained. Both earlier failed fixtures remain immutable; no production/scientific change.',source_files()+[(HERE/'current_toy_fixture.py','current_toy_fixture.py'),(target,'current_navigation_fixture.py'),(HERE/'CORE-FIXTURE-CORRECTION-002.md','CORE-FIXTURE-CORRECTION-002.md')],[dict(route_correction=changed,conservative_clearance_m=clearance,unchanged_gate='3600 > 10 * full_apartment_tour_duration',groups=5)],prior='APARTMENT-s39-core002')
build()
