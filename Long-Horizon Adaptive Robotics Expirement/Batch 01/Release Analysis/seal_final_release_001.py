"""Materialize root's final selection and evidence decisions; create no seeds or runs."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
EXP = BATCH.parent
RUNTIME = EXP / 'Runtime'
sys.path.insert(0, str(RUNTIME))
import release_runner as runner
import protocol

RELEASE = 'batch01-eval-r1'
PREP = EXP / 'Evidence/prepared-artifacts/batch01-eval-r1-final'
SNAPSHOT = BATCH / 'selection-evidence-final-001'
RECEIPTS = EXP / 'Evidence/queue-receipts'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ref(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Missing final reference: ' + str(path))
    return {'path': str(path), 'sha256': digest(path)}


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def receipt(identity):
    path = RECEIPTS / (identity + '.json')
    value = load(path)
    if value['id'] != identity or value['state'] != 'succeeded' or type(value['exit_status']) is not int or value['exit_status'] != 0:
        raise ValueError('Successful official receipt required: ' + identity)
    return ref(path)


def main():
    job = runner.queued_job(Path(__file__))
    selected_path = BATCH / 'development-selection-decision-001.json'
    controls_path = BATCH / ('release-control-index-' + RELEASE + '.json')
    freeze_path = BATCH / ('freeze-' + RELEASE + '.json')
    ready_path = BATCH / ('readiness-' + RELEASE + '.json')
    closed_ledger = BATCH / 'development-ledger-closed-001.md'
    if any(p.exists() for p in (selected_path, controls_path, freeze_path, ready_path, closed_ledger)):
        raise ValueError('Final output exists; do not overwrite a prior sealing attempt')
    prepared = load(PREP / 'prepared-artifacts.json')
    prepared_receipt = receipt('20260923T130110458073Z-8dc16ef5')
    if prepared['queue_job_id'] != '20260923T130110458073Z-8dc16ef5':
        raise ValueError('Unexpected artifact-preparation job')
    runner.verify_artifacts(prepared, PREP / 'not-a-freeze.json')
    accounting = load(SNAPSHOT / 'accounting.json')
    if accounting['counts']['terminal_attempts'] != 29 or accounting['counts']['result_records'] != 30:
        raise ValueError('Final development accounting differs')
    for item in accounting['canonical_files']:
        if digest(item['source_path']) != item['sha256'] or digest(item['snapshot_path']) != item['sha256']:
            raise ValueError('Development store changed before selection')
    code = load(PREP / 'code.json')
    current = {Path(r['path']).name: r['sha256'] for r in code['files'] if Path(r['path']).parent == RUNTIME}
    if current != {p.name: digest(p) for p in RUNTIME.glob('*.py')}:
        raise ValueError('Prepared Runtime identity differs')
    narrative = load(EXP / 'Engineering Investigation/current-implementation-narrative.json')
    if any(current[r['member']] != r['sha256'] for r in narrative['source_refs']):
        raise ValueError('Implementation narrative does not match selected source')
    final_retention = EXP / 'Evidence/derived/retention-development-final-001/summary.json'
    retention = load(final_retention)
    retention_receipt = receipt('20260923T125735157737Z-1b84f895')
    if len(retention['runs']) != 29 or retention['registered_without_completed_result'] or not retention['current_headroom_satisfies_planning_estimate']:
        raise ValueError('Incomplete or insufficient retention evidence')
    if shutil.disk_usage(EXP).free < retention['full_release_planning_requirement_bytes']:
        raise ValueError('Current capacity no longer covers the complete release')
    pair = load(EXP / 'Evidence/derived/development-A3-profile-001/index.json')
    if pair['counts'] != {'completed': 2, 'failed_or_partial': 0, 'selected': 2, 'with_integrity_findings': 0}:
        raise ValueError('Pair derivation is not complete and clean')
    development_freeze = load(EXP / 'Evidence/derived/recovery-profile-qualification-001/development-freeze.json')
    qualification = development_freeze['restart_qualification']
    if (qualification['payload_template_to_cell'] != {'part:A': 'profile-A1-root-001'}
            or qualification['prospective_absence_bound_s'] != 5.0
            or qualification['absence_timebase'] != 'wall'
            or qualification['absence_endpoint'] != 'recover_held_admitted'):
        raise ValueError('Selected qualification is not the accepted A-only rule')
    support_receipts = [receipt(j) for j in (
        '20260923T121322613458Z-dd45dfa8', '20260923T115431720868Z-38d34027',
        '20260923T124804450282Z-77877d08', '20260923T125616352142Z-b537850e',
        '20260923T125651721797Z-a3c8c319', '20260923T124647079277Z-8b1658f1',
        '20260923T121521761878Z-5a73938e', '20260923T121917353957Z-9c6d09f6')]
    now = datetime.now(timezone.utc).isoformat()
    selected = []
    support = {'C0': ['B01-dev-C0-013', 'B01-dev-C0-012', 'B01-dev-C0-011'],
               'A1': ['B01-dev-A1-005', 'B01-dev-A1-006'],
               'A2': ['B01-dev-A2-003', 'B01-dev-A2-004'],
               'A3': ['B01-dev-A3-005', 'B01-dev-A3-006']}
    latest = {'C0': 'B01-dev-C0-013', 'A1': 'B01-dev-A1-006', 'A2': 'B01-dev-A2-004', 'A3': 'B01-dev-A3-006'}
    for entrant, run_id in latest.items():
        row = next(a for a in accounting['attempts'] if a['run_id'] == run_id)
        expected_changes = [] if entrant in ('C0', 'A3') else ['initial_conditions.py', 'release_runner.py', 'test_initial_conditions.py']
        changed = sorted(k for k in current if row['historical_runtime_file_sha256'].get(k) != current[k])
        if changed != expected_changes:
            raise ValueError('Unexpected source changes since development: ' + entrant)
        selected.append({'architecture_id': 'B01-' + entrant, 'kind': 'baseline' if entrant == 'C0' else entrant,
                         'supporting_attempt_ids': support[entrant], 'latest_development_revision_id': row['revision_id'],
                         'historical_source_zip': row['source_zip'], 'historical_manifest': row['manifest'],
                         'final_code_index': prepared['artifacts']['code'], 'final_environment_index': prepared['artifacts']['environment'],
                         'final_model_index': None if entrant == 'C0' else prepared['artifacts']['model'],
                         'source_changes_after_latest_attempt': changed,
                         'change_disposition': 'C0/A3 latest snapshot matches every final Runtime Python byte. A1/A2 retain identical policy, prompt, model, planner, sensors and evaluator; later common changes are the fixed public 0.10 simulation-second after-release dwell, release registration retention and the dwell tests. Runtime436 plus10 focused tests, actual C0-013 and qualified A3 pair support these common changes. Earlier episodes are not relabeled as running final bytes.',
                         'selection_reason': 'Latest supported implemented mechanism; all entrants retained, including weak and failed outcomes. Earlier checkpoints are historical development, not selected by score.',
                         'mechanism': narrative['candidates']['B01-' + entrant]['mechanism'],
                         'limitations': ['Development validity remains as canonically recorded; no scored inference', 'Current-source support combines exact identity, targeted common-change tests and actual development; not every future scene was tested', 'Equal opportunity is not equal realized effort or maturity']})
    decision = {'schema_version': 'batch01-development-selection-decision-1', 'recorded_at_utc': now,
                'operator': 'Codex session4 root', 'release_id': RELEASE, 'decision': 'Close the symmetric development extension and select all four current mechanisms for the unchanged full evaluation',
                'initial_opportunity': {'entrants': ['C0', 'A1', 'A2', 'A3'], 'working_sessions': 2, 'active_engineering_hour_ceiling': 12, 'episode_ceiling_per_entrant': 60},
                'historical_effort': {'active_engineering_hours': None, 'measurement_state': 'unmeasured', 'initial_time_ceiling_compliance': 'unknown', 'later_extension_active_hours': None, 'later_measurement_state': 'unmeasured', 'reason': 'No complete active start/stop instrumentation; wall time, parallelism, tokens and policy run duration are not engineering-hours substitutes'},
                'episode_accounting': {'counts': accounting['counts'], 'entrants': accounting['entrants'], 'exact_attempts_corrections_and_source_bindings': ref(SNAPSHOT / 'accounting.json'), 'common_primitive_and_model_probes_are_not_architecture_episodes': True},
                'symmetric_extension': {'adoption': ref(BATCH / 'development-opportunity-extension-001.json'), 'disposition': 'Named development003 and necessary common physical/recovery/reader/registration prerequisites complete. Remaining episode opportunities unused; no further entrant-score tuning.'},
                'selection_rule': load(BATCH / 'development-opportunity-extension-001.json')['selection_rule'],
                'selected_checkpoints': selected, 'prompt_and_development_knowledge': accounting['current_runtime_provenance']['prompt_and_development_knowledge'],
                'actual_model_configuration': load(PREP / 'model.json')['config'],
                'final_restart_qualification': qualification,
                'qualification_data_change': 'C0-013 and latest A1/A2 development used the earlier P1 qualification data. The final common protected classifier uses the new accepted A-only profile, exercised by A3-005/006. This changes calibration support, not candidate policy, public observations or the recovery controller. Original cuts/results remain classified under their original inputs. States outside the new cell are unsupported; no old B or other-profile cell is silently merged.',
                'evidence_refs': [ref(SNAPSHOT / 'accounting.json'), ref(SNAPSHOT / 'snapshot-files.json'), ref(PREP / 'prepared-artifacts.json'), prepared_receipt, *support_receipts],
                'limitations': ['Original active-time budget compliance unknown; this later symmetric extension cannot repair historical missing effort records', 'All development failures and original qualification exclusions remain intact', 'C0 nominal competence and the A-only local carry qualification do not guarantee arbitrary recovery states', 'No concealed seeds or scored outcomes used for selection; source and configuration are common to all matched entrants']}
    # Root decisions are complete before any final freeze or concealed-seed creation.
    write(selected_path, decision)
    ledger = BATCH / 'Development Ledger.md'
    old = ledger.read_bytes()
    heading = '## Final development selection — ' + now
    if heading.encode('utf-8') in old:
        raise ValueError('Duplicate final ledger entry')
    addition = ('\n\n' + heading + '\n\nRoot closed the symmetric extension and selected all four latest supported mechanisms under [development-selection-decision-001.json](development-selection-decision-001.json). The closed accounting retains 29 terminal attempts and 30 result records, including the C0-002 correction: C0=13, A1=6, A2=4, A3=6. All remain below60; remaining opportunity is unused. Historical and later active engineering hours remain unmeasured, and original12-hour compliance remains unknown. No winner or success-only filter was used.\n\nFinal source identity is the successful prepared batch01-eval-r1-final bundle. C0-013/A3-006 match all56 Runtime files. A1/A2 policy/model/prompt/physics/sensing/evaluator bytes are unchanged; their three later common files and supporting tests/probes are explicitly dispositioned in the decision. The original failures, cut classifications and source identities remain intact. This closes development; scored evidence will be registered separately.\n')
    ledger.write_bytes(old + addition.encode('utf-8'))
    if not ledger.read_bytes().startswith(old) or ledger.read_text(encoding='utf-8').count(heading) != 1:
        raise ValueError('Append-only ledger integrity failed')
    with closed_ledger.open('xb') as stream:
        stream.write(ledger.read_bytes())
    paths = {}
    def add(path, purpose):
        path = Path(path).resolve()
        if path == ledger.resolve():
            path = closed_ledger.resolve()
        if path.parent == (EXP / 'Architecture Map').resolve() and path.suffix == '.jsonl':
            raise ValueError('Mutable live map registry cannot be frozen')
        paths.setdefault(str(path), {'purposes': []})['purposes'].append(purpose)
    draft = load(HERE / 'final-readiness-draft.json')
    candidates = load(HERE / 'final-gate-evidence-candidates.json')
    for name, item in {**draft['source_pointers'], **candidates['candidate_refs']}.items():
        if name in ('old_readiness', 'checkpoint', 'selection_runbook', 'control_index_plan'):
            continue
        add(item['path'], name + ': retained source/evidence; historical items retain their dated scope')
    for path in SNAPSHOT.rglob('*'):
        if path.is_file():
            add(path, 'closed development accounting/source snapshot')
    for path in (EXP / 'Engineering Investigation').glob('*'):
        if path.is_file() and path.suffix in ('.py', '.js', '.css'):
            add(path, 'frozen Investigation implementation and verification sources')
    for path in (EXP / 'Engineering Investigation').glob('*.md'):
        add(path, 'frozen Investigation interface documentation')
    for relative in ('workspace.html', 'current-implementation-narrative.json'):
        add(EXP / 'Engineering Investigation' / relative, 'source-matched presentation')
    for path in HERE.glob('*'):
        if path.is_file() and path.suffix in ('.py', '.ps1'):
            add(path, 'frozen external collection/analysis/execution helper')
    for relative in ('RELEASE-SERIES.md', 'release-series-synthetic-validation-001.json'):
        add(HERE / relative, 'completed coordinator evidence')
    for path in (EXP / 'Evidence/derived/recovery-profile-qualification-001').glob('*.json'):
        add(path, 'actual accepted A-only qualification; protected loader separately verifies full artifact closure')
    for path in (EXP / 'Evidence/derived/retention-development-final-001').glob('*.json'):
        add(path, 'complete registered development retention accounting')
    extra = [selected_path, closed_ledger, BATCH / 'retention-capacity-decision-001.json',
             BATCH / 'Recovery Profile Results.md', BATCH / 'Recovery Profile Assembly Tools/acceptance-profile-001.json',
             EXP / 'Evidence/derived/recovery-profile-provisional-001/provisional-rule.json',
             Path('D:/CodexEvidence/LLMs-in-Robotics/recovery-profile-assessment-001/assessment.json'),
             EXP / 'Evidence/derived/development-A3-profile-001/index.json', EXP / 'Evidence/derived/development-C0-013-001/index.json',
             BATCH / 'After Release Milestone Patch/physical-validation-001.json', PREP / 'prepared-artifacts.json',
             *[Path(r['path']) for r in prepared['artifacts'].values()], Path(prepared_receipt['path']), Path(retention_receipt['path']),
             *[Path(r['path']) for r in support_receipts]]
    for path in extra:
        add(path, 'final decision/current evidence')
    artifacts = [{'id': 'file-' + hashlib.sha256(path.encode()).hexdigest()[:16], **ref(path), 'purposes': item['purposes']} for path, item in sorted(paths.items())]
    controls = {'schema_version': 'batch01-release-control-index-1', 'release_id': RELEASE, 'recorded_at_utc': now,
                'scope': 'Root-selected final controls and direct evidence; preserves historical failures without promoting historical scope',
                'settings': {'attempts': 264, 'main': 192, 'controls': 72, 'maximum_retries': 0, 'bootstrap_draws': 2000, 'public_analysis_seed': 0, 'scenario_families': 20, 'replicates': 2, 'full_task_cap_seconds': 156600, 'fixed_trace_slots': 12},
                'artifact_files': artifacts, 'qualification_scope': 'Only the accepted new part:A profile cell, wall5 through recover_held_admitted; historical P1/P2 records are evidence history, not additional final cells',
                'future_outputs_excluded': ['live Map JSONL registries', 'scored evidence and derived results', 'final generated HTML'],
                'queued_materialization_job': job['id']}
    write(controls_path, controls)
    frozen_at = datetime.now(timezone.utc).isoformat()
    freeze = {'release_id': RELEASE, 'frozen_at': frozen_at,
              **{k: prepared[k] for k in ('code_sha256', 'environment_sha256', 'model_sha256', 'protocol_sha256', 'artifacts')},
              'selection_criteria': decision['selection_rule'] + ' Exact decision: ' + str(selected_path) + ' sha256=' + digest(selected_path) + '. Controls: ' + str(controls_path) + ' sha256=' + digest(controls_path) + '. Retain all264 dispositions and fixed12 trace slots, family-cluster bootstrap2000/publicseed0, no scored-result selection.',
              'maximum_retries': 0, 'restart_matching_mode': 'qualified_class', 'restart_qualification': qualification,
              'development_selection': ref(selected_path), 'control_index': ref(controls_path)}
    write(freeze_path, freeze)
    details = {
        'physical_workcell': 'Accept declared MuJoCo/Panda 95mm-grid n3/n6/n10 task feasibility: calibration007 seven primitive/timing checks, full-horizon C0 evidence including C0-01210/10, final-source C0-013/A3 pair and common-change tests. No universal state/contact guarantee.',
        'public_perception': 'Accept implemented public tagged-image/device-I/O interface:75 static centers, maximum1.267882mm under4mm, native camera round trips and actual tasks. Preserve stale/occluded/unavailable observations; no dynamic perception guarantee.',
        'independent_evaluator': 'Accept protected independent completion/partial/error checks, native-tick completion dwell and current436tests; premature done assertions and canonical C0-002 correction remain retained. Count alone is not completion.',
        'conventional_baseline': 'Accept competent durable conventional scheduler at all horizons, separate from LLM comparison; current C0-013 exercises admissible public after-release cut. Unsupported carry states are retained, never inferred from later task success.',
        'candidate_implementations': 'Accept all3 actual fixed14B mechanisms and matched persistence implementation based current-source mapping, development003 and actualA3pair, tests and source-matched narrative. A1 0/6 and A2 1/10 outcomes remain included; no success prerequisite or ranking.',
        'model_and_terms': 'Accept existing pinned commercially reusable model/runtime/assets under retained terms review, successful current artifact rehash and exact effective configuration. Qwen3-14B Q4_K_M, thinkingoff, context16384/output1024; baseline no model. No new spending or external access.',
        'isolation': 'Accept measured WSL bubblewrap filesystem/process/network/seccomp and actuator boundaries, current436tests and actual restart/D sandbox probes. Protected seeds/history remain outside candidate mount; scored D override rejected.',
        'timing_and_resources': 'Accept current actual-host timing including development003,C0-013,qualifiedA3pair and physical fixtures with physics during inference. Exact hardOSlimits plus five-second sampled watchdog/stale-observation rejection are frozen; resource_caps_enforced remainsfalse, peaks/wholeGPUattribution and termination tails unknown.',
        'evidence_retention': 'Accept complete29bundle inventory and current capacity for all156600seconds at3.189121856241325MiB/s plus50GiB; mandatory batch capacity checks, complete raw retention, direct source-bound readers/coordinator and once-only registrar. Git retains metadata, not full raw backup; final HTML/analysis are downstream outputs.',
        'disturbance_admissibility': 'Accept fixed public exposure/fallback rules and protected per-cut assessment with the independently validated A-only raw-pickup high-profile cell. Both actual onlineA3cuts admissible and admission absence covered. Three baseline transfer failures, old cuts, unsupported B/inserts/other profiles, fallback/unknown or inadmissible states stay visible and cannot count as qualified recovery. Finite empirical discrete support, no universal/continuous safety claim.',
        'equal_development_opportunity': 'Accept documented original common opportunity plus prospectively adopted symmetric prerequisite extension and completed accounting. Selectall4; unused allowances not unequal offered budgets. Historical/later activehours unmeasured and original time-limit complianceunknown, explicitly disclosed; no concealed/scored tuning.'}
    if set(details) != set(protocol.REQUIRED_GATES):
        raise ValueError('Gate set differs from protocol')
    ready = {'schema_version': 'batch01-final-readiness-1', 'release_id': RELEASE, 'recorded_at_utc': frozen_at,
             'operator': 'Codex session4 root', 'freeze_sha256': digest(freeze_path), 'scored_ready': True,
             'gates': {name: True for name in protocol.REQUIRED_GATES}, 'gate_details': {k: {'decision': 'accept_declared_scope_with_stated_limits', 'basis': v} for k, v in details.items()},
             'evidence_refs': [ref(controls_path), *[{k: row[k] for k in ('path', 'sha256')} for row in artifacts]],
             'resource_caps_enforced': False, 'scope': 'Concrete engineering readiness for the unchanged local simulation release, not result validity or demonstrated benefit. Every scored attempt is independently assessed.'}
    write(ready_path, ready)
    protocol.validate_release_gates(freeze_path, ready_path)
    print(json.dumps({'selection': ref(selected_path), 'control_index': ref(controls_path), 'freeze': ref(freeze_path), 'readiness': ref(ready_path), 'direct_files': len(ready['evidence_refs']), 'release_or_seeds_created': False}, indent=2))


if __name__ == '__main__':
    main()
