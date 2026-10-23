"""One declared long-host diagnostic: no model and no recovery commands."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def prepare(args):
    spec = importlib.util.spec_from_file_location('probe_challenges', RCI / 'host/challenges.py')
    challenges = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(challenges)
    value = challenges.make_manifest('blocked-insert-home', 'serve', args.run_id)
    value.update(framework_revision=args.revision, noise_seed=24201, sim_cap_s=args.sim_cap_s,
                 wall_cap_s={240: 300, 720: 840, 900: 1100}[args.sim_cap_s], storage_cap_bytes=536870912, model_turns_max=0,
                 qualification_stage='campaign002-host-probe-qualification',
                 diagnostic_purpose=args.purpose,
                 runtime_workspace=str(Path(os.environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/qualification' / args.run_id))
    sources = (list((CAMPAIGN / 'harness').glob('*.py'))
               + list((CAMPAIGN / 'assessment').glob('*.py'))
               + list((RCI / 'readiness-session-10/assessment').glob('*.py'))
               + [Path(__file__), HERE / 'assess_host_probe.py'])
    if args.purpose == 'continuous-physics-during-durable-io':
        spec = importlib.util.spec_from_file_location('host_quiescence_inventory', HERE / 'prepare_model_v15.py')
        extra = importlib.util.module_from_spec(spec); spec.loader.exec_module(extra)
        sources.extend(REPO / name for name in extra.cleanup_inputs())
        sources.append(CAMPAIGN / 'io-repair/DESIGN.md')
        sources.append(CAMPAIGN / 'io-repair/READ_EVIDENCE_V2.md')
        sources.append(CAMPAIGN / 'io-repair/TRANSPORT_EVIDENCE_V2.md')
        sources.append(CAMPAIGN / 'io-repair/PROCESS_SEQUENCE_EVIDENCE_V1.md')
        sources.append(CAMPAIGN / 'io-repair/CONVENTIONAL_ADMISSION_ORDER_V1.md')
        sources.append(CAMPAIGN / 'io-repair/RAW_TOOL_RESULT_EVIDENCE_V1.md')
        evidence = CAMPAIGN / 'io-repair/native-output-source-002'
        if not evidence.is_dir() or not list(evidence.glob('*.rs')):
            raise ValueError('Raw tool-result format evidence is missing')
        sources.extend(path for path in evidence.iterdir() if path.is_file())
        sources.append(RCI / 'isolation-session-9/native/app-server-schema/v2/RawResponseItemCompletedNotification.json')
        sources.extend(CAMPAIGN / name for name in (
            'io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md',
            'io-repair/CHANNEL_TRANSPORT_V3_QUALIFICATION_001.md',
            'io-repair/CHANNEL_TRANSPORT_STARTUP_REPAIR_V1.md',
            'io-repair/CHANNEL_PROBE_PROCESS_IDENTITY_V1.md',
            'io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
            'io-repair/CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md',
              'io-repair/CHANNEL_OWNER_DRAIN_V1.md'))
        channels = CAMPAIGN / 'io-repair/codehost-channel-source-001'
        if not channels.is_dir() or not list(channels.glob('*.rs')):
            raise ValueError('Native channel source evidence is missing')
        sources.extend(path for path in channels.iterdir() if path.is_file())
        sources.extend(HERE / name for name in (
            'prepare_native.py', 'test_prepare_native.py',
            'prepare_model_v6.py', 'test_prepare_model_v6.py',
            'prepare_model_v7.py', 'test_prepare_model_v7.py',
            'prepare_model_v8.py', 'test_prepare_model_v8.py',
            'prepare_model_v9.py', 'test_prepare_model_v9.py',
            'prepare_model_v10.py', 'test_prepare_model_v10.py',
            'prepare_model_v11.py', 'test_prepare_model_v11.py',
            'boundary_suite_v3.py', 'test_boundary_suite_v3.py',
            'prepare_boundary_v3.py', 'test_prepare_boundary_v3.py'))
        value['infrastructure_revision'] = 'single-owner-continuous-physics-with-synchronous-supervisory-durability-1'
    value['runtime_input_files'] = [path.relative_to(REPO).as_posix() for path in sorted(sources)]
    value['scope'] = (f'Fixed {args.sim_cap_s} simulation-second idle serve-mode diagnostic: {args.purpose}. '
                      'No model, operator recovery, task score or substitution for final qualification.')
    challenges.validate_manifest(value)
    save(args.manifest, value)
    print(json.dumps({'run_id': args.run_id, 'model_calls': 0, 'sim_cap_s': args.sim_cap_s}))


def run(args):
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    if (manifest.get('qualification_stage') != 'campaign002-host-probe-qualification'
            or manifest.get('model_turns_max') != 0 or manifest.get('mode') != 'serve'
            or (manifest.get('sim_cap_s'), manifest.get('wall_cap_s')) not in ((240, 300), (720, 840), (900, 1100))):
        raise ValueError('Only the declared bounded no-model diagnostic is allowed')
    workspace = Path(manifest['runtime_workspace'])
    if workspace.exists():
        raise ValueError('Existing diagnostic workspace; never resubmit')
    free_before = shutil.disk_usage(REPO).free
    if free_before < 102_000_000_000:
        raise RuntimeError('Free reserve threatened')
    args.output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-X', 'utf8', '-B', str(CAMPAIGN / 'harness/run_host.py'),
               '--manifest', str(args.manifest.resolve()), '--evidence', str(args.output / 'host'),
               '--runtime-workspace', str(workspace)]
    start = time.time()
    with (args.output / 'stdout.txt').open('x', encoding='utf-8') as out, (args.output / 'stderr.txt').open('x', encoding='utf-8') as err:
        result = subprocess.run(command, cwd=REPO, stdout=out, stderr=err, timeout=manifest['wall_cap_s'] + 60,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    save(args.output / 'execution.json', {'schema': 'campaign002-host-probe-execution-1',
         'run_id': manifest['run_id'], 'argv': command, 'exit_code': result.returncode,
         'started_unix_s': start, 'ended_unix_s': time.time(), 'model_calls': 0,
         'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
         'free_before': free_before, 'free_after': shutil.disk_usage(REPO).free})
    print(json.dumps({'run_id': manifest['run_id'], 'host_exit_code': result.returncode, 'model_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--sim-cap-s', type=int, choices=(240, 720, 900), default=720)
    p.add_argument('--purpose', choices=('long-host-timing', 'garbage-collection-correlation', 'bounded-gc-deferral', 'recorder-stall-localization', 'continuous-physics-during-durable-io'), default='long-host-timing')
    p = sub.add_parser('run')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else run)(args)
