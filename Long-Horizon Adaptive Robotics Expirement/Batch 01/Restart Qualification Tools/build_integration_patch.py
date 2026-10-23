"""Generate a reviewable Runtime patch; NEVER apply it or edit Runtime.

Writes only beside this script. Source bases are hashed because physical source
is currently changing. A stale patch must be regenerated/reviewed, not forced.
"""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent.parent / 'Runtime'
PREFIX = 'Long-Horizon Adaptive Robotics Expirement/Runtime/'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('expected one unchanged integration anchor: ' + old[:100])
    return text.replace(old, new, 1)


def proposed_restart_state(source):
    source = replace_once(source, 'import re\n', 'import re\nfrom restart_physical_class import export_observation\nfrom restart_qualification import qualified_entry_identity\n')
    source = replace_once(source, '    result=_plain(snapshot,errors)\n',
        "    snapshot['physical_class_observation']=export_observation(\n"
        "        model,cell.xml,cell.registry,getattr(cell,'restart_physical_seal',None),\n"
        "        physical_configuration_sha256=snapshot['physical_configuration_sha256'])\n"
        "    result=_plain(snapshot,errors)\n")
    source = replace_once(source, 'def _calibration(entry,snapshot):', 'def _calibration(entry,snapshot,*,qualification=None):')
    source = replace_once(source,
        "    if entry.get('physical_configuration_sha256')!=snapshot.get('physical_configuration_sha256'):\n",
        "    if entry.get('envelope_basis')!='measured_before_this_intervention':return 'unknown','envelope must predate the intervention'\n"
        "    mode=entry.get('match_mode','exact_configuration')\n"
        "    if mode=='qualified_class':\n"
        "        assessment=qualified_entry_identity(entry,snapshot,qualification)\n"
        "        return assessment['state'],assessment['reason']\n"
        "    if mode!='exact_configuration':return 'unknown','unsupported physical matching mode'\n"
        "    if entry.get('physical_configuration_sha256')!=snapshot.get('physical_configuration_sha256'):\n")
    source = replace_once(source, 'def _grip(entry,snapshot,obj,policy):\n    state,reason=_calibration(entry,snapshot)',
        'def _grip(entry,snapshot,obj,policy,*,qualification=None):\n    state,reason=_calibration(entry,snapshot,qualification=qualification)')
    source = replace_once(source, 'def _route(entries,snapshot,obj,available):', 'def _route(entries,snapshot,obj,available,*,qualification=None,grip_entry=None):')
    source = replace_once(source, '    for entry in entries:\n        state,reason=_calibration(entry,snapshot)',
        "    for entry in entries:\n"
        "        if isinstance(entry,dict) and entry.get('match_mode')=='qualified_class' and (\n"
        "                not isinstance(grip_entry,dict) or grip_entry.get('match_mode')!='qualified_class'\n"
        "                or entry.get('qualification_cell_id')!=grip_entry.get('qualification_cell_id')):\n"
        "            reports.append({'state':'unknown','reason':'grip and route must use the same measured transfer cell'});continue\n"
        "        state,reason=_calibration(entry,snapshot,qualification=qualification)")
    source = replace_once(source, 'def classify_restart(snapshot,*,calibration=None,policy=None):',
        'def classify_restart(snapshot,*,calibration=None,policy=None,qualification_context=None):')
    source = replace_once(source, "_grip(calibration.get('grip'),snapshot,obj,rules)",
        "_grip(calibration.get('grip'),snapshot,obj,rules,qualification=qualification_context)")
    source = replace_once(source, "_route(calibration.get('routes'),snapshot,obj,available)",
        "_route(calibration.get('routes'),snapshot,obj,available,qualification=qualification_context,grip_entry=calibration.get('grip'))")
    source = replace_once(source, "    try:calibration_hash=digest(calibration)\n",
        "    transfer_entries=[calibration.get('grip')]+(calibration.get('routes') if isinstance(calibration.get('routes'),list) else [])\n"
        "    transfer_reports=[qualified_entry_identity(entry,snapshot,qualification_context) for entry in transfer_entries\n"
        "                      if isinstance(entry,dict) and entry.get('match_mode')=='qualified_class']\n"
        "    try:calibration_hash=digest(calibration)\n")
    source = replace_once(source, "            'calibration_input_sha256':calibration_hash,'infrastructure':infrastructure,\n",
        "            'calibration_input_sha256':calibration_hash,'infrastructure':infrastructure,\n"
        "            'qualified_class_evidence':transfer_reports,\n")
    return source


def proposed_cell(source):
    source = replace_once(source, 'from evaluator import IndependentEvaluator\n',
        'from evaluator import IndependentEvaluator\nfrom restart_physical_class import source_binding,seal_model\n')
    source = replace_once(source, '        self.model=mujoco.MjModel.from_xml_string(self.xml)\n',
        '        self.model=mujoco.MjModel.from_xml_string(self.xml)\n'
        '        # Protected compile-site attestation. Missing evidence cannot admit\n'
        '        # class transfer, but does not manufacture a physics task failure.\n'
        '        self.restart_physical_seal=None;self.restart_physical_export_error=None\n'
        '        try:\n'
        '            self.restart_physical_seal=seal_model(self.model,self.xml,self.registry,source_binding(HERE,mujoco))\n'
        '        except (ValueError,TypeError,KeyError,AttributeError,OSError) as error:\n'
        '            self.restart_physical_export_error=str(error)\n')
    return source


def main():
    generated = {
        'restart_compatibility.py': (HERE / 'compatibility.py').read_text(encoding='utf-8'),
        'restart_physical_class.py': (HERE / 'descriptor.py').read_text(encoding='utf-8').replace('from compatibility import', 'from restart_compatibility import'),
        'restart_qualification.py': (HERE / 'qualification.py').read_text(encoding='utf-8').replace('from compatibility import', 'from restart_compatibility import').replace('from descriptor import', 'from restart_physical_class import')}
    original = {name: (RUNTIME / name).read_text(encoding='utf-8') for name in ('cell.py', 'restart_state.py')}
    generated['cell.py'] = proposed_cell(original['cell.py'])
    generated['restart_state.py'] = proposed_restart_state(original['restart_state.py'])
    chunks = []
    for name, new in generated.items():
        before = original.get(name, '')
        chunks.append('diff --git ' + json.dumps('a/' + PREFIX + name) + ' ' + json.dumps('b/' + PREFIX + name) + '\n')
        if name not in original:
            chunks.append('new file mode 100644\n')
        chunks.extend(difflib.unified_diff(before.splitlines(keepends=True), new.splitlines(keepends=True),
                         fromfile='a/' + PREFIX + name if name in original else '/dev/null', tofile='b/' + PREFIX + name))
        compile(new, name, 'exec')
    (HERE / 'runtime-integration.patch').write_text(''.join(chunks), encoding='utf-8', newline='\n')
    manifest = {'status': 'proposed_unapplied_unmeasured', 'runtime_source_bases_sha256': {
        name: hashlib.sha256((RUNTIME / name).read_bytes()).hexdigest() for name in original},
        'helpers_sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in
                          ('descriptor.py', 'qualification.py', 'compatibility.py', 'build_integration_patch.py')},
        'patch_sha256': hashlib.sha256((HERE / 'runtime-integration.patch').read_bytes()).hexdigest(),
        'qualification_artifact': None, 'readiness_changed': False, 'evaluation_seeds_drawn': False,
        'runtime_files_modified': False, 'physical_measurement': False}
    (HERE / 'integration-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__': main()
