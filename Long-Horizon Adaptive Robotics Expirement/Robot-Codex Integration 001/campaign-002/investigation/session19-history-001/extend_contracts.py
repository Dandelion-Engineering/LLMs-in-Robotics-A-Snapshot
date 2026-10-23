"""Extend presentation-only metadata contracts; retain exact before/after."""
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;I=HERE.parent;C=I.parent;REPO=C.parents[2]
M=C.parent.parent/'Architecture Map'

def replace(s,a,b):
    assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)

def main():
    bindings={}
    for rev,label,version,method in [('097','OBSERVED',5,'native-os-closure-001/DECLARATION.md'),
                                    ('098','GRACEFUL',6,'graceful-process-drain-001/DECLARATION.md')]:
        snapshot=json.loads((M/('releases/RCI001-C02-dev-'+rev+'/snapshot.json')).read_text(encoding='utf-8'))
        names=[f'io-repair/single-interrupt-diagnostic-v{version}/{f}.py' for f in ['run','common','launch']]+['io-repair/'+method]
        bindings[label]={name:snapshot['sources'][(C/name).relative_to(REPO).as_posix()] for name in names}
    extra='\nFAILED_BOUNDARY_SCHEMA = \'campaign002-failed-boundary-queue-1\'\n'
    for label,items in bindings.items():extra+=label+'_INTERRUPT_SOURCES = '+repr(items)+'\n'
    addition='''    elif row.get('run_id') == 'RCI001-C02-shutdown-diagnostic-005':
        run, revision = 'RCI001-C02-shutdown-diagnostic-005', 'RCI001-C02-dev-097'
        root = CAMPAIGN / 'io-repair/shutdown-diagnostic-005'
        script = CAMPAIGN / 'io-repair/single-interrupt-diagnostic-v5/run.py'
        protocol = 'RCI001-Campaign002-single-interrupt-diagnostic-v5'
        required_sources = OBSERVED_INTERRUPT_SOURCES
    elif row.get('run_id') == 'RCI001-C02-shutdown-diagnostic-006':
        if row.get('queue_completion_contract', row.get('queue_completion', {})).get('schema') != COMPLETED_INTERRUPT_SCHEMA:
            raise ValueError('Native006 requires the separate completed unassessed contract')
        run, revision = 'RCI001-C02-shutdown-diagnostic-006', 'RCI001-C02-dev-098'
        root = CAMPAIGN / 'io-repair/shutdown-diagnostic-006'
        script = CAMPAIGN / 'io-repair/single-interrupt-diagnostic-v6/run.py'
        protocol = 'RCI001-Campaign002-single-interrupt-diagnostic-v6'
        required_sources = GRACEFUL_INTERRUPT_SOURCES
'''
    boundary='''def failed_boundary_dispatch(row, job, paths, manifest, snapshot, manifest_hash):
    """Bind the no-model boundary command without opening its failed outputs."""
    run = row['run_id']; short = run.removeprefix('RCI001-C02-')
    if re.fullmatch(r'RCI001-C02-boundary-\\d{3}', run) is None:
        raise ValueError('Failed boundary run identity differs')
    script = CAMPAIGN/'qualification/boundary_suite_v3.py'
    mp = CAMPAIGN/'qualification'/(short+'-manifest.json')
    sp = CAMPAIGN.parent.parent/'Architecture Map/releases'/row['revision']/'snapshot.json'
    destination = CAMPAIGN.parent/'local-evidence/campaign002/qualification'/run
    executable = REPO/'venv/Scripts/python.exe'
    expected = [str(executable),'-X','utf8','-B',str(script),'--output',str(destination)]
    if (Path(paths['Frozen attempt manifest']).resolve()!=mp.resolve()
            or Path(paths['Frozen source snapshot']).resolve()!=sp.resolve()
            or job.get('argv')!=expected or job.get('cwd')!=str(REPO)
            or job.get('resolved_executable')!=str(executable)):
        raise ValueError('Failed boundary exact dispatch differs')
    fields={'run_id':run,'framework_revision':row['revision'],'stage':'diagnostic',
            'mode':'boundary-suite','qualification_stage':'no-model-isolation-control-continuity','model_turns_max':0}
    if any(type(manifest.get(k)) is not type(v) or manifest[k]!=v for k,v in fields.items()):
        raise ValueError('Failed boundary manifest scope differs')
    if (snapshot.get('revision')!=row['revision'] or snapshot.get('run_id')!=run
            or snapshot.get('manifest_sha256')!=manifest_hash
            or snapshot.get('schema')!='robot-codex-readiness-source-1'):
        raise ValueError('Failed boundary snapshot binding differs')
    name=script.relative_to(REPO).as_posix(); binding=(snapshot.get('sources') or {}).get(name)
    if (name not in manifest.get('runtime_input_files',[]) or not isinstance(binding,dict)
            or set(binding)!={'sha256','bytes'} or type(binding.get('bytes')) is not int or binding['bytes']<=0
            or re.fullmatch('[0-9a-f]{64}',str(binding.get('sha256'))) is None):
        raise ValueError('Failed boundary source identity unavailable')


'''
    changes=[]
    for filename in ['qualification_report.py','qualification_qa.py']:
        p=I/filename;raw=p.read_bytes();s=raw.decode('utf-8')
        backup=HERE/(filename+'.before');backup.write_bytes(raw)
        s=replace(s,'\ndef failed_single_interrupt_dispatch(',extra+'\ndef failed_single_interrupt_dispatch(')
        s=replace(s,"    manifest_path = root / 'manifest.json'\n",addition+"    manifest_path = root / 'manifest.json'\n")
        s=replace(s,"                '--host-evidence', str(evidence / 'host'), '--workspace', str(workspace)]\n",
            "                '--host-evidence', str(evidence / 'host'), '--workspace', str(workspace)]\n"
            "    if run == 'RCI001-C02-shutdown-diagnostic-005':\n"
            "        expected += ['--observer-config-sha256', '33948458d956c920ed1a24dd3f262f115b220dc0b3e113bf487ecb269ee1212c']\n")
        s=s.replace("'campaign002-failed-diagnostic-queue-1', SINGLE_INTERRUPT_SCHEMA)","'campaign002-failed-diagnostic-queue-1', SINGLE_INTERRUPT_SCHEMA, FAILED_BOUNDARY_SCHEMA)")
        if filename=='qualification_report.py':
            s=replace(s,"    if row.get('run_id') != 'RCI001-C02-shutdown-diagnostic-004':", "    if row.get('run_id') not in ('RCI001-C02-shutdown-diagnostic-004','RCI001-C02-shutdown-diagnostic-006'):")
            s=s.replace('Only the declared Native004 completion is supported','Only declared Native004/006 completions are supported')
            # This occurrence is unique in the failed branch, before the completed branch.
            anchor="    single = contract['schema'] == SINGLE_INTERRUPT_SCHEMA\n"
            s=replace(s,anchor,anchor+"    boundary = contract['schema'] == FAILED_BOUNDARY_SCHEMA\n")
            first=s.index('def failed_queue_row(');end=s.index('def completed_diagnostic_row(',first)
            part=s[first:end];part=replace(part,'    if not direct:\n','    if not direct and not boundary:\n')
            part=replace(part,'    if direct:\n        failed_diagnostic_dispatch(',
                "    if boundary:\n        failed_boundary_dispatch(row, job, {label: Path(item['path']) for label, item in indexed.items()}, manifest, snapshot, manifest_item['sha256'])\n    elif direct:\n        failed_diagnostic_dispatch(")
            s=s[:first]+part+s[end:]
            s=replace(s,'def failed_queue_row(',boundary+'def failed_queue_row(')
        else:
            s=replace(s,"    if row.get('run_id') != 'RCI001-C02-shutdown-diagnostic-004' or row.get('queue_failure') is not None:",
                "    if row.get('run_id') not in ('RCI001-C02-shutdown-diagnostic-004','RCI001-C02-shutdown-diagnostic-006') or row.get('queue_failure') is not None:")
            s=s.replace('Only the separate Native004 completion is supported','Only the separate Native004/006 completions are supported')
            anchor="    if failure['schema'] == SINGLE_INTERRUPT_SCHEMA:\n"
            s=replace(s,anchor,"    if failure['schema'] == FAILED_BOUNDARY_SCHEMA:\n        failed_boundary_dispatch(row, job, paths, manifest, snapshot, failure['manifest_sha256'])\n        return diagnostic_links_guard(failure.get('diagnostic_links', []), output, links, context='Failed queue')\n"+anchor)
            s=replace(s,'def failed_queue_guard(',boundary+'def failed_queue_guard(')
        p.write_text(s,encoding='utf-8',newline='\n')
        (HERE/(filename+'.diff')).write_text(''.join(difflib.unified_diff(raw.decode('utf-8').splitlines(True),s.splitlines(True),fromfile=filename+'.before',tofile=filename)),encoding='utf-8')
        changes.append({'path':str(p.resolve()),'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    with (HERE/'contract-extension.json').open('x',encoding='utf-8') as f:json.dump({'changes':changes,'scope':'Historical metadata display only; no qualification reassessment.'},f,indent=2)
    print(json.dumps({'extended':len(changes)}))

if __name__=='__main__':main()
