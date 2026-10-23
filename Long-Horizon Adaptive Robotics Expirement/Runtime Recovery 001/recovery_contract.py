"""Explicit administrative continuation contract; never authorizes a retry.

References in this contract are absolute. The original release, sources and
results remain immutable. This supplement identifies a different administrative
driver, not a replacement or retroactive enlargement of the original freeze.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
SCHEMA = 'robot-admin-continuation-1'
RELEASE_HASH = 'ed65f8b33e16daaa081031cfe7ccc7ac65644af3522546aad0d2fa76a1d72fe1'
QUEUE_HASH = '31997fc851494df62c2466cf189b5e945a6a933464f5cd43e69b3d877c029829'
ADMIN_RUN = 'batch01-eval-r4-C24-rep2-A1-persistent'
ADMIN_BATCH = '20260924T201725179192Z-055d76ec'
ANNEX_ID = 'batch01-eval-r4-admin-001'
HASH = re.compile(r'^[0-9a-f]{64}$')


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def semantic_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': digest(path)}


def reference(value):
    require(isinstance(value, dict) and isinstance(value.get('path'), str)
            and HASH.fullmatch(str(value.get('sha256', ''))), 'Malformed absolute reference')
    path = Path(value['path'])
    require(path.is_absolute(), 'Contract references must be absolute')
    # A resolved path alone conceals symlink/junction changes. Reject aliases.
    import stat
    for part in (path, *path.parents):
        if part.exists():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    'Reparse path in recovery reference')
    require(path.is_file() and digest(path) == value['sha256'], 'Missing/changed contract artifact: ' + str(path))
    return path.resolve()


def verify_source_index(index_ref):
    index = read(reference(index_ref))
    require(index.get('schema_version') == 'recovery-source-index-1', 'Unknown supplemental source index')
    require(Path(index.get('runtime_root', '')).resolve() == HERE, 'Supplement names another runtime root')
    files = index.get('files')
    require(isinstance(files, list) and files, 'Empty supplemental source index')
    paths = [reference(row) for row in files]
    require(len(paths) == len(set(paths)) and set(paths) == {p.resolve() for p in HERE.glob('*.py')},
            'Supplemental source set is incomplete, duplicated or extended')
    names = [row.get('archive_path') for row in files]
    require(names == [p.name for p in paths] and len(names) == len(set(names)), 'Invalid source archive mapping')
    with zipfile.ZipFile(reference(index.get('bundle'))) as archive:
        actual = archive.namelist()
        require(len(actual) == len(set(actual)) and set(actual) == set(names), 'Extra/missing/duplicate ZIP members')
        for row in files:
            require(hashlib.sha256(archive.read(row['archive_path'])).hexdigest() == row['sha256'],
                    'Supplement archive differs from current source')
    return index


def verify_analysis_index(index_ref):
    index = read(reference(index_ref))
    expected_root = EXPERIMENT / 'Batch 01' / 'Release Analysis 005'
    require(index.get('schema_version') == 'recovery-analysis-source-index-1'
            and Path(index.get('root', '')).resolve() == expected_root, 'Analysis source root differs')
    files = index.get('files', [])
    paths = [reference(row) for row in files]
    require(len(paths) == len(set(paths)) and set(paths) == {p.resolve() for p in expected_root.rglob('*') if p.is_file()},
            'Tested analysis source inventory differs')
    require(expected_root / 'collect_results.py' in paths and expected_root / 'analyze_results.py' in paths,
            'Analysis source inventory is incomplete')
    return index


def validate_disposition(value, release_ref, manifest_ref, annex_id):
    require(value.get('schema_version') == 'administrative-interruption-1'
            and value.get('annex_id') == annex_id and value.get('run_id') == ADMIN_RUN,
            'Administrative disposition identity mismatch')
    require(value.get('release') == release_ref and value.get('manifest') == manifest_ref,
            'Administrative disposition release/manifest differs')
    require(value.get('original_queue_job_id') == ADMIN_BATCH, 'Wrong interrupted job')
    require(value.get('execution_disposition') == 'interrupted' and value.get('validity') == 'invalid'
            and value.get('invalidity_class') == 'infrastructure' and value.get('task_outcome') == 'unknown',
            'Administrative disposition cannot assert a scored task outcome')
    require(value.get('physical_ended_at', 'absent') is None and value.get('metrics') == {}
            and value.get('post_run_integrity') == {'state': 'missing'}
            and value.get('supervisor_terminal') == {'state': 'missing'},
            'Missing interruption measurements must remain unknown')
    require(isinstance(value.get('administratively_recorded_at'), str) and value['administratively_recorded_at'],
            'Administrative recording time is required separately')
    receipt = read(reference(value.get('official_receipt')))
    require(receipt.get('id') == ADMIN_BATCH and receipt.get('state') == 'interrupted'
            and receipt.get('exit_status', 'absent') is None
            and receipt.get('error') == 'Worker disappeared; job was not retried',
            'Administrative disposition lacks the authentic interrupted/null receipt')
    require(value.get('queue_reconciled_at') == receipt.get('ended_at'), 'Reconciliation time differs')
    for evidence in value.get('evidence', []):
        reference(evidence)
    require(len(value.get('evidence', [])) >= 5, 'Administrative evidence is incomplete')
    inventory = read(reference(value.get('partial_evidence_inventory')))
    require(inventory.get('run_id') == ADMIN_RUN and inventory.get('complete_raw_result_present') is False,
            'Partial raw inventory identity differs')
    # Large partial raw files were hashed in the queued preflight. Do not reread
    # hundreds of MB here in a metadata finalizer. The immutable inventory records
    # exact bytes; before physical execution full inventory verification is required.
    require(inventory.get('files') and all(HASH.fullmatch(str(r.get('sha256', '')))
            and type(r.get('bytes')) is int and r['bytes'] >= 0 for r in inventory['files']),
            'Incomplete partial evidence inventory')


def verify_partial_inventory(disposition):
    inventory = read(reference(disposition['partial_evidence_inventory']))
    raw_root = Path(inventory['root']).resolve()
    expected = {Path(r['path']).resolve(): r for r in inventory['files']}
    require(set(expected) == {p.resolve() for p in raw_root.rglob('*') if p.is_file()},
            'Partial evidence file set changed')
    for path, row in expected.items():
        require(path.is_relative_to(raw_root) and path.stat().st_size == row['bytes'], 'Partial evidence size/path changed')
        reference(row)


def _same_payload(candidate, adopted):
    omitted = {'status', 'adoption', 'validation'}
    return {k: v for k, v in candidate.items() if k not in omitted} == {
        k: v for k, v in adopted.items() if k not in omitted}


def verify_adoption(annex):
    require(annex.get('status') == 'adopted', 'Recovery annex is not adopted')
    adoption = annex.get('adoption', {})
    require(adoption.get('author') == 'Codex session 4' and adoption.get('recorded_at')
            and adoption.get('no_policy_or_scoring_change') is True
            and adoption.get('authorization') and adoption.get('contract_departure'),
            'Explicit scoped administrative amendment is missing')
    validation = annex.get('validation', {})
    candidate_ref = validation.get('prepared_annex')
    candidate = read(reference(candidate_ref))
    require(candidate.get('status') == 'prepared' and _same_payload(candidate, annex),
            'Adopted authority differs from validated prospective payload')
    report_path = reference(validation.get('report'))
    report = read(report_path)
    receipt = read(reference(validation.get('official_receipt')))
    require(report.get('prepared_annex') == candidate_ref and report.get('passed') is True
            and report.get('source_index') == annex['source_index']
            and report.get('analysis_source_index') == annex['analysis_source_index']
            and report.get('queue_job_id') == receipt.get('id'), 'Preflight report binding differs')
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0, 'Preflight did not officially succeed')
    require(report.get('checks') and all(v is True for v in report['checks'].values()),
            'Preflight checks are incomplete or failed')
    for check in ('original_release_verified', 'same_physical_source_locations', 'partial_inventory_verified',
                  'retained_originals_verified', 'retained_selection_exactly_equal', 'source_diff_restricted', 'tests_passed'):
        require(report['checks'].get(check) is True, 'Missing required preflight check: ' + check)
    reference(report.get('retained_selection_differential'))
    reference(report.get('module_locations'))
    require(len(report.get('executions', [])) == 2, 'Required recovery/analysis suites are missing')
    for execution in report['executions']:
        require(type(execution.get('exit_status')) is int and execution['exit_status'] == 0, 'Suite did not succeed')
        reference(execution.get('stdout')); reference(execution.get('stderr'))
    # No execution/import is necessary to bind argv: exact options are established
    # by the queued preparer and must be present unchanged in the official receipt.
    expected = [str(EXPERIMENT.parent / 'venv' / 'Scripts' / 'python.exe'), '-X', 'utf8', '-B',
                str(HERE / 'prepare_recovery.py'), 'validate', '--annex', candidate_ref['path'],
                '--output', str(report_path.parent)]
    require(report_path.name == 'validation.json' and report.get('queued_argv') == expected
            and receipt.get('argv') == expected and Path(receipt.get('cwd', '')).resolve() == EXPERIMENT.parent,
            'Preflight receipt is for another command or output')


def verify_annex(annex_path, release_dir=None, require_adopted=True):
    annex_path = Path(annex_path).resolve(); annex = read(annex_path)
    require(annex.get('schema_version') == SCHEMA and annex.get('annex_id') == ANNEX_ID,
            'Unknown administrative authority')
    release_ref = annex.get('release'); release_path = reference(release_ref)
    require(release_ref['sha256'] == RELEASE_HASH and release_path.name == 'release.json', 'Wrong original r4 release')
    root = release_path.parent
    if release_dir is not None:
        require(root == Path(release_dir).resolve(), 'Annex names another release')
    require(Path(annex.get('original_runtime_root', '')).resolve() == EXPERIMENT / 'Runtime 004',
            'Original physical source root moved')
    queue = annex.get('installed_queue'); reference(queue)
    require(queue['sha256'] == QUEUE_HASH, 'Installed queue differs from the approved repair')
    reference(annex.get('queue_repair_verification'))
    read_decision = read(reference(annex.get('serialized_read_decision')))
    diagnostic = read(reference(read_decision.get('diagnostic')))
    diagnostic_receipt = read(reference(read_decision.get('official_receipt')))
    require(diagnostic.get('completed') is True and diagnostic.get('sources_unchanged') is True
            and diagnostic.get('serialized_case', {}).get('passed') is True
            and diagnostic_receipt.get('id') == diagnostic.get('ownership', {}).get('job_id')
            and diagnostic_receipt.get('state') == 'succeeded'
            and type(diagnostic_receipt.get('exit_status')) is int and diagnostic_receipt['exit_status'] == 0,
            'Serialized ownership read lacks successful diagnostic evidence')
    reference(annex.get('superseded_failed_validation'))
    source_index = verify_source_index(annex.get('source_index'))
    verify_analysis_index(annex.get('analysis_source_index'))
    release = read(release_path); public = sorted(release['manifest_refs'], key=lambda r: r['scheduled_index'])
    require(len(public) == 264 and [r['scheduled_index'] for r in public] == list(range(1, 265)),
            'Original stored schedule differs')
    by_id = {row['run_id']: {'path': str((root / row['path']).resolve()), 'sha256': row['sha256']} for row in public}
    require(len(by_id) == 264, 'Duplicated original identity')
    partitions = [annex.get(k) for k in ('retained_originals', 'administrative_dispositions', 'remaining_originals')]
    require(all(isinstance(p, list) for p in partitions) and list(map(len, partitions)) == [132, 1, 131],
            'Administrative partition must preserve exactly 132 + 1 + 131 originals')
    retained, administrative, remaining = partitions
    ordered = list(by_id)
    ids = [[r.get('run_id') for r in p] for p in partitions]
    require(len(set(sum(ids, []))) == 264 and set(sum(ids, [])) == set(by_id), 'Partition duplicates/omits original run')
    require(all(group == [rid for rid in ordered if rid in group] for group in ids), 'Stored order changed')
    require(ids[1] == [ADMIN_RUN] and annex.get('administrative_batch_ids') == [ADMIN_BATCH],
            'Administrative exception exceeds the one interrupted attempt/batch')
    require(annex.get('invariants') == {'automatic_retries': 0, 'bootstrap_draws': 2000, 'bootstrap_seed': 0,
            'policy_physics_model_budgets_scoring_unchanged': True, 'stored_order_preserved': True,
            'fixed_trace_count': 12, 'administrative_outcome': 'unknown'}, 'Scientific invariants differ')
    for row in retained + remaining:
        rid = row['run_id']; require(row.get('manifest_ref') == by_id[rid], 'Original manifest reference changed')
        reference(row['manifest_ref'])
    # Only append operations may change the canonical store. Existing protected
    # records are bound semantically, independent of new unrelated rows.
    map_root = EXPERIMENT / 'Architecture Map'
    canonical = {}
    for kind in ('run', 'result', 'revision'):
        rows = [json.loads(line) for line in (map_root / (kind + 's.jsonl')).read_text(encoding='utf-8').splitlines() if line.strip()]
        require(len({r['id'] for r in rows}) == len(rows), 'Duplicate canonical identity')
        canonical[kind] = {r['id']: r for r in rows}
    for row in retained:
        rid = row['run_id']; terminal_path = reference(row.get('terminal_ref'))
        require(terminal_path == root / 'attempts' / rid / 'terminal.json', 'Retained terminal names another attempt')
        terminal = read(terminal_path)
        require(terminal.get('run_id') == rid and terminal.get('release_sha256') == RELEASE_HASH
                and terminal.get('manifest_sha256') == by_id[rid]['sha256'], 'Retained terminal identity differs')
        for item in row.get('protected_refs', []):
            reference(item)
        require(len(row.get('protected_refs', [])) >= 7, 'Retained finalization bindings incomplete')
        result = canonical['result'].get(rid + '-result')
        require(result is not None and semantic_hash(result) == row.get('canonical_result_sha256'),
                'Retained canonical result changed')
        require(semantic_hash(canonical['run'].get(rid)) == row.get('canonical_run_sha256'),
                'Retained canonical registration changed')
        require([r for r in canonical['result'].values() if r.get('run_id') == rid] == [result],
                'Retained result acquired a conflicting correction')
    for row in annex.get('protected_canonical_revisions', []):
        require(semantic_hash(canonical['revision'].get(row['id'])) == row['sha256'], 'Original revision changed')
    require(len(annex.get('protected_canonical_revisions', [])) == 4, 'Original revision bindings incomplete')
    dispositions = {}
    for row in administrative:
        rid = row['run_id']; value = read(reference(row.get('disposition_ref')))
        validate_disposition(value, release_ref, by_id[rid], annex['annex_id'])
        require(row.get('expected_canonical_note_id') == rid + '-administrative-interruption-001', 'Administrative note identity changed')
        require(not (root / 'attempts' / rid / 'terminal.json').exists()
                and not (root / 'batches' / ADMIN_BATCH / 'finished.json').exists()
                and not (root / 'batches' / ADMIN_BATCH / 'finalized.json').exists(), 'Historical missing terminal was replaced')
        require(not any(r.get('run_id') == rid for r in canonical['result'].values()), 'Administrative attempt has a conflicting normal result')
        require(semantic_hash(canonical['run'].get(rid)) == value.get('canonical_run_sha256'), 'Interrupted registration changed')
        dispositions[rid] = value
    for item in annex.get('original_reviews', []):
        reference(item)
    require(len(annex.get('original_reviews', [])) == 3, 'Original infrastructure reviews must be preserved')
    reference(annex.get('source_change_review'))
    architectures = ('baseline', 'A1', 'A2', 'A3')
    require(annex.get('revision_ids') == {a: ANNEX_ID + '-' + a for a in architectures}
            and annex.get('parent_revision_ids') == {a: 'batch01-eval-r4-' + a + '-frozen' for a in architectures},
            'Recovery revision lineage differs')
    if require_adopted:
        verify_adoption(annex)
    else:
        require(annex.get('status') in ('prepared', 'adopted'), 'Unknown annex status')
    return {'annex': annex, 'annex_ref': ref(annex_path), 'root': root, 'source_index': source_index,
            'source_index_ref': annex['source_index'], 'retained_run_ids': ids[0], 'administrative_run_ids': ids[1],
            'administrative_batch_ids': [ADMIN_BATCH], 'allowed_run_ids': ids[2], 'dispositions': dispositions}
