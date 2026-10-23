"""Temporary synthetic metadata only; public slots contain no concealed seeds."""
import copy
import json
from pathlib import Path

import collect_results as c


class Fixture:
    def __init__(self, base):
        self.base = Path(base).resolve(); self.root = self.base / 'release'
        (self.root / 'runs').mkdir(parents=True)
        self.freeze = self.base / 'freeze.json'; self.ready = self.base / 'readiness.json'
        self.write(self.freeze, {'release_id': 'unit-admin', 'protocol_sha256': c.ref(c.protocol.__file__)['sha256']})
        self.write(self.ready, {'release_id': 'unit-admin', 'freeze_sha256': c.ref(self.freeze)['sha256']})
        self.manifests = c.protocol.public_run_slots('unit-admin'); refs = []
        for manifest in self.manifests:
            manifest.update(freeze_sha256=c.ref(self.freeze)['sha256'], readiness_sha256=c.ref(self.ready)['sha256'],
                            artifact_hashes={'protocol_sha256': c.ref(c.protocol.__file__)['sha256']})
            path = self.root / 'runs' / (manifest['run_id'] + '.json'); self.write(path, manifest)
            refs.append({'run_id': manifest['run_id'], 'path': path.relative_to(self.root).as_posix(), 'sha256': c.ref(path)['sha256']})
        self.write(self.root / 'release.json', {'schema_version': c.protocol.SCHEMA_VERSION, 'release_id': 'unit-admin',
                                               'freeze_manifest': c.ref(self.freeze), 'readiness': c.ref(self.ready), 'manifest_refs': refs})
        self.original, self.admin, self.new = [row['run_id'] for row in self.manifests[:3]]
        self.annex_path = self.base / 'annex.json'; self.disposition_path = self.base / 'disposition.json'
        self.source_index_path = self.base / 'source-index.json'; self.receipt_path = self.base / 'interrupted.json'
        self.write(self.source_index_path, {'schema_version': 'synthetic-source-index', 'files': []})
        self.receipt = {'id': 'interrupted-job', 'state': 'interrupted', 'exit_status': None}
        self.write(self.receipt_path, self.receipt)
        self.disposition = {'schema_version': 'administrative-interruption-1', 'annex_id': 'unit-annex', 'run_id': self.admin,
                            'execution_disposition': 'interrupted', 'validity': 'invalid', 'invalidity_class': 'infrastructure',
                            'task_outcome': 'unknown', 'physical_ended_at': None,
                            'administratively_recorded_at': '2026-09-24T20:40:38+00:00',
                            'post_run_integrity': {'state': 'missing'}, 'supervisor_terminal': {'state': 'missing'},
                            'metrics': {}, 'original_queue_job_id': 'interrupted-job', 'official_receipt': c.ref(self.receipt_path)}
        self.annex = {'annex_id': 'unit-annex', 'status': 'adopted',
                      'revision_ids': {a: 'unit-admin-' + a + '-admin001'
                                       for a in c.protocol.ARCHITECTURES}}
        self.notes = [{'id': 'canonical-admin-note', 'recorded_at': '2026-09-24T20:41:00+00:00',
                       'target_ids': [self.admin], 'claim_type': 'decision', 'supersedes_note_id': None,
                       'details': {'provenance_kind': 'administrative_interruption'}}]
        self.sync_authority()
        self.records = []; self.add_terminal(self.original)

    @staticmethod
    def write(path, value):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')

    def sync_authority(self):
        self.disposition['official_receipt'] = c.ref(self.receipt_path)
        self.write(self.disposition_path, self.disposition)
        self.annex['administrative_dispositions'] = [{'run_id': self.admin,
            'disposition_ref': c.ref(self.disposition_path), 'expected_canonical_note_id': 'canonical-admin-note'}]
        self.write(self.annex_path, self.annex)
        self.notes[0]['details'].update(administrative_disposition_ref=c.ref(self.disposition_path),
                                       recovery_annex_ref=c.ref(self.annex_path))

    def verified(self):
        return {'annex': copy.deepcopy(self.annex), 'annex_ref': c.ref(self.annex_path), 'root': self.root,
                'allowed_run_ids': [m['run_id'] for m in self.manifests if m['run_id'] not in (self.original, self.admin)],
                'retained_run_ids': [self.original], 'administrative_run_ids': [self.admin],
                'administrative_batch_ids': ['interrupted-job'], 'dispositions': {self.admin: copy.deepcopy(self.disposition)},
                'source_index': c.read(self.source_index_path), 'source_index_ref': c.ref(self.source_index_path)}

    def fake_verify(self, path, release_dir=None, require_adopted=True):
        if Path(path).resolve() != self.annex_path or Path(release_dir).resolve() != self.root or not require_adopted:
            raise ValueError('Fixture requires exact adopted annex/root')
        if self.annex['status'] != 'adopted':
            raise ValueError('Annex is not adopted')
        return self.verified()

    def add_terminal(self, rid, recovery=False):
        manifest = next(m for m in self.manifests if m['run_id'] == rid)
        job = 'job-' + str(self.manifests.index(manifest))
        attempt, batch = self.root / 'attempts' / rid, self.root / 'batches' / job
        extra = {'recovery_annex_ref': c.ref(self.annex_path),
                 'recovery_source_index_ref': c.ref(self.source_index_path)} if recovery else {}
        revision = 'unit-admin-' + manifest['architecture'] + '-admin001'
        raw = {'run_id': rid, 'stage': 'evaluation', 'execution_status': 'completed', 'validity': 'valid',
               'outcome': 'success', 'ended_at': '2026-09-24T20:00:00+00:00', 'termination_reason': 'completed',
               'completion_time_s': 12.5, 'wall_duration_s': 13., 'model_calls': 2, 'total_tokens': 50}
        self.write(attempt / 'evidence' / 'result.json', raw)
        terminal = {'run_id': rid, 'queue_job_id': job, 'release_sha256': c.ref(self.root / 'release.json')['sha256'],
                    'manifest_sha256': c.ref(self.root / 'runs' / (rid + '.json'))['sha256'], 'result': raw,
                    'post_run_integrity': {'passed': True}, 'supervisor_result_ref': c.ref(attempt / 'evidence' / 'result.json'), **extra}
        if recovery:
            terminal['revision_id'] = revision
            self.write(attempt / 'registered.json', {'run_id': rid, 'revision_id': revision, **extra})
        self.write(attempt / 'terminal.json', terminal)
        receipt = {'id': job, 'state': 'succeeded', 'exit_status': 0}
        self.write(batch / 'official-queue-status.json', receipt)
        self.write(batch / 'planned.json', {'queue_job_id': job, 'release_sha256': terminal['release_sha256'],
                                          'selected_run_ids': [rid], **extra})
        self.write(batch / 'finished.json', {'queue_job_id': job, 'terminal_run_ids': [rid],
            'terminal_refs': [{'run_id': rid, **c.ref(attempt / 'terminal.json')}], 'unlaunched_selected_run_ids': [], **extra})
        self.write(batch / 'finalized.json', {'queue_job_id': job, 'run_ids': [rid],
            'official_queue_receipt_sha256': c.ref(batch / 'official-queue-status.json')['sha256'], **extra})
        details = {'terminal_sha256': c.ref(attempt / 'terminal.json')['sha256'], 'queue_job_id': job, **extra}
        if recovery:
            details['revision_id'] = revision
        row = {'id': rid + '-result', 'run_id': rid, 'supersedes_result_id': None,
               'execution_status': 'completed', 'validity': 'valid', 'outcome': 'success',
               'ended_at': raw['ended_at'], 'termination_reason': 'completed', 'metrics': [], 'details': details}
        self.records.append(row)
        return attempt, batch, terminal, row

    def write_canonical(self):
        refs = {}
        canonical = self.base / 'canonical'; canonical.mkdir(exist_ok=True)
        for name, rows in (('results', self.records), ('notes', self.notes)):
            path = canonical / (name + '.jsonl')
            path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
            refs['canonical_' + name + '_source'] = c.ref(path)
        return refs
