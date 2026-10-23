"""Check actual outputs of the non-actuating Robot-Codex smoke fixture."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def leaves(value):
    if isinstance(value, dict):
        return [leaf for child in value.values() for leaf in leaves(child)]
    if isinstance(value, list):
        return [leaf for child in value for leaf in leaves(child)]
    return [value]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(workspace, evidence):
    summary=json.loads((evidence/'summary.json').read_text(encoding='utf-8'))
    policy=json.loads((evidence/'launch_policy.json').read_text(encoding='utf-8'))
    note=workspace/'notes/bootstrap-observation.json'
    observed=json.loads(note.read_text(encoding='utf-8'))
    values=leaves(observed)
    required=['bootstrap-smoke-001','BOOTSTRAP-A-913','NO-ACTUATOR-BOOTSTRAP-173','BOOT-READ-4827']
    checks={'launcher_passed':summary.get('passed') is True,
            'effective_astra_max':summary.get('effective_model',{}).get('matches_pinned_model') is True,
            'exact_bootstrap':policy.get('bootstrap')=='Follow the instructions in RobotAgentPrompt.md.',
            'all_file_specific_markers_observed':all(any(marker in str(value) for value in values) for marker in required),
            'public_event_id_observed':any(str(value)=='11' for value in values),
            'generation_observed':any(str(value)=='1' for value in values),
            'continuity_updated':sha(workspace/'Continuity.md')!=policy['workspace_files']['Continuity.md'],
            'trusted_inputs_unchanged':all(sha(workspace/name)==digest for name,digest in policy['workspace_files'].items() if name!='Continuity.md')}
    transcript=(evidence/'exec/stderr.txt').read_text(encoding='utf-8',errors='replace')
    checks['bootstrap_in_actual_cli_transcript']='Follow the instructions in RobotAgentPrompt.md.' in transcript
    checks['tool_execution_present']='exec' in transcript and 'RobotAgentPrompt.md' in transcript
    return {'scope':'Filesystem/authentication stage A only. No robot attached; no continuity crash or physical qualification.',
            'passed':all(checks.values()),'checks':checks,'outputs':observed,
            'output_sha256':sha(note),'continuity_sha256':sha(workspace/'Continuity.md'),
            'effective_model_evidence':summary.get('effective_model'),
            'limitations':['File-specific outputs and recorded shell trace support actual bootstrap use; this is not an adversarial information-flow proof.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); report=verify(a.workspace,a.evidence)
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
