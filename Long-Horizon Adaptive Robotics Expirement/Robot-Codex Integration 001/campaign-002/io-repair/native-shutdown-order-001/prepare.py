"""Prepare fresh diagnostic004 with exact previous inputs and tested additions."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
IO = HERE.parent
CAMPAIGN = IO.parent
REPO = CAMPAIGN.parent.parents[1]
MAP = CAMPAIGN.parent.parent/'Architecture Map'
WRAPPER = IO/'single-interrupt-diagnostic-v4'
sys.path.insert(0, str(WRAPPER))
import common

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def identity(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': common.sha(path), 'bytes': path.stat().st_size}

def verify_checks():
    state = common.read(HERE/'checks-state-002.json')
    common.require(state.get('passed') is True and state.get('sources_unchanged') is True,
                   'Final source-bound checks required')
    for row in state['sources']:
        common.require(identity(row['path']) == row, 'Tested source changed')
    for row in state['outputs']:
        common.require(identity(row['path']) == row, 'Test output changed')
    return state

def candidate():
    verify_checks()
    previous = common.read(MAP/'releases/RCI001-C02-dev-091/snapshot.json')
    paths = set(previous['sources']) | set(common.required_inputs())
    additions = list(HERE.glob('*.py')) + list(HERE.glob('*.md')) + [HERE/'checks-state.json',HERE/'checks-state-002.json']
    additions += [IO/directory/n for directory in ('checks-034','checks-035') for n in ('test-execution.json','harness.stdout','harness.stderr','assessment.stdout','assessment.stderr')]
    additions += [HERE/'wrapper-checks'/n for n in ('receipt.json','stdout','stderr')]
    additions += [HERE/'wrapper-checks-002'/n for n in ('receipt.json','stdout','stderr')]
    additions += [CAMPAIGN/'harness/test_native_shutdown_order.py']
    paths.update(p.relative_to(REPO).as_posix() for p in additions)
    value = common.read(common.REFERENCE)
    value.update(run_id=common.RUN, framework_revision=common.REVISION,
                 qualification_stage=common.STAGE, outer_campaign_protocol=common.PROTOCOL,
                 model_turns_max=1, runtime_workspace=str(common.WORKSPACE),
                 runtime_input_files=sorted(paths))
    common.validate_manifest(value)
    changed = {name for name, old in previous['sources'].items()
               if {'sha256': common.sha(REPO/name), 'bytes':(REPO/name).stat().st_size} != old}
    expected = {str(CAMPAIGN.relative_to(REPO)).replace('\\','/')+'/harness/'+name
                for name in ('codehost_bridge_v3.py','native_quiescence.py','test_native_owner_bootstrap.py')}
    expected.update((CAMPAIGN/'assessment'/name).relative_to(REPO).as_posix()
                    for name in ('raw_tool_result_reads.py','test_raw_tool_result_reads.py'))
    common.require(changed == expected, 'Unexpected shared-source changes')
    baseline = common.read(MAP/'releases/RCI001-wsl-010d/snapshot.json')
    common.require(len(baseline['sources']) == 624, 'Original source count differs')
    for name, row in baseline['sources'].items():
        common.require(previous['sources'].get(name) == row
                       and {'sha256':common.sha(REPO/name),'bytes':(REPO/name).stat().st_size} == row,
                       'Original source changed')
    return value, sorted(changed)

def main():
    value, changed = candidate()
    common.ROOT.mkdir(exist_ok=False)
    common.save(common.MANIFEST, value)
    common.save(common.ROOT/'preparation-receipt.json', {
        'diagnostic_only':True, 'model_invocations_max':1, 'resume_allowed':False,
        'run_id':common.RUN, 'revision':common.REVISION, 'author':'Codex session 15',
        'manifest':identity(common.MANIFEST), 'method':identity(common.METHOD),
        'shared_source_changes':changed, 'original624_verified':True,
        'checks':identity(HERE/'checks-state-002.json')})
    print(json.dumps({'manifest':identity(common.MANIFEST),'changed':changed}))

if __name__ == '__main__': main()
