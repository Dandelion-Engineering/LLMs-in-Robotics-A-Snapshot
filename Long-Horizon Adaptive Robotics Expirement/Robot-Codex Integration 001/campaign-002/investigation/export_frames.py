"""Queued post-campaign export of byte-identical recorded PNGs; never renders physics.

Run only after all Campaign 002 slots settle. The qualified recorder.Reader
verifies each finalized container and original paired-image hashes. No source or
retained recording is modified, and missing images are never recreated.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

import build as report

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
EXPERIMENT = CAMPAIGN.parent.parent
REPO = EXPERIMENT.parent
READER_PATH = EXPERIMENT / 'Storage Retention Implementation 001/future/recorder.py'
SNAPSHOT = None


def sha(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def artifact(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path), 'bytes': Path(path).stat().st_size}


def reader_module():
    if SNAPSHOT is None:raise ValueError('Explicit Campaign002 frozen snapshot is required')
    frozen = read(SNAPSHOT)
    expected = frozen['sources'][READER_PATH.relative_to(REPO).as_posix()]['sha256']
    if sha(READER_PATH) != expected:
        raise ValueError('Qualified recorder reader changed; refuse decoding')
    spec = importlib.util.spec_from_file_location('campaign002_recorded_frame_reader', READER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def even_selection(rows, maximum):
    if len(rows) <= maximum:
        return rows
    if maximum == 1:
        return [rows[0]]
    return [rows[(i * (len(rows) - 1)) // (maximum - 1)] for i in range(maximum)]


def publications(history):
    """Exact capture-time join; the recorded publication clock stays separate."""
    origin = next(row['wall_unix_s'] for _, row in history if row.get('type') == 'episode_started')
    result = {}
    for line, row in history:
        capture = row.get('payload', {}).get('capture_sim_time_s')
        if row.get('type') != 'observation' or not report.number(capture):
            continue
        if capture not in result:
            result[capture] = {'event_id': row['event_id'], 'physical_line': line,
                'wall_unix_s': row.get('wall_unix_s'), 'sim_time_s': row.get('sim_time_s'),
                'observation_sequence': row['payload'].get('sequence'),
                't': row['wall_unix_s'] - origin if report.number(row.get('wall_unix_s')) else None}
    return result


def export(plan_path, maximum=32, byte_cap=128_000_000, build_report=False, snapshot=None, qualification_index=None):
    global SNAPSHOT
    SNAPSHOT=Path(snapshot).resolve() if snapshot is not None else None
    if type(maximum) is not int or not 1 <= maximum <= 32:
        raise ValueError('At most 32 original frames per selected run are authorized')
    if type(byte_cap) is not int or not 0 < byte_cap <= 128_000_000:
        raise ValueError('Aggregate image export cap must be at most 128MB')
    plan = read(plan_path)
    report.validate_plan(plan)
    report.require_settled(plan,plan_path.parent/'execution')
    rows = [report.run_record(a, plan_path.parent / 'execution', HERE) for a in plan['attempts']]
    report.select_examples(rows)
    selected = {row['run_id']: row for row in rows if row['examples']}
    output = HERE / 'frames'
    output.mkdir(exist_ok=True)
    physical_bytes = sum(p.stat().st_size for p in output.rglob('*.png'))
    if physical_bytes > byte_cap:
        raise ValueError('Existing frame export already exceeds cap; no deletion authorized')
    decoder = reader_module()
    exports = []
    for attempt in plan['attempts']:
        rid = attempt['run_id']
        if rid not in selected:
            continue
        row = selected[rid]
        item = {'run_id': rid, 'selection_reasons': row['examples'], 'frames': [],
            'status': 'unavailable', 'reason': 'No completed authenticated assessed attempt',
            'maximum_exported': maximum, 'original_images_modified': False}
        exports.append(item)
        if row.get('queue_verified') is not True or not row.get('scientific_admission'):
            continue
        folder = plan_path.parent / 'execution' / rid
        receipt_path, assessment_path = folder / 'storage/queue-receipt.json', folder / 'assessment.json'
        if not receipt_path.is_file():receipt_path=folder/'official-status.json'
        receipt = read(receipt_path)
        job = receipt.get('job', receipt)
        if job.get('state') != 'succeeded' or type(job.get('exit_status')) is not int or job['exit_status'] != 0:
            raise ValueError('Official queue changed after gate')
        assessment = read(assessment_path)
        item.update(queue_receipt=artifact(receipt_path), assessment=artifact(assessment_path),
                    diagnostic_only=assessment['validity'] != 'valid')
        inventory = {(entry['root'], entry['path']): entry for entry in assessment['evidence_inventory']}
        host = Path(attempt['host_evidence'])
        recording = host / 'native-recording'
        manifest_path, database_path = recording / 'container-manifest.json', recording / 'evidence.sqlite.gz'
        try:
            for path in (manifest_path, database_path):
                key = ('protected_host', path.relative_to(host).as_posix())
                entry = inventory.get(key)
                if entry is None or not path.is_file() or path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
                    raise ValueError('Native recording differs from admitted inventory: ' + path.name)
            item['container_manifest'], item['container'] = artifact(manifest_path), artifact(database_path)
            history_path = host / 'public-history.jsonl'
            history = report.trace(history_path, 'protected_host:public-history.jsonl', inventory, HERE)
            published = publications(history)
            item['publication_history'] = artifact(history_path)
            reader = decoder.Reader(recording)
            try:
                if reader.meta.get('run_id') != rid:
                    raise ValueError('Native recording run identity differs from registered attempt')
                all_images = list(reader.images())
                available = [image for image in all_images if image['status'] == 'available']
                chosen = even_selection(available, maximum)
                item.update(status='available' if chosen else 'unavailable_by_policy',
                    reason='Original retained images selected uniformly over available frame index, including first/last.' if chosen else 'No available original RGB pairs in retained recorder.',
                    capture_count=len(all_images), available_count=len(available),
                    availability_counts=dict(Counter(image['status'] for image in all_images)),
                    availability_reason_counts=dict(Counter(image['reason'] for image in all_images)),
                    first_capture_sim_s=all_images[0]['capture_time_s'] if all_images else None,
                    last_capture_sim_s=all_images[-1]['capture_time_s'] if all_images else None,
                    last_available_capture_sim_s=available[-1]['capture_time_s'] if available else None,
                    image_policy=reader.meta.get('image_policy', reader.meta.get('policy')),
                    omitted_by_display_selection=len(available) - len(chosen), omitted_by_export_budget=0)
                target = output / rid
                target.mkdir(exist_ok=True)
                for image in chosen:
                    original = reader.image(image['id'])
                    if original['status'] != 'available':
                        raise ValueError('Selected available frame changed availability')
                    png = original['rgb']
                    if png[:8] != b'\x89PNG\r\n\x1a\n' or report.digest(png) != image['rgb_sha256']:
                        raise ValueError('Original retained RGB is not the expected exact PNG')
                    width, height = struct.unpack('!II', png[16:24])
                    name = image['id'].replace(':', '-') + '.png'
                    if Path(name).name != name or any(c in name for c in ('/', '\\')):
                        raise ValueError('Unsafe frame identity')
                    destination = target / name
                    additional = 0 if destination.is_file() else len(png)
                    if physical_bytes + additional > byte_cap:
                        item['omitted_by_export_budget'] += 1
                        continue
                    if destination.exists():
                        if destination.read_bytes() != png:
                            raise ValueError('Existing export differs; cannot overwrite original pixels')
                    else:
                        with destination.open('xb') as stream:
                            stream.write(png)
                        physical_bytes += len(png)
                    pub = published.get(image['capture_time_s'])
                    frame = {**image, 'rgb_path': str(destination.resolve()), 'rgb_bytes': len(png),
                        'width': width, 'height': height, 'publication': pub,
                        'capture_wall_time': None,
                        'capture_wall_time_reason': 'Native image metadata records capture simulation time; no capture wall time is inferred.',
                        'publication_match': 'Exact capture_sim_time_s join to first protected public observation' if pub else 'No exact public observation join; synchronization unavailable',
                        'capture_to_publication_sim_s': pub['sim_time_s'] - image['capture_time_s'] if pub and report.number(pub.get('sim_time_s')) else None}
                    item['frames'].append(frame)
                item['exported_count'] = len(item['frames'])
            finally:
                reader.close()
        except (ValueError, OSError, KeyError, decoder.RecordingFailure) as error:
            item.update(status='unavailable_integrity_or_format', reason=str(error), frames=[], exported_count=0)
    index = {'schema': 'campaign002-original-frame-export-1', 'created_at': datetime.now(timezone.utc).isoformat(),
        'campaign_id': plan['campaign_id'], 'plan': artifact(plan_path), 'exporter': artifact(Path(__file__)),
        'reader': artifact(READER_PATH), 'snapshot': artifact(SNAPSHOT), 'runs': exports,
        'aggregate_existing_png_bytes': physical_bytes, 'maximum_png_bytes': byte_cap,
        'maximum_frames_per_selected_run': maximum,
        'pixels': 'Byte-identical original PNGs from recorder.Reader.image(); no resizing, recoloring, simulation, reconstruction or re-encoding.',
        'coverage': 'Sparse original retention and display selection are distinct. Unavailable-by-policy and quota-exhausted captures are not restored. '
                    'Nearest previously published frame can be stale; publication age and capture simulation time remain visible.'}
    (output / 'index.json').write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')
    if build_report:
        report.build(plan_path, HERE, qualification_index)
    return {'index': str(output / 'index.json'), 'png_bytes': physical_bytes,
            'selected_runs': len(exports), 'exported_frames': sum(len(x['frames']) for x in exports),
            'omissions': {x['run_id']: x['reason'] for x in exports if x['status'] != 'available'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=CAMPAIGN / 'execution-plan.json')
    parser.add_argument('--max-per-run', type=int, default=32)
    parser.add_argument('--max-total-bytes', type=int, default=128_000_000)
    parser.add_argument('--build-report', action='store_true')
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--qualification-index',type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.plan.resolve(), args.max_per_run, args.max_total_bytes, args.build_report,
                            args.snapshot,args.qualification_index), indent=2))
