"""Queue-only validation of bounded presentation, immutable upstream and actual analysis."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--node', type=Path, required=True)
    parser.add_argument('--analysis-file', type=Path, required=True)
    parser.add_argument('--analysis-provenance', type=Path, required=True)
    parser.add_argument('--analysis-receipt', type=Path, required=True)
    parser.add_argument('--prior-html', type=Path, required=True)
    parser.add_argument('--evaluation-index', type=Path, required=True)
    parser.add_argument('--evaluation-receipt', type=Path, required=True)
    parser.add_argument('--trace-selection', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(EXPERIMENT / 'Runtime Recovery 001'))
    import recovery_runner
    job = recovery_runner.queued_job(expected_script=__file__)
    import build_workspace as builder
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = builder.source_inventory()
    report = {'format': 'investigation007-validation-1', 'queue_job_id': job['id'],
        'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed',
        'sources_before': before, 'checks': [], 'error': None}
    failure = None
    try:
        for label, directory in [('unchanged005', builder.UPSTREAM), ('unchanged006', builder.READER), ('bounded007', HERE)]:
            argv = [sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', 'discover',
                    '-s', str(directory), '-p', 'test_*.py', '-v']
            result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            log = output / (label + '.log')
            log.write_bytes(result.stdout + result.stderr)
            counts = re.findall(rb'Ran (\d+) tests? in', result.stderr)
            count = int(counts[-1]) if counts else None
            report['checks'].append({'label': label, 'argv': argv, 'exit_status': result.returncode,
                                     'test_count': count, 'log': builder.source(log)})
            if result.returncode or not count:
                raise ValueError('Presentation tests failed: ' + label)
        fixture_dir = output / 'cross-language-fixture'
        fixture_dir.mkdir()
        fixture_run = {'run_id': 'synthetic-contract-check', 'manifest': {'architecture': 'fixture'},
            'result': None, 'sampling': {'event_gaps': [
                {'from_event': i, 'to_event': i + 1, 'gap_s': 0.501, 'explanation': 'synthetic metadata size regression'}
                for i in range(8000)]}, 'source_files': [],
            'trace_availability': {'state': 'available'},
            'events': [{'event_id': 1, 'event_type': 'candidate_reply', 'source': 'fixture',
                'sim_time_s': 0, 'wall_elapsed_s': 0, 'sim_tick': 0, 'parent_ids': [],
                'payload': {'events': [{'type': 'model_context_supplied', 'path': 'context.txt',
                    'content': 'lambda λ 🦾 ' * 3000}],
                    'reserved': {'format': 'robot-trace-value-1.0', 'node': ['r', 'ordinary-data']}}}],
            'motion': [{'sim_time_s': 0, 'q': [0], 'tcp': [0, 0, 0]}]}
        fixture_descriptor = builder.trace_package.write_trace(fixture_run, fixture_dir, 0)
        builder.trace_package.verify_trace(fixture_run, fixture_descriptor, fixture_dir)
        (fixture_dir / 'fixture-descriptor.json').write_text(json.dumps(fixture_descriptor), encoding='utf-8')
        env = dict(os.environ, INVESTIGATION007_FIXTURE_DIR=str(fixture_dir))
        result = subprocess.run([str(args.node), '--test', str(HERE / 'test_client.js')],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        log = output / 'client.log'; log.write_bytes(result.stdout + result.stderr)
        report['checks'].append({'label': 'bounded_client', 'exit_status': result.returncode,
                                 'log': builder.source(log)})
        if result.returncode:
            raise ValueError('Bounded client tests failed')
        # Check JavaScript as it will appear in the combined real template.
        fixture = {'records': {key: [] for key in ('architecture', 'revision', 'run', 'result', 'note')},
                   'evidence_runs': [], 'store_sha256': '0' * 64}
        html, _ = builder.render(fixture, output / 'fixture.html')
        scripts = re.findall(r'<script>(.*?)</script>', html, flags=re.S)
        if len(scripts) != 1:
            raise ValueError('Combined client script extraction failed')
        js = output / 'combined-client.js'; js.write_text(scripts[0], encoding='utf-8')
        result = subprocess.run([str(args.node), '--check', str(js)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log = output / 'combined-client-syntax.log'; log.write_bytes(result.stdout + result.stderr)
        report['checks'].append({'label': 'combined_client_syntax', 'exit_status': result.returncode,
                                 'log': builder.source(log)})
        if result.returncode:
            raise ValueError('Combined client JavaScript syntax failed')
        analysis = builder.original.read_analysis(args.analysis_file, output / 'fixture.html')
        canonical = builder.original.load_snapshot(builder.EXPERIMENT / 'Architecture Map', output / 'fixture.html')
        derivatives = builder.original.read_derivatives(args.evaluation_index, args.evaluation_receipt,
            output / 'fixture.html', canonical_files=canonical['file_sha256'], paired_analysis=analysis)
        if len(derivatives['runs']) != 264:
            raise ValueError('Actual derivative reader did not retain all264 planned dispositions')
        bound = builder.original.bind_analysis(analysis, args.analysis_provenance,
            args.analysis_receipt, output / 'fixture.html', derivatives=derivatives)
        if bound['binding']['state'] != 'verified' or analysis['report'] != bound['report']:
            raise ValueError('Actual frozen analysis identity differs')
        report['actual_analysis'] = {'unchanged': True, 'source': builder.source(args.analysis_file),
                                    'receipt': builder.source(args.analysis_receipt)}
        report['actual_derivative_index'] = {'planned_dispositions': len(derivatives['runs']),
            'source': builder.source(args.evaluation_index), 'receipt': builder.source(args.evaluation_receipt),
            'producer_version': 'Engineering Investigation 005', 'rederived': False}
        # Exercise the actual production reader/package path on the FIRST fixed
        # declaration. This is presentation validation, never a policy rerun.
        directories, selection = builder.original.select_traces(args.trace_selection, [])
        if len(directories) != 12 or len(selection['runs']) != 12:
            raise ValueError('Real trace probe requires the original twelve-slot declaration')
        entry, directory = selection['runs'][0], directories[0]
        row = next(item for item in derivatives['runs'] if item['run_id'] == entry['run_id'])
        probe_dir = output / 'first-declared-trace'
        probe_dir.mkdir()
        run = builder.original.read_selected_trace(entry, directory, probe_dir / 'index.html', 2, 5,
            selected_result=row.get('selected_result'), selection_provenance=row.get('selection_provenance'))
        metadata = {key: value for key, value in run.items() if key not in ('events', 'motion')}
        def json_bytes(value):
            return len(json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8'))
        report['real_trace_probe'] = {'run_id': run['run_id'], 'ordinal': 0,
            'selection': builder.source(args.trace_selection), 'observation_hz': 2, 'motion_hz': 5,
            'full_metadata_bytes': json_bytes(metadata),
            'metadata_field_bytes': {key: json_bytes(value) for key, value in metadata.items()},
            'sampling_field_bytes': {key: json_bytes(value) for key, value in metadata.get('sampling', {}).items()},
            'events': len(run['events']), 'motion': len(run['motion']), 'status': 'pending'}
        descriptor = builder.trace_package.write_trace(run, probe_dir, 0)
        verification = builder.trace_package.verify_trace(run, descriptor, probe_dir)
        if (verification.get('state') != 'verified'
                or verification.get('full_metadata_roundtrip_equal') is not True):
            raise ValueError('Real selected trace did not roundtrip')
        (probe_dir / 'descriptor.json').write_text(json.dumps(descriptor), encoding='utf-8')
        report['real_trace_probe'].update({'status': 'verified', 'verification': verification,
            'descriptor_bytes': json_bytes(descriptor), 'package': descriptor['package']})
        del run, metadata
        # Preserve an exact identity for the technically successful but oversized prior build.
        report['retained_oversized006_html'] = builder.source(args.prior_html)
        builder.verify_upstream(); builder.original.verify_upstream()
        after = builder.source_inventory()
        if before != after:
            raise ValueError('Presentation source changed during validation')
        report['sources_after'] = after
        report['status'] = 'completed'
    except Exception as exc:
        failure = exc
        report['error'] = type(exc).__name__ + ': ' + str(exc)
    report['ended_at'] = datetime.now(timezone.utc).isoformat()
    recovery_runner.original.write_once(output / 'validation.json', report)
    print(json.dumps({'status': report['status'], 'checks': report['checks'], 'error': report['error']}))
    if failure:
        raise failure


if __name__ == '__main__':
    main()
