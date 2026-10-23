"""Add the new declared sources across prospective qualification and admission."""
import difflib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]

def unique(text, old, new):
    if text.count(old) != 1: raise ValueError('Expected unique source seam: '+old)
    return text.replace(old, new)

def main():
    path = C/'qualification/prepare_model_v22.py'
    if path.exists(): raise ValueError('Existing lineage preparation footprint')
    text = (C/'qualification/prepare_model_v21.py').read_text(encoding='utf-8')
    text = text.replace('model_inventory_v20', 'model_inventory_v21').replace("HERE/'prepare_model_v20.py'", "HERE/'prepare_model_v21.py'")
    start = text.index('PRE_EXIT_INPUTS=('); end = text.index('\n\ndef pre_exit_inputs', start)
    text = text[:start]+'''PROCESS_DRAIN_INPUTS=(
    'qualification/prepare_model_v22.py','qualification/test_prepare_model_v22.py',
    'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md',
    'harness/process_drain.py','harness/native_process_quiescence.py','harness/test_native_process_quiescence.py',
    'assessment/process_integrity.py','assessment/test_process_integrity.py',
)
'''+text[end:]
    text = text.replace('pre_exit_inputs', 'process_drain_inputs').replace('PRE_EXIT_INPUTS', 'PROCESS_DRAIN_INPUTS')
    text = text.replace('prior.pilot_retirement_inputs()', 'prior.pre_exit_inputs()')
    text = text.replace('pre-exit lifecycle', 'graceful process-drain')
    with path.open('x', encoding='utf-8', newline='\n') as stream: stream.write(text)
    text = (C/'qualification/test_prepare_model_v21.py').read_text(encoding='utf-8')
    text = text.replace('import prepare_model_v21 as subject', 'import prepare_model_v22 as subject')
    text = text.replace('pre_exit_inputs', 'process_drain_inputs').replace('PRE_EXIT_INPUTS', 'PROCESS_DRAIN_INPUTS')
    with (C/'qualification/test_prepare_model_v22.py').open('x', encoding='utf-8', newline='\n') as stream: stream.write(text)
    edits = {}
    for name in ('qualification/prepare_native.py', 'qualification/host_probe.py',
                 'qualification/boundary_suite_v3.py', 'harness/raw_event_preflight_v2.py'):
        edits[name] = [('prepare_model_v21.py', 'prepare_model_v22.py'),
                       ('extra.pre_exit_inputs()', 'extra.process_drain_inputs()')]
    edits['harness/test_native_owner_bootstrap.py'] = [(
        "        pre_exit = b'                args.native_exit_barrier=self.native_exit_barrier\\n'",
        "        process_selection = b'                args.native_process_drain=True\\n'\n"
        "        self.assertEqual(candidate.count(process_selection), 1)\n"
        "        candidate = candidate.replace(process_selection, b'')\n"
        "        pre_exit = b'                args.native_exit_barrier=self.native_exit_barrier\\n'")]
    edits['harness/test_native_shutdown_order.py'] = [(
        "            bridge = (HERE/'codehost_bridge_v3.py').read_text(encoding='utf-8')\n",
        "            bridge = (HERE/'codehost_bridge_v3.py').read_text(encoding='utf-8')\n"
        "            process_dispatch = (\"        if isinstance(request, dict) and request.get('schema') == 'campaign002-process-drain-request-1':\\n\"\n"
        "                                \"            import process_drain\\n\"\n"
        "                                \"            return process_drain.bridge_join(self, request)\\n\")\n"
        "            self.assertEqual(bridge.count(process_dispatch), 1)\n"
        "            bridge = bridge.replace(process_dispatch, '')\n")]
    fields = [('native_process_drain_method', 'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md'),
              ('native_process_drain_assessor', 'assessment/process_integrity.py'),
              ('native_process_drain_diagnostic_proof', 'io-repair/graceful-process-assessment-001/transport-proof.json'),
              ('native_process_drain_diagnostic_result', 'io-repair/graceful-process-assessment-001/terminal-result.json')]
    marker = "        'native_pre_exit_drain_assessor': CAMPAIGN / 'assessment/pre_exit_integrity.py',\n"
    edits['admission/prepare_certificate.py'] = [(marker, marker+''.join(
        '        '+repr(key)+': CAMPAIGN / '+repr(name)+',\n' for key,name in fields))]
    marker = "            ('native_pre_exit_drain_assessor','assessment/pre_exit_integrity.py'),\n"
    edits['admission/test_prepare_admission.py'] = [(marker, marker+''.join(
        '            ('+repr(key)+','+repr(name)+'),\n' for key,name in fields)),
        ("        for relative in ('io-repair/PILOT_RETIREMENT_INVENTORY_V1.md',",
         "        for relative in ('io-repair/GRACEFUL_PROCESS_DRAIN_V1.md',\n"
         "                         'assessment/process_integrity.py',\n"
         "                         'io-repair/graceful-process-assessment-001/transport-proof.json',\n"
         "                         'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md',")]
    (HERE/'lineage-original').mkdir(exist_ok=False)
    differences = []
    for name, changes in edits.items():
        path = C/name; original = path.read_text(encoding='utf-8'); text = original
        for old,new in changes: text = unique(text, old, new)
        (HERE/'lineage-original'/path.name).write_bytes(path.read_bytes())
        differences.extend(difflib.unified_diff(original.splitlines(True), text.splitlines(True), fromfile='before/'+name, tofile='after/'+name))
        path.write_text(text, encoding='utf-8', newline='\n')
    with (HERE/'lineage.diff').open('x', encoding='utf-8') as stream: stream.write(''.join(differences))
    print(json.dumps({'added': 2, 'changed': len(edits), 'policy_fields_changed': False}))

if __name__ == '__main__': main()
