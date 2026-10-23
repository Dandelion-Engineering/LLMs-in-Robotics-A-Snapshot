"""Build an immutable index only from five completed, qualified queue jobs.

No jobs are launched and no missing assessment is invented. All five official
receipts must pass the existing integer-exit0 queue gate before any assessment
file is hashed or opened. The independent admission verifier then checks source
lineage, exact commands and every native, boundary, smoke and pilot requirement.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import prepare_certificate as certificate


def build(snapshot, output, *, native, boundary, smoke, pilot_stock, pilot_home):
    snapshot, output = Path(snapshot), Path(output)
    if output.exists():
        raise FileExistsError(output)
    supplied = [('native', native, None), ('boundary', boundary, None), ('smoke', smoke, None),
                ('pilot', pilot_stock, 'misplaced-stock'), ('pilot', pilot_home, 'blocked-insert-home')]
    verifier = certificate.load_verifier()
    queues = []
    for kind, paths, family in supplied:
        if len(paths) != (5 if kind in ('native', 'boundary') else 6):
            raise ValueError('Wrong number of qualification input paths: ' + kind)
        # Positional paths: manifest, snapshot, queue, assessment, evidence, host.
        binding = certificate.identity(paths[2])
        job = verifier.base.queue_gate(verifier.base.read_json(binding['path']))
        queues.append((binding, job))
    if len({job['id'] for _, job in queues}) != 5:
        raise ValueError('Native, boundary, smoke and two pilots require five distinct official jobs')
    entries = []
    for (kind, paths, family), (queue, _) in zip(supplied, queues):
        manifest, frozen, _, assessment, evidence, *host = map(Path, paths)
        entry = {'manifest': certificate.identity(manifest), 'snapshot': certificate.identity(frozen),
                 'queue': queue, 'assessment': certificate.identity(assessment),
                 'evidence': str(evidence.resolve())}
        if kind == 'native':
            entry['assessor'] = certificate.identity(certificate.CAMPAIGN / 'qualification/assess_native.py')
        if host:
            entry['host_evidence'] = str(host[0].resolve())
        if family:
            entry['family'] = family
        entries.append(entry)
    frozen = verifier.base.read_json(snapshot)
    problems = verifier.base.frozen_problems(snapshot, frozen, frozen.get('revision'))
    if problems:
        raise ValueError('Final source snapshot/archive integrity failed: ' + str(problems))
    created = datetime.now(timezone.utc).isoformat()
    index = {'schema': 'campaign002-qualification-index-1', 'created_at': created,
             'source_revision': frozen['revision'], 'final_source_snapshot': certificate.identity(snapshot),
             'native': entries[0], 'boundary': entries[1], 'smoke': entries[2], 'pilots': entries[3:]}
    artifacts = {name: certificate.identity(certificate.CAMPAIGN / 'assessment' / filename)
                 for name, filename in (('base_assessor', 'assess.py'), ('smoke_assessor', 'assess_smoke_v2.py'))}
    verifier.verify_qualification_index(index, frozen, verifier.stamp(created), artifacts)
    output.parent.mkdir(parents=True, exist_ok=True)
    certificate.save(output, (json.dumps(index, indent=2, allow_nan=False) + '\n').encode('utf-8'))
    return {'qualified': True, 'qualification_index': certificate.identity(output),
            'source_revision': frozen['revision'], 'official_job_ids': [job['id'] for _, job in queues]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True, help='Final current source snapshot')
    parser.add_argument('--output', type=Path, required=True)
    labels = ('MANIFEST', 'SNAPSHOT', 'QUEUE', 'ASSESSMENT', 'EVIDENCE')
    for name in ('native', 'boundary'):
        parser.add_argument('--' + name, nargs=5, type=Path, metavar=labels, required=True)
    for name in ('smoke', 'pilot-stock', 'pilot-home'):
        parser.add_argument('--' + name, nargs=6, type=Path, metavar=labels + ('HOST_EVIDENCE',), required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.snapshot, args.output, native=args.native, boundary=args.boundary,
                           smoke=args.smoke, pilot_stock=args.pilot_stock, pilot_home=args.pilot_home)))


if __name__ == '__main__':
    main()
