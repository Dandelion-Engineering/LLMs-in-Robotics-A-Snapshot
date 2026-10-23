"""Assemble unchanged provisional cells; acceptance is an explicit operator input.

CLI use is queue-only because retained evidence is rehashed. Without --acceptance
the outputs are unusable drafts. No physics, fitting, seeds or readiness grant.
The public function exists for bounded synthetic tests, not a queue bypass.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

from bundle_construction import validate_provisional_rule
from compatibility import digest, sha

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[3] / 'Runtime 004'
ASSESSOR = HERE / 'assess_validation.py'
ACCEPTANCE_SCHEMA = 'operator-restart-qualification-acceptance-1'
SUPPORTS = {'carry_state', 'absence_survival', 'whole_arm_payload_route',
            'settled_placement', 'development_validation'}
QUEUE_IDENTITY = ('id', 'child_pid', 'worker_pid', 'resolved_executable', 'argv', 'cwd', 'started_at')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def stamp(value):
    require(isinstance(value, str), 'Missing timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timestamp requires a timezone')
    return result.astimezone(timezone.utc)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def runtime_modules():
    if str(RUNTIME) not in sys.path:
        sys.path.insert(0, str(RUNTIME))
    import restart_calibration_loader
    import release_runner
    return restart_calibration_loader, release_runner


class Inputs:
    def __init__(self):
        self.refs = {}
        self.member_refs = {}

    def read(self, path, expected=None, *, parse=False):
        path = Path(path).resolve()
        require('candidate_state' not in [p.casefold() for p in path.parts], 'Candidate state is not qualification evidence')
        before = path.stat()
        if parse:
            raw = path.read_bytes()
            value = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            checksum = hashlib.sha256(raw).hexdigest()
        else:
            with path.open('rb') as stream:
                checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
            value = None
        after = path.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Input changed while reading: ' + str(path))
        ref = {'path': str(path), 'sha256': checksum, 'bytes': after.st_size}
        if expected is not None:
            require(sha(expected.get('sha256')) and expected['sha256'] == checksum,
                    'Input hash differs: ' + str(path))
            require('bytes' not in expected or expected['bytes'] == after.st_size, 'Input size differs: ' + str(path))
        require(path not in self.refs or self.refs[path] == ref, 'Input identity changed during assembly')
        self.refs[path] = ref
        return value, ref

    def reference(self, ref, base, *, parse=False):
        if isinstance(ref, dict) and ('archive' in ref or 'member' in ref):
            return self.archive_member(ref, base, parse=parse)
        require(isinstance(ref, dict) and text(ref.get('path')) and sha(ref.get('sha256')), 'Malformed input reference')
        path = Path(ref['path'])
        return self.read(path if path.is_absolute() else base / path, ref, parse=parse)

    def archive_member(self, ref, base, *, parse=False):
        require('path' not in ref and text(ref.get('archive')) and text(ref.get('member'))
                and sha(ref.get('sha256')), 'Malformed archive member reference')
        member = ref['member']; member_path = PurePosixPath(member)
        require(not member_path.is_absolute() and '..' not in member_path.parts and '\\' not in member
                and member == str(member_path), 'Unsafe or noncanonical archive member')
        archive = Path(ref['archive'])
        archive = (archive if archive.is_absolute() else base / archive).resolve()
        require(archive in self.refs, 'Archive absent from previously verified input inventory')
        before = archive.stat()
        with zipfile.ZipFile(archive) as bundle:
            matches = [info for info in bundle.infolist() if info.filename == member]
            require(len(matches) == 1 and not matches[0].is_dir(), 'Archive member missing or ambiguous')
            with bundle.open(matches[0]) as stream:
                if parse:
                    raw = stream.read()
                    value = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
                    checksum = hashlib.sha256(raw).hexdigest()
                else:
                    checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
                    value = None
        after = archive.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Archive changed while reading member')
        require(checksum == ref['sha256'], 'Archive member hash differs: ' + member)
        require('bytes' not in ref or ref['bytes'] == matches[0].file_size, 'Archive member size differs')
        verified = {'archive': str(archive), 'member': member, 'sha256': checksum,
                    'bytes': matches[0].file_size, 'archive_ref': self.refs[archive]}
        key = (archive, member)
        require(key not in self.member_refs or self.member_refs[key] == verified, 'Archive member identity changed during assembly')
        self.member_refs[key] = verified
        return value, verified

    def stable(self):
        for path, ref in list(self.refs.items()):
            self.read(path, ref)


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def bind_inputs(rule_path, assessment_path, receipt_path):
    inputs = Inputs()
    rule, rule_ref = inputs.read(rule_path, parse=True)
    assessment, assessment_ref = inputs.read(assessment_path, parse=True)
    receipt, receipt_ref = inputs.read(receipt_path, parse=True)
    validate_provisional_rule(rule)
    require(assessment.get('schema_version') == 'restart-fixed-rule-validation-assessment-1', 'Unsupported assessment')
    require(assessment.get('qualification_granted') is False and assessment.get('scored_ready_claimed') is False,
            'Assessment must retain its non-authorizing scope')
    job = assessment.get('assessment_queue')
    require(isinstance(job, dict) and all(k in job and receipt.get(k) == job[k] for k in QUEUE_IDENTITY),
            'Receipt differs from assessment job identity')
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int and receipt['exit_status'] == 0,
            'Successful assessment receipt required')
    require(stamp(receipt['started_at']) <= stamp(assessment['completed_at']) <= stamp(receipt['ended_at']),
            'Receipt does not cover completed assessment')
    _, runner = runtime_modules()
    require(runner.python_entrypoint(job['argv'], job['cwd']) == ASSESSOR, 'Receipt names another assessor')
    argv = job['argv']
    require(argv.count('--output') == 1, 'Assessment output argument is ambiguous')
    output_arg = Path(argv[argv.index('--output') + 1])
    output_arg = (output_arg if output_arg.is_absolute() else Path(job['cwd']) / output_arg).resolve()
    require(Path(assessment_path).resolve() == output_arg / 'assessment.json', 'Assessment does not match queued output')
    _, bound_rule = inputs.reference(assessment['rule_ref'], Path(assessment_path).resolve().parent)
    require(bound_rule == rule_ref and assessment.get('canonical_rule_sha256') == digest(rule), 'Assessed rule differs')
    spec, spec_ref = inputs.reference(rule['class_spec'], Path(rule_path).resolve().parent, parse=True)
    require(digest(spec) == rule['class_spec']['canonical_sha256'], 'Canonical class specification differs')
    _, assessed_spec = inputs.reference(assessment['class_spec_ref'], Path(assessment_path).resolve().parent)
    require(assessed_spec == spec_ref, 'Assessed class specification differs')
    require(assessment.get('construction_extraction_ref', {}).get('sha256') == rule['construction_extraction']['sha256'],
            'Construction identity differs')
    consumed = assessment.get('consumed_files')
    require(isinstance(consumed, list) and consumed, 'Assessment lacks retained byte verification inventory')
    consumed_paths = set()
    for ref in consumed:
        require(isinstance(ref, dict) and 'archive' not in ref and 'member' not in ref,
                'Consumed inventory must bind whole-file bytes')
        _, verified = inputs.reference(ref, Path(assessment_path).resolve().parent)
        consumed_paths.add(verified['path'])
    for name in ('validation_extraction_ref', 'validation_receipt_ref', 'extraction_receipt_ref',
                 'construction_extraction_ref', 'numeric_source_ref', 'fixture_predicate_source_ref', 'compatibility_source_ref'):
        _, ref = inputs.reference(assessment[name], Path(assessment_path).resolve().parent)
        require(ref.get('path', ref.get('archive')) in consumed_paths,
                'Assessment reference absent from consumed inventory: ' + name)
    dependencies = assessment.get('assessor_dependency_sha256')
    require(isinstance(dependencies, dict) and dependencies, 'Assessor source verification missing')
    for path, checksum in dependencies.items():
        inputs.read(path, {'sha256': checksum})
    _, assessor_ref = inputs.read(ASSESSOR, {'sha256': assessment.get('assessor_sha256')})
    require(dependencies.get(str(ASSESSOR)) == assessor_ref['sha256'], 'Assessor not covered by source inventory')
    require(isinstance(assessment.get('trials'), list) and isinstance(assessment.get('construction_trials'), list),
            'Full declared trial outcomes are missing')
    ids = [row['trial_id'] for row in assessment['trials']]
    require(len(ids) == len(set(ids)), 'Duplicate assessed trial')
    selected = assessment.get('selected_validation_ids')
    require(isinstance(selected, list) and selected and len(selected) == len(set(selected)) and set(selected) <= set(ids),
            'Completed selected validation identities are missing')
    return inputs, rule, rule_ref, spec, assessment, assessment_ref, receipt_ref, consumed_paths


def acceptance_cells(acceptance, rule, rule_ref, assessment, assessment_ref, inputs, consumed_paths, base):
    require(acceptance.get('schema_version') == ACCEPTANCE_SCHEMA
            and acceptance.get('decision') == 'accept_unchanged_provisional_rule', 'Explicit operator acceptance missing')
    require(text(acceptance.get('operator')) and text(acceptance.get('root_note'))
            and text(acceptance.get('validation_review_note')), 'Concrete operator/support review notes missing')
    require(acceptance.get('rule_sha256') == rule_ref['sha256']
            and acceptance.get('assessment_sha256') == assessment_ref['sha256'], 'Acceptance binds different rule or assessment bytes')
    require(stamp(assessment['completed_at']) <= stamp(acceptance['accepted_at_utc']) < datetime.now(timezone.utc),
            'Acceptance must follow completed assessment and precede assembly')
    decisions = acceptance.get('cells')
    require(isinstance(decisions, dict) and set(decisions) == set(rule['payload_template_to_cell'].values()),
            'Acceptance must cover exactly the unchanged mapped cells')
    cells, support_files = copy.deepcopy(rule['cells']), []
    selected = set(assessment['selected_validation_ids'])
    for cell in cells:
        if cell['cell_id'] not in decisions:
            continue
        decision = decisions[cell['cell_id']]
        require(decision.get('provisional_cell_sha256') == digest(cell), 'Accepted cell differs from provisional values')
        require(text(decision.get('root_note')), 'Cell support decision requires a concrete note')
        scope = decision.get('validation_scope', {})
        require(isinstance(scope.get('trial_ids'), list) and scope['trial_ids'] and set(scope['trial_ids']) <= selected
                and text(scope.get('note')), 'Cell validation scope must name retained selected trials and its limits')
        supports, added = set(), []
        references = decision.get('support_refs')
        require(isinstance(references, list) and references, 'Explicit per-cell physical support decisions missing')
        for ref in references:
            require(text(ref.get('artifact_id')) and text(ref.get('reason')), 'Physical support identity/reason missing')
            purposes = ref.get('supports')
            require(isinstance(purposes, list) and purposes and set(purposes) <= SUPPORTS,
                    'Physical support purposes missing or unsupported')
            _, verified = inputs.reference(ref, base)
            require(verified['path'] in consumed_paths, 'Support artifact was not verified by completed assessment')
            require(stamp(ref['recorded_at_utc']) <= stamp(acceptance['accepted_at_utc']), 'Support artifact postdates acceptance')
            supports.update(purposes)
            support_files.append({'artifact_id': ref['artifact_id'], **verified})
            added.append({'kind': 'prior_physical_calibration', 'artifact_id': ref['artifact_id'],
                'sha256': verified['sha256'], 'bytes_verified_by_operator': True,
                'recorded_at_utc': ref['recorded_at_utc'], 'supports': purposes, 'support_decision': ref['reason']})
        require(SUPPORTS <= supports, 'Mapped cell lacks explicit decisions for all required support categories')
        original = cell.get('evidence_refs', [])
        require(isinstance(original, list), 'Provisional evidence references malformed')
        # Preserve every predeclared value. New physical support is metadata only.
        cell['evidence_refs'] = copy.deepcopy(original) + [ref for ref in added if ref not in original]
        for key, value in next(c for c in rule['cells'] if c['cell_id'] == cell['cell_id']).items():
            require((cell[key][:len(value)] == value) if key == 'evidence_refs' else cell[key] == value,
                    'Assembly changed a provisional cell field')
    return cells, support_files


def assemble(rule_path, assessment_path, receipt_path, output, *, acceptance_path=None, queue_authority=None):
    output = Path(output).resolve()
    require(not output.exists(), 'Assembly output must be fresh; retain prior attempts')
    require('candidate_state' not in [p.casefold() for p in output.parts], 'Output cannot be candidate state')
    values = bind_inputs(rule_path, assessment_path, receipt_path)
    inputs, rule, rule_ref, spec, assessment, assessment_ref, receipt_ref, consumed_paths = values
    for directory in assessment.get('input_directories', []):
        root = Path(directory).resolve()
        require(not (output == root or root in output.parents or output in root.parents), 'Output overlaps retained evidence')
    acceptance = None
    cells, support_files = copy.deepcopy(rule['cells']), []
    if acceptance_path is not None:
        acceptance, acceptance_ref = inputs.read(acceptance_path, parse=True)
        receipt, _ = inputs.read(receipt_path, parse=True)
        require(stamp(receipt['ended_at']) <= stamp(acceptance['accepted_at_utc']),
                'Operator acceptance must follow official assessment completion')
        cells, support_files = acceptance_cells(acceptance, rule, rule_ref, assessment, assessment_ref,
                                               inputs, consumed_paths, Path(acceptance_path).resolve().parent)
    else:
        acceptance_ref = None
    loader, _ = runtime_modules()
    implementation_refs = []
    for path in (Path(__file__), HERE / 'bundle_construction.py', HERE / 'compatibility.py',
                 RUNTIME / 'restart_calibration_loader.py', RUNTIME / 'restart_qualification.py',
                 RUNTIME / 'restart_compatibility.py', RUNTIME / 'restart_physical_class.py'):
        _, ref = inputs.read(path)
        implementation_refs.append(ref)
    for path in inputs.refs:
        require(output not in path.parents and output != path, 'Output contains an input')
    files = [{'artifact_id': 'retained-' + hashlib.sha256(str(path).encode('utf-8')).hexdigest(), **ref}
             for path, ref in sorted(inputs.refs.items(), key=lambda item: str(item[0]))]
    by_id = {ref['artifact_id']: ref for ref in files}
    for ref in support_files:
        require(ref['artifact_id'] not in by_id or by_id[ref['artifact_id']] == ref, 'Artifact ID has conflicting identities')
        by_id[ref['artifact_id']] = ref
    # Existing references are never trusted merely because a boolean says verified.
    if acceptance:
        for cell in cells:
            for ref in cell.get('evidence_refs', []):
                require(ref.get('artifact_id') in by_id and by_id[ref['artifact_id']]['sha256'] == ref.get('sha256'),
                        'Provisional physical reference lacks independent artifact verification')
    bundle = {'schema_version': 'prior-restart-class-qualification-1',
        'status': 'measured_development' if acceptance else 'draft_requires_operator_acceptance',
        'accepted_at_utc': acceptance['accepted_at_utc'] if acceptance else None,
        'empirical_transfer_rule': rule['empirical_transfer_rule'], 'class_spec': spec, 'cells': cells,
        'artifact_files': list(by_id.values()), 'geometry_scope': rule['geometry_scope'],
        'untested_combinations': rule['untested_combinations'],
        'provisional_rule_ref': rule_ref, 'provisional_rule_canonical_sha256': digest(rule),
        'provisional_cell_sha256': {cell['cell_id']: digest(cell) for cell in rule['cells']},
        'assessment_ref': assessment_ref, 'assessment_canonical_sha256': digest(assessment),
        'assessment_trial_index': {name: [{key: row[key] for key in
            ('trial_id', 'execution_status', 'selected_validation', 'state', 'binding_state', 'child_status') if key in row}
            for row in assessment[name]] for name in ('construction_trials', 'trials')},
        'selected_validation_ids': assessment['selected_validation_ids'],
        'assessment_summary': {key: assessment[key] for key in
            ('finite_declared_checks_state', 'selected_state_counts', 'source_holds', 'construction_binding_complete',
             'validation_set_support', 'limitations', 'continuous_clearance_bound_m') if key in assessment},
        'assessment_receipt_ref': receipt_ref, 'operator_acceptance': acceptance,
        'operator_acceptance_ref': acceptance_ref, 'assembly_implementation_refs': implementation_refs,
        'archive_member_refs': list(inputs.member_refs.values()),
        'qualification_granted_by_assembler': False, 'scored_ready_claimed': False}
    inputs.stable()
    output.mkdir(parents=True, exist_ok=False)
    suffix = '' if acceptance else '.draft'
    bundle_path = output / ('qualification' + suffix + '.json')
    write(bundle_path, bundle)
    with bundle_path.open('rb') as stream:
        bundle_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    freeze = {'schema_version': 'development-restart-qualification-freeze-1', 'stage': 'development',
        'frozen_at': datetime.now(timezone.utc).isoformat() if acceptance else None,
        'restart_matching_mode': 'qualified_class', 'restart_qualification': {
            'path': str(bundle_path), 'sha256': bundle_hash, 'bundle_sha256': digest(bundle),
            'class_spec_sha256': digest(spec), 'selection_rule': rule['selection_rule'],
            'payload_template_to_cell': rule['payload_template_to_cell'], **rule['absence']},
        'scored_ready_claimed': False, 'evaluation_seeds_created': False}
    freeze_path = output / ('development-freeze' + suffix + '.json')
    write(freeze_path, freeze)
    if acceptance:
        loader.load_restart_qualification(freeze, freeze_path)
    else:
        write(output / 'acceptance.draft.json', {'schema_version': ACCEPTANCE_SCHEMA,
            'decision': None, 'operator': None, 'accepted_at_utc': None, 'root_note': None,
            'validation_review_note': None, 'rule_sha256': rule_ref['sha256'],
            'assessment_sha256': assessment_ref['sha256'], 'cells': {
                cell['cell_id']: {'provisional_cell_sha256': digest(cell), 'root_note': None,
                    'validation_scope': {'trial_ids': [], 'note': None}, 'support_refs': []}
                for cell in rule['cells'] if cell['cell_id'] in rule['payload_template_to_cell'].values()}})
    inputs.stable()
    report = {'schema_version': 'restart-qualification-assembly-1', 'status': 'complete',
        'completed_at': datetime.now(timezone.utc).isoformat(), 'assembly_queue': queue_authority,
        'operator_acceptance_present': acceptance is not None, 'loader_validation': 'pass' if acceptance else 'not_run_draft',
        'qualification_granted_by_assembler': False, 'scored_ready_claimed': False,
        'inputs_unchanged': True, 'input_refs': list(inputs.refs.values()), 'rule_ref': rule_ref,
        'archive_member_refs': list(inputs.member_refs.values()),
        'assessment_ref': assessment_ref, 'bundle_path': str(bundle_path), 'development_freeze_path': str(freeze_path),
        'missing_provisional_loader_metadata': {cell['cell_id']: [key for key in
            ('envelope_basis', 'maximum_qualified_absence_s', 'absence_timebase', 'absence_endpoint') if key not in cell]
            for cell in rule['cells']},
        'scope': 'Explicit operator decision assembled; unchanged provisional numerical cells. All assessed rows retained.'}
    write(output / 'assembly.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rule', 'assessment', 'assessment-receipt', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--acceptance')
    args = parser.parse_args(argv)
    _, runner = runtime_modules()
    job = runner.queued_job(expected_script=Path(__file__).resolve())
    receipt = json.loads(Path(args.assessment_receipt).read_text(encoding='utf-8'))
    runner.verify_queue_receipt(receipt['id'], args.assessment_receipt)
    report = assemble(args.rule, args.assessment, args.assessment_receipt, args.output,
                      acceptance_path=args.acceptance, queue_authority=job)
    print(json.dumps({'queue_job_id': job['id'], 'output': str(Path(args.output).resolve()),
                      'loader_validation': report['loader_validation'], 'qualification_granted_by_assembler': False}))


if __name__ == '__main__':
    main()
