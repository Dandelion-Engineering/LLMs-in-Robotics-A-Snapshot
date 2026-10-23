"""Prepare diagnostic005 without launching a process, model or trace."""
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent.parent
sys.path.insert(0,str(HERE.parent/'single-interrupt-diagnostic-v5'))
import common
REPO=common.REPO
MAP=common.RCI.parent/'Architecture Map'


def identity(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':common.sha(path),'bytes':path.stat().st_size}


def verify_checks():
    rows=[]
    for name in ('control-tests-002','wrapper-tests-001','launcher-checks-001'):
        path=HERE/name/'receipt.json';value=common.read(path)
        common.require(value.get('passed') is True and value.get('model_calls')==0,'Passing no-model checks required')
        for row in value['sources']:
            common.require(common.sha(row['path'])==row['sha256']==common.sha(row['copy']),
                           'Tested source or preserved source copy changed: '+row['path'])
        rows.append(identity(path))
    return rows


def candidate():
    verify_checks()
    previous=common.read(common.PREVIOUS)
    common.require(len(previous['sources'])==958,'Unexpected dev096 source inventory')
    for name,old in previous['sources'].items():
        current=identity(REPO/name)
        common.require({'sha256':current['sha256'],'bytes':current['bytes']}==old,'Previously frozen source changed: '+name)
    baseline=common.read(MAP/'releases/RCI001-wsl-010d/snapshot.json')
    common.require(len(baseline['sources'])==624,'Original source inventory differs')
    common.require(all(previous['sources'].get(name)==row for name,row in baseline['sources'].items()),
                   'Original624 preservation failed')
    value=common.read(common.REFERENCE)
    paths=set(common.required_inputs())|{(HERE/'launcher-checks-001/receipt.json').relative_to(REPO).as_posix()}
    value.update(run_id=common.RUN,framework_revision=common.REVISION,qualification_stage=common.STAGE,
        outer_campaign_protocol=common.PROTOCOL,model_turns_max=1,runtime_workspace=str(common.WORKSPACE),
        runtime_input_files=sorted(paths))
    common.validate_manifest(value)
    return value


def load_registry():
    spec=importlib.util.spec_from_file_location('native_os_closure_registry',CAMPAIGN/'registry.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=module.common
    def author(identifier):
        row=original(identifier);row['author']='Codex session 18';return row
    module.common=module.prior.common=author
    return module


def main():
    value=candidate()
    common.require(not common.ROOT.exists() and not common.SNAPSHOT.parent.exists(),'Fresh diagnostic identity required')
    common.output_paths(common.EVIDENCE,common.HOST,common.WORKSPACE)
    registry=load_registry();data,_,_=registry.prior.store(MAP)
    known={row['id'] for records in data.values() for row in records}
    common.require(common.RUN not in known and common.REVISION not in known,'Map identity already allocated')
    common.ROOT.mkdir()
    common.save(common.MANIFEST,value)
    common.save(common.ROOT/'preparation-receipt.json',{'run':common.RUN,'revision':common.REVISION,
        'manifest':identity(common.MANIFEST),'method':identity(common.METHOD),'checks':verify_checks(),
        'previous958_unchanged':True,'original624_unchanged':True,'source_count':len(value['runtime_input_files']),
        'model_invocations_max':1,'diagnostic_only':True,'qualifier_claim':False,'scorable':False,
        'model_calls':0,'trace_starts':0,'observer_config_created':False})
    print(json.dumps({'prepared':True,'manifest':identity(common.MANIFEST),'source_count':len(value['runtime_input_files'])}))


if __name__=='__main__':main()
