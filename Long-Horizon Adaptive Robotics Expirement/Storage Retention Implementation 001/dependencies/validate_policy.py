"""Validate unchanged current readers with all nonretained r4 frames unavailable.

This process-local filesystem guard does not mutate evidence or frozen code.
The actual 005 reader and 007 package comparator run with their original checks.
"""
from __future__ import annotations
import argparse
import builtins
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import gc
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from urllib.parse import unquote

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
EXP=ROOT/'Long-Horizon Adaptive Robotics Expirement'
ATTEMPTS=EXP/'Evidence/releases/batch01-eval-r4/attempts'
SITE=EXP/'Engineering Investigation 007/site-r4-003'

def source(path):
    data=Path(path).read_bytes()
    return {'path':str(Path(path).resolve()),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module
def paths_from_manifest(path):
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rt',encoding='utf-8') as f:
        return {os.path.normcase(os.path.abspath(ROOT/json.loads(line)['path'])) for line in f}

@contextmanager
def retained_only(allowed):
    original_open=builtins.open; original_io_open=io.open
    original_stat=Path.stat;original_exists=Path.exists;original_is_file=Path.is_file
    denied=[]
    prefix=os.path.normcase(str(ATTEMPTS.resolve()))+os.sep
    def unavailable(path):
        if isinstance(path,int):return False
        try:normalized=os.path.normcase(os.path.abspath(os.fspath(path)))
        except TypeError:return False
        if not normalized.startswith(prefix):return False
        suffix=normalized[len(prefix):].replace('\\','/')
        parts=suffix.split('/')
        return (len(parts)>=4 and parts[1:3]==['evidence','frames']
                and Path(normalized).suffix.lower() in ('.png','.npz') and normalized not in allowed)
    def fail(path,operation):
        denied.append({'path':str(path),'operation':operation})
        raise FileNotFoundError('Intentionally unavailable under staged retention policy: '+str(path))
    def checked_open(file,*args,**kwargs):
        if unavailable(file):fail(file,'open')
        return original_open(file,*args,**kwargs)
    def checked_io_open(file,*args,**kwargs):
        if unavailable(file):fail(file,'io.open')
        return original_io_open(file,*args,**kwargs)
    def checked_stat(path,*args,**kwargs):
        if unavailable(path):fail(path,'stat')
        return original_stat(path,*args,**kwargs)
    def checked_exists(path):
        if unavailable(path):denied.append({'path':str(path),'operation':'exists'});return False
        return original_exists(path)
    def checked_is_file(path):
        if unavailable(path):denied.append({'path':str(path),'operation':'is_file'});return False
        return original_is_file(path)
    builtins.open=checked_open;io.open=checked_io_open
    Path.stat=checked_stat;Path.exists=checked_exists;Path.is_file=checked_is_file
    try:yield denied
    finally:
        builtins.open=original_open;io.open=original_io_open
        Path.stat=original_stat;Path.exists=original_exists;Path.is_file=original_is_file

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--required',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--windows',type=Path)
    parser.add_argument('--phase',choices=['staged','post'],required=True)
    parser.add_argument('--actual-reader',choices=['first','all'],default='all')
    args=parser.parse_args()
    sys.path.insert(0,str(EXP/'Runtime Recovery 001'))
    import recovery_runner
    job=recovery_runner.queued_job(expected_script=__file__)
    allowed=paths_from_manifest(args.required)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'format':'retained-policy-current-consumers-1','status':'failed','phase':args.phase,
            'queue_job_id':job['id'],'required_manifest':source(args.required),'started_at':datetime.now(timezone.utc).isoformat(),
            'validator_source':source(__file__),
            'guard':'For affected r4 frames absent from required manifest, Path.exists/is_file return false and stat/open raise FileNotFoundError. No historical source or test is changed.',
            'actual_reader_traces':[]}
    failure=None
    try:
        if args.windows:
            checker=load_module('retention_window_checker',HERE/'validate_windows.py')
            report['diagnostic_window_completeness']=checker.validate(args.required,args.windows)
            report['diagnostic_window_checker_source']=source(HERE/'validate_windows.py')
        # The guard proves fail-closed behavior on an existing would-retire file.
        if args.phase=='staged':
            probe=next(p for d in sorted(ATTEMPTS.iterdir()) if (d/'evidence/frames').is_dir()
                       for p in (d/'evidence/frames').iterdir()
                       if p.suffix in ('.png','.npz') and os.path.normcase(os.path.abspath(p)) not in allowed)
        else:
            probe=ATTEMPTS/'batch01-eval-r4-C01-rep1-baseline-persistent/evidence/frames/retention-policy-denied-probe.png'
        with retained_only(allowed) as denied:
            assert not probe.exists() and not probe.is_file()
            try:probe.open('rb')
            except FileNotFoundError:pass
            else:raise AssertionError('Guard permitted denied frame')
        report['guard_self_test']={'state':'passed','probe':str(probe),'probe_kind':'existing candidate' if args.phase=='staged' else 'absent synthetic path','denials':len(denied)}
        builder=load_module('build_workspace',EXP/'Engineering Investigation 007/build_workspace.py')
        before=builder.source_inventory()
        package=json.loads((SITE/'package-manifest.json').read_text())
        report['current_package']=source(SITE/'package-manifest.json')
        report['all12_trace_manifests']=[source(SITE/unquote(t['package']['manifest']['href'])) for t in package['trace_checks']]
        for trace,identity in zip(package['trace_checks'],report['all12_trace_manifests']):
            assert identity['sha256']==trace['package']['manifest']['sha256'] and identity['bytes']==trace['package']['manifest']['bytes']
        selection_path=EXP/'Batch 01/evaluation-trace-selection-r4.json'
        directories,selection=builder.original.select_traces(selection_path,[])
        assert len(selection['runs'])==12
        limit=12 if args.actual_reader=='all' else 1
        with retained_only(allowed) as denied:
            # Use the exact production source-bound derivative and analysis path,
            # including selected-result/provenance arguments to the trace reader.
            submitted=EXP/'Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation007-003-submission.json'
            argv=json.loads(submitted.read_text())['argv']
            arg={argv[i]:Path(argv[i+1]) for i in range(len(argv)-1)
                 if argv[i] in ('--analysis-file','--analysis-provenance','--analysis-receipt','--evaluation-index','--evaluation-receipt')}
            output=SITE/'index.html'
            canonical=builder.original.load_snapshot(EXP/'Architecture Map',output)
            analysis=builder.original.read_analysis(arg['--analysis-file'],output)
            derivatives=builder.original.read_derivatives(arg['--evaluation-index'],arg['--evaluation-receipt'],output,
                canonical_files=canonical['file_sha256'],paired_analysis=analysis)
            bound=builder.original.bind_analysis(analysis,arg['--analysis-provenance'],arg['--analysis-receipt'],output,derivatives=derivatives)
            assert bound['binding']['state']=='verified' and len(derivatives['runs'])==264
            selected={row['run_id']:row for row in derivatives['runs']}
            report['source_bound_derivatives']={'state':'verified','planned_dispositions':len(derivatives['runs']),
                'analysis_unchanged':bound['report']==analysis['report'],'sources':[source(p) for p in arg.values()]}
            # All twelve current manifests and preserved first-trace source-bound
            # validation are checked against the same policy, even in first mode.
            manifests=[(SITE,t['package']['manifest']) for t in package['trace_checks']]
            validation=EXP/'Evidence/derived/investigation007-package-validation-004/first-declared-trace'
            saved=json.loads((validation/'descriptor.json').read_text())
            manifests.append((validation,saved['package']['manifest']))
            counts=[]
            for directory,ref in manifests:
                raw=(directory/unquote(ref['href'])).read_bytes()
                assert len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
                m=json.loads(raw);n=0
                for event in m['event_headers']:
                    for a in event.get('artifact_refs',{}).values():
                        if a.get('state')!='available':continue
                        p=(directory/unquote(a['href'])).resolve()
                        assert p.is_file() and p.stat().st_size==a['bytes']
                        n+=1
                counts.append({'run_id':m['run_id'],'manifest_sha256':ref['sha256'],'available_frame_references':n})
            report['all12_and_saved_validation_dependencies']=counts
            for ordinal,(entry,directory) in enumerate(zip(selection['runs'][:limit],directories[:limit])):
                check=package['trace_checks'][ordinal]
                manifest=json.loads((SITE/unquote(check['package']['manifest']['href'])).read_text())
                descriptor={**manifest['metadata'],'package':check['package']}
                row=selected.get(entry['run_id'],{})
                run=builder.original.read_selected_trace(entry,directory,SITE/'index.html',2,5,
                    selected_result=row.get('selected_result'),selection_provenance=row.get('selection_provenance'))
                verified=builder.trace_package.verify_trace(run,descriptor,SITE)
                assert verified['state']=='verified' and verified['full_metadata_roundtrip_equal']
                row={'run_id':entry['run_id'],'ordinal':ordinal,'state':'passed','exact_historical_package_equal':True,'verification':verified}
                report['actual_reader_traces'].append(row)
                print(json.dumps(row),flush=True)
                del run;gc.collect()
            explorer=load_module('retention_explorer_validator',EXP/'Task and Architecture Explorer/validate_report.py')
            buf=io.StringIO()
            with redirect_stdout(buf):explorer.main()
            report['explorer']=json.loads(buf.getvalue())
            assert report['explorer']['state']=='passed'
        report['unexpected_policy_denials']=denied
        if denied:raise ValueError('An intended current consumer requested a retired frame')
        builder.verify_upstream();builder.original.verify_upstream()
        after=builder.source_inventory()
        if before!=after:raise ValueError('Current presentation source changed during policy validation')
        report['presentation_sources']=before
        report['original_reader_source']=source(EXP/'Engineering Investigation 005/evidence_adapter.py')
        report['original_package_comparator_source']=source(EXP/'Engineering Investigation 007/trace_package.py')
        report['numerical_dependency_check']={'kind':'source inspection plus preserved stream identities; no new scientific interpretation',
            'sources':[source(EXP/name) for name in ['Runtime 004/diagnostics.py','Engineering Investigation 005/continuity.py','Engineering Investigation 005/qualified_restart.py','Runtime 004/protocol.py','Batch 01/Release Analysis 005/analyze_results.py']],
            'finding':'Aggregate uses compact results/manifests. Diagnostics uses events/motion/result. Continuity uses events/result/protected snapshots and qualified calibration references; it does not open r4 PNG/NPZ bodies. All such non-image evidence remains preserved. Full diagnostics and continuity were not recomputed by this presentation gate.'}
        if source(__file__)!=report['validator_source']:raise ValueError('Validator source changed during execution')
        report['status']='passed'
    except Exception as exc:
        failure=exc;report['error']=type(exc).__name__+': '+str(exc)
    report['ended_at']=datetime.now(timezone.utc).isoformat()
    with (out/'validation.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'status':report['status'],'actual_traces':len(report['actual_reader_traces']),'error':report.get('error')}))
    if failure:raise failure

if __name__=='__main__':main()
