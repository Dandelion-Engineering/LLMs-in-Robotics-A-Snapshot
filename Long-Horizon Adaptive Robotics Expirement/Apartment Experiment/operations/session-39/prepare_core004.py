"""Freeze the missing synthetic constructor fields; no production repair."""
import ast
from attempts import *
from prepare_suites import source_files

prior=read(ROOT/'core003/output/result.json')
assert prior['passed'] is False and all(prior['checks'][n] for n in ('all_four_toy_pick_carry_release','usable_chargers_and_return_reserve','storage_and_million_frame_fidelity'))
source=RELEASE/'frozen_repository'/APP.relative_to(REPO)/'native_stream_engineering.py'
tree=ast.parse(source.read_text(encoding='utf-8'));changed=0
for function in tree.body:
    if isinstance(function,ast.FunctionDef) and function.name=='fixture':
        for i,node in enumerate(function.body):
            if isinstance(node,ast.Assign) and ast.unparse(node.targets[0])=='client.args':
                function.body[i+1:i+1]=ast.parse('from structured_errors import FailureTrace\nclient.failure_trace=FailureTrace(client.args.redact_tokens)\nclient.args.apartment_failure_trace=client.failure_trace').body
                changed+=1;break
assert changed==1
target=HERE/'current_native_stream_fixture.py'
with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write('# Synthetic constructor-state repair only; see CORE-STREAM-FIXTURE.md.\n'+ast.unparse(tree)+'\n')
register('core004','core_native_suite.py','Complete the remaining stream and frozen-bundle groups. Synthetic object.__new__ fixture receives the same FailureTrace state as the actual production constructor; every original stream gate and real preflight remains unchanged. Preserve core003 as failed while using its three separately successful groups.',source_files()+[(target,target.name),(HERE/'CORE-STREAM-FIXTURE.md','CORE-STREAM-FIXTURE.md')],['Only synthetic constructor initialization added; no production/scientific change','Two remaining groups; no repetition of already successful four-toy, navigation and storage groups'],prior='APARTMENT-s39-core003')
build()
