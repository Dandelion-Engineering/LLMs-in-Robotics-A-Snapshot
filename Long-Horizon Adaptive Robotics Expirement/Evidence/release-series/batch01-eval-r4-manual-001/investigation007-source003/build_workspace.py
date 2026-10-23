"""Build a bounded lazy presentation; preserve original 005 evidence and analysis."""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
UPSTREAM = EXPERIMENT / 'Engineering Investigation 005'
READER = EXPERIMENT / 'Engineering Investigation 006'
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
MAX_HTML_BYTES = 16 * 1024 * 1024


def source(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return {'path': str(path), 'sha256': h.hexdigest(), 'bytes': path.stat().st_size}


def verify_upstream():
    binding = HERE / 'upstream-source-bindings.json'
    record = json.loads(binding.read_text(encoding='utf-8'))
    for ref in record['reader006_files'] + [record['original005_binding']]:
        if source(ref['path']) != ref:
            raise ValueError('Frozen presentation source changed: ' + ref['path'])
    return source(binding)


verify_upstream()
_spec = importlib.util.spec_from_file_location('investigation007_upstream006', READER / 'build_workspace.py')
original = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(original)
# Original005 process_development imports this name from the active entrypoint.
# Re-export the unchanged map loader; keep all producer implementation paths005.
load_map_module = original.load_map_module
sys.path.insert(0, str(HERE))
import trace_package


def source_inventory():
    return [source(p) for p in sorted(HERE.iterdir()) if p.is_file()]


def render(snapshot, output):
    raw_size = len(original.safe_json(snapshot).encode('utf-8'))
    if raw_size > MAX_SNAPSHOT_BYTES:
        raise ValueError('Compact snapshot exceeds fixed 32 MiB presentation limit')
    template = (HERE / 'workspace.html').read_text(encoding='utf-8')
    for marker, path in (
        ('/*__PLAYBACK_STYLE__*/', UPSTREAM / 'playback.css'),
        ('/*__ANALYSIS_STYLE__*/', UPSTREAM / 'analysis.css'),
        ('/*__LAZY_CODE__*/', HERE / 'lazy_data.js'),
        ('/*__PLAYBACK_CODE__*/', HERE / 'playback.js'),
        ('/*__ANALYSIS_CODE__*/', HERE / 'analysis.js')):
        if template.count(marker) != 1:
            raise ValueError('Expected one template marker: ' + marker)
        template = template.replace(marker, path.read_text(encoding='utf-8'))
    for relative in ('README.md', 'Architecture Map/README.md',
                     'Long-Horizon Adaptive Robotics Experiment Design/Contract.md'):
        old = '../' + quote(relative, safe='/.')
        new = quote(Path(os.path.relpath(EXPERIMENT / relative, output.parent)).as_posix(), safe='/.')
        template = template.replace('href="' + old + '"', 'href="' + new + '"')
    if template.count('__MAP_SNAPSHOT__') != 1:
        raise ValueError('Expected one snapshot marker')
    packed = original.pack_snapshot(snapshot)
    html = template.replace('__MAP_SNAPSHOT__', original.safe_json(packed))
    if len(html.encode('utf-8')) > MAX_HTML_BYTES:
        raise ValueError('HTML exceeds fixed 16 MiB presentation limit')
    return html, {k: v for k, v in packed.items() if k != 'data'}


def build(args):
    output = args.output.resolve()
    # Never overwrite previous builds or publish an incomplete shell.
    output.parent.mkdir(parents=True, exist_ok=False)
    before = source_inventory()
    verify_upstream()
    original.verify_upstream()
    snapshot = original.load_snapshot(args.map_root.resolve(), output)
    snapshot['presentation_implementation'] = {
        'version': 'Engineering Investigation 007',
        'scope': 'Bounded lazy lossless presentation only; original 005 evidence sampling and Analysis005 estimates remain unchanged.',
        'producer_version': 'Engineering Investigation 005',
        'analysis_version': 'Release Analysis 005',
        'annex_reader_version': 'Engineering Investigation 006',
        'sources': before,
        'limits': {'html_bytes': MAX_HTML_BYTES, 'decoded_snapshot_bytes': MAX_SNAPSHOT_BYTES,
                   'trace_manifest_bytes': 16 * 1024 * 1024, 'json_node_bytes': 1024 * 1024,
                   'text_chunk_bytes': 64 * 1024, 'resident_traces': 1},
        'limits_basis': 'Engineering allocation controls, not an empirically proven browser optimum.'}
    snapshot['implementation_narrative'] = original.read_implementation_narrative(
        args.implementation_narrative, snapshot['records'], args.map_root)
    directories, selection = original.select_traces(args.trace_selection, [])
    snapshot['paired_analysis'] = original.read_analysis(args.analysis_file, output)
    snapshot['run_metadata'] = original.read_run_metadata(args.metadata_root, output)
    snapshot['evaluation_derivatives'] = original.read_derivatives(args.evaluation_index,
        args.evaluation_receipt, output, canonical_files=snapshot['file_sha256'],
        paired_analysis=snapshot['paired_analysis'])
    snapshot['paired_analysis'] = original.bind_analysis(snapshot['paired_analysis'],
        args.analysis_provenance, args.analysis_receipt, output,
        derivatives=snapshot['evaluation_derivatives'])
    snapshot['trace_selection'] = selection
    selected = {row['run_id']: row for row in snapshot['evaluation_derivatives'].get('runs', [])}
    descriptors, trace_checks = [], []
    for ordinal, (entry, path) in enumerate(zip(selection['runs'], directories)):
        row = selected.get(entry['run_id'], {})
        run = original.read_selected_trace(entry, path, output, args.observation_hz, args.motion_hz,
            selected_result=row.get('selected_result'), selection_provenance=row.get('selection_provenance'))
        descriptor = trace_package.write_trace(run, output.parent, ordinal)
        verification = trace_package.verify_trace(run, descriptor, output.parent)
        if not isinstance(verification, dict) or verification.get('state') != 'verified':
            raise ValueError('Trace roundtrip verification failed')
        descriptors.append(descriptor)
        trace_checks.append({'ordinal': ordinal, 'run_id': run['run_id'],
            'events': len(run.get('events', [])), 'motion': len(run.get('motion', [])),
            'lossless_roundtrip_equal': True, 'package': descriptor['package']})
        print(json.dumps({'packaged_trace': run['run_id'], 'ordinal': ordinal,
                          'events': len(run.get('events', [])), 'motion': len(run.get('motion', []))}), flush=True)
        del run
        gc.collect()
    if [d['run_id'] for d in descriptors] != [e['run_id'] for e in selection['runs']]:
        raise ValueError('Trace identity/order differs from fixed declaration')
    snapshot['evidence_runs'] = descriptors
    # Snapshot remains a compact index; no trace event payload is embedded.
    package = {'format': 'robot-investigation-package-007',
        'built_at': datetime.now(timezone.utc).isoformat(),
        'presentation_implementation': snapshot['presentation_implementation'],
        'trace_selection': selection, 'trace_checks': trace_checks,
        'store_sha256': snapshot['store_sha256'], 'canonical_file_sha256': snapshot['file_sha256'],
        'metadata_runs': len(snapshot['run_metadata']['runs']),
        'derivative_runs': len(snapshot['evaluation_derivatives']['runs']),
        'analysis_report': source(args.analysis_file),
        'analysis_receipt': source(args.analysis_receipt),
        'derivation_receipt': source(args.evaluation_receipt)}
    manifest = output.parent / 'package-manifest.json'
    with manifest.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(package, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
    manifest_ref = source(manifest)
    snapshot['presentation_package'] = {**manifest_ref, 'href': manifest.name}
    html, archive = render(snapshot, output)
    verify_upstream()
    original.verify_upstream()
    if source_inventory() != before:
        raise ValueError('Presentation source changed during build')
    # Read canonical files again, refusing a changed store after processing.
    final_map = original.load_snapshot(args.map_root.resolve(), output)
    if final_map['file_sha256'] != snapshot['file_sha256']:
        raise ValueError('Canonical source changed during packaging')
    # These original readers verify exact bound analysis/evidence inputs again.
    original.bind_analysis(snapshot['paired_analysis'], args.analysis_provenance,
        args.analysis_receipt, output, derivatives=snapshot['evaluation_derivatives'])
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(html)
    result = {'format': 'investigation007-build-result-1', 'status': 'completed',
        'output': source(output), 'package_manifest': manifest_ref, 'snapshot_archive': archive,
        'trace_count': len(descriptors), 'trace_roundtrips_equal': True,
        'metadata_runs': package['metadata_runs'], 'derivative_runs': package['derivative_runs'],
        'source_inventory_before': before, 'source_inventory_after': source_inventory(),
        'browser_verification': 'pending'}
    with (output.parent / 'build-result.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-root', type=Path, default=EXPERIMENT / 'Architecture Map')
    parser.add_argument('--output', type=Path, required=True)
    for flag in ('metadata-root', 'trace-selection', 'evaluation-index', 'evaluation-receipt',
                 'analysis-file', 'analysis-provenance', 'analysis-receipt', 'implementation-narrative'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--observation-hz', type=float, default=2.0)
    parser.add_argument('--motion-hz', type=float, default=5.0)
    args = parser.parse_args()
    if args.observation_hz != 2 or args.motion_hz != 5:
        raise ValueError('This presentation preserves the fixed 2 Hz / 5 Hz selection')
    sys.path.insert(0, str(EXPERIMENT / 'Runtime Recovery 001'))
    import recovery_runner
    recovery_runner.queued_job(expected_script=__file__)
    print(json.dumps(build(args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
