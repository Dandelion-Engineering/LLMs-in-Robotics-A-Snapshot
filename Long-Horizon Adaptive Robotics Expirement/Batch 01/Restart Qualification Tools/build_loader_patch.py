"""Generate a separate, reviewable loader/absence patch; never edit Runtime."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent.parent / 'Runtime'
PREFIX = 'Long-Horizon Adaptive Robotics Expirement/Runtime/'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('expected one unchanged integration anchor: ' + old[:120])
    return text.replace(old, new, 1)


def proposed_protocol(source):
    return replace_once(source, '    return freeze, readiness\n',
        '    # Explicit class mode must have prior byte-verified evidence before seed creation.\n'
        '    from restart_calibration_loader import CalibrationInputError, load_restart_qualification\n'
        '    try:load_restart_qualification(freeze, freeze_path)\n'
        '    except CalibrationInputError as exc:raise ProtocolError(str(exc)) from exc\n'
        '    return freeze, readiness\n')


def proposed_release(source):
    source = replace_once(source, '    artifacts=verify_artifacts(freeze,freeze_path)\n',
        '    artifacts=verify_artifacts(freeze,freeze_path)\n'
        '    from restart_calibration_loader import CalibrationInputError,load_restart_qualification\n'
        '    try:restart_qualification=load_restart_qualification(freeze,freeze_path)\n'
        '    except CalibrationInputError as exc:raise ReleaseError(str(exc)) from exc\n'
        "    artifacts['restart_qualification']=restart_qualification.as_dict() if restart_qualification is not None else None\n")
    source = replace_once(source, '    @property\n    def manifest(self):return json.loads(self.manifest_json)\n',
        '    @property\n    def manifest(self):return json.loads(self.manifest_json)\n'
        '    @property\n    def restart_qualification(self):\n'
        "        if self._authority is not _AUTHORITY:raise ReleaseError('Evaluation context was not issued by the gated authorizer')\n"
        "        return json.loads(self.artifacts_json).get('restart_qualification')\n")
    return source


def proposed_experiment(source):
    source = replace_once(source, 'from restart_state import capture_restart_state,classify_restart\n',
        'from restart_state import capture_restart_state,classify_restart\n'
        'from restart_calibration_loader import (VerifiedRestartQualification,CalibrationInputError,\n'
        '    select_restart_calibration,absence_observation,first_control_endpoint)\n')
    source = replace_once(source, 'policy_seed=None,evaluation_context=None):\n',
        'policy_seed=None,evaluation_context=None,development_restart_qualification=None):\n')
    source = replace_once(source, '    evidence=Evidence(evidence_path,run_id)\n',
        "    if stage=='evaluation':\n"
        "        if development_restart_qualification is not None:raise CalibrationInputError('Development qualification cannot override evaluation authority')\n"
        '        restart_qualification=evaluation_context.restart_qualification\n'
        '    elif development_restart_qualification is None:restart_qualification=None\n'
        '    elif isinstance(development_restart_qualification,VerifiedRestartQualification):\n'
        '        restart_qualification=development_restart_qualification.as_dict()\n'
        "    else:raise CalibrationInputError('Development qualification must come from the protected loader')\n"
        '    evidence=Evidence(evidence_path,run_id)\n')
    source = replace_once(source,
        '    # No protected, source-matched calibration authorization input currently exists.\n'
        '    # Never infer prior calibration from this episode or a later successful outcome.\n'
        '    restart_calibration=None\n',
        '    # The protected frozen map is assessed only at the actual existing cut.\n'
        '    restart_calibration=None;restart_selection=None;restart_revocation=None\n'
        '    restart_absence_endpoint_observed=False;restart_first_control_observed=False\n'
        "    qualification_context=restart_qualification['qualification_context'] if restart_qualification else None\n"
        "    restart_absence_settings=restart_qualification['absence'] if restart_qualification else None\n")
    source = replace_once(source, '    def sim_now():return float(cell.data.time) if cell is not None else 0.\n',
        '    def sim_now():return float(cell.data.time) if cell is not None else 0.\n'
        '    def record_restart_absence(endpoint,landmark,parents=None,control=None):\n'
        '        report=absence_observation(restart_revocation,landmark,endpoint,restart_absence_settings)\n'
        "        report['restart_event_id']=restart_parent\n"
        "        report['qualification_identity']=restart_qualification['identity'] if restart_qualification else None\n"
        "        if control is not None:report['control_admission']=control\n"
        "        event=evidence.emit('restart_absence',report,landmark['sim_s'],'evaluator',parents or [restart_parent])\n"
        "        if restart_exposure is not None:restart_exposure.setdefault('absence_observations',[]).append({**report,'event_id':event})\n"
        '        return report\n')
    source = replace_once(source, "        manifest['restart_opportunity']=restart_tracker.configuration()\n",
        "        manifest['restart_opportunity']=restart_tracker.configuration()\n"
        "        manifest['restart_qualification_identity']=restart_qualification['identity'] if restart_qualification else None\n")
    source = replace_once(source, "                phase='restart_evidence'\n",
        "                phase='restart_evidence'\n"
        "                capture_started={'wall_s':time.perf_counter(),'sim_s':sim_now()}\n")
    source = replace_once(source, '                admissibility=classify_restart(rich,calibration=restart_calibration)\n',
        "                capture_finished={'wall_s':time.perf_counter(),'sim_s':sim_now()}\n"
        '                restart_selection=select_restart_calibration(restart_qualification,rich)\n'
        "                restart_calibration=restart_selection['calibration']\n"
        '                admissibility=classify_restart(rich,calibration=restart_calibration,qualification_context=qualification_context)\n'
        "                classification_finished={'wall_s':time.perf_counter(),'sim_s':sim_now()}\n")
    source = replace_once(source,
        "                    'protected_snapshot':rich['geometry'],'restart_calibration':restart_calibration},sim,'evaluator')\n",
        "                    'protected_snapshot':rich['geometry'],'restart_calibration':restart_calibration,\n"
        "                    'restart_qualification_identity':restart_qualification['identity'] if restart_qualification else None,\n"
        "                    'restart_qualification_selection':{k:v for k,v in restart_selection.items() if k!='calibration'},\n"
        "                    'capture_landmarks':{'start':capture_started,'finish':capture_finished,'classification_finish':classification_finished}},sim,'evaluator')\n")
    source = replace_once(source, "                cell.cancel('runtime incarnation revoked')\n",
        "                restart_revocation={'wall_s':time.perf_counter(),'sim_s':sim_now()}\n"
        "                cell.cancel('runtime incarnation revoked')\n"
        "                revoked={'before_cancel':restart_revocation,'after_cancel':{'wall_s':time.perf_counter(),'sim_s':sim_now()}}\n"
        "                restart_exposure['authority_revocation']=revoked\n"
        "                evidence.emit('restart_authority_revoked',revoked,sim_now(),'evaluator',[restart_parent])\n")
    source = replace_once(source,
        "                    ready_event=evidence.emit('restart_ready',{'incarnation':incarnation,'reply':ready},sim,parents=[restart_parent] if restart_parent else [])\n",
        "                    ready_landmark={'wall_s':time.perf_counter(),'sim_s':sim_now()}\n"
        "                    absence=record_restart_absence('restart_ready',ready_landmark)\n"
        "                    restart_absence_endpoint_observed=not restart_absence_settings or restart_absence_settings['absence_endpoint']=='restart_ready'\n"
        "                    ready_event=evidence.emit('restart_ready',{'incarnation':incarnation,'reply':ready,'absence':absence},ready_landmark['sim_s'],parents=[restart_parent] if restart_parent else [])\n")
    source = replace_once(source, "                        admission_event=evidence.emit('action_admission',feedback,sim,'gateway',[request_event])\n",
        "                        admission_event=evidence.emit('action_admission',feedback,sim,'gateway',[request_event])\n"
        '                        if restart_revocation is not None and not restart_pending and not restart_first_control_observed:\n'
        '                            control=first_control_endpoint(action,feedback,incarnation=incarnation,\n'
        "                                expected_destination=restart_qualification['destination'] if restart_qualification else None)\n"
        '                            if control is not None:\n'
        '                                restart_first_control_observed=True\n'
        "                                record_restart_absence(control['endpoint'],{'wall_s':time.perf_counter(),'sim_s':sim_now()},\n"
        '                                    [restart_parent,admission_event],control=control)\n'
        '                                # The first other control ends this opportunity, even when its scope is unsupported.\n'
        '                                restart_absence_endpoint_observed=True\n')
    source = replace_once(source, '        sim_at_end=sim_now()\n',
        '        sim_at_end=sim_now()\n'
        '        if restart_revocation is not None and not restart_absence_endpoint_observed:\n'
        "            try:record_restart_absence('episode_end_unobserved',{'wall_s':episode_end_wall,'sim_s':sim_at_end})\n"
        "            except Exception as exc:cleanup_errors.append('censored absence evidence: '+str(exc))\n")
    return source


def proposed_files():
    original = {name:(RUNTIME/name).read_text(encoding='utf-8') for name in ('protocol.py','release_runner.py','experiment.py')}
    generated = {'restart_calibration_loader.py':(HERE/'calibration_loader.py').read_text(encoding='utf-8')
        .replace('from compatibility import','from restart_compatibility import').replace('from qualification import','from restart_qualification import'),
        'protocol.py':proposed_protocol(original['protocol.py']),
        'release_runner.py':proposed_release(original['release_runner.py']),
        'experiment.py':proposed_experiment(original['experiment.py'])}
    return original, generated


def main():
    original, generated = proposed_files(); chunks=[]
    for name,new in generated.items():
        before=original.get(name,'');compile(new,name,'exec')
        chunks.append('diff --git '+json.dumps('a/'+PREFIX+name)+' '+json.dumps('b/'+PREFIX+name)+'\n')
        if name not in original:chunks.append('new file mode 100644\n')
        chunks.extend(difflib.unified_diff(before.splitlines(keepends=True),new.splitlines(keepends=True),
            fromfile='a/'+PREFIX+name if name in original else '/dev/null',tofile='b/'+PREFIX+name))
    patch=HERE/'runtime-loader-integration.patch';patch.write_text(''.join(chunks),encoding='utf-8',newline='\n')
    manifest={'status':'proposed_unapplied_unmeasured','runtime_source_bases_sha256':{
        name:hashlib.sha256((RUNTIME/name).read_bytes()).hexdigest() for name in original},
        'helpers_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('calibration_loader.py','build_loader_patch.py')},
        'generated_utf8_sha256':{name:hashlib.sha256(value.encode()).hexdigest() for name,value in generated.items()},
        'patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),
        'runtime_files_modified':False,'physical_measurement':False,'qualification_artifact':None,
        'readiness_changed':False,'evaluation_seeds_drawn':False}
    (HERE/'loader-integration-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':main()
