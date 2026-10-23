"""Queue-owned Windows launcher; never submits/polls queue or imports a distro."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wsl_path(path):
    path = Path(path).resolve()
    if len(path.drive) != 2 or path.drive[1] != ':' or path.drive.startswith('\\'):
        raise ValueError('Use a local absolute Windows drive path')
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('build', 'verify', 'test', 'diagnose'))
    parser.add_argument('--distribution', required=True)
    parser.add_argument('--config'); parser.add_argument('--output-dir')
    parser.add_argument('--manifest'); parser.add_argument('--manifest-sha256')
    args = parser.parse_args(argv)
    if os.name != 'nt':
        raise ValueError('Launch through the installed Windows queue')
    sys.path.insert(0, str(EXP/'Runtime'))
    import release_runner
    job = release_runner.queued_job(Path(__file__).resolve())
    sources = {p.name: sha(p) for p in sorted(HERE.glob('*.py'))}
    command = [str(Path(os.environ['SystemRoot'])/'System32'/'wsl.exe'), '--distribution', args.distribution]
    if args.mode == 'verify':
        command += ['--user', 'root']  # Read /root0700 and all static ownership; no mutation.
    command += ['--exec', '/usr/bin/python3', '-I', '-B']
    output = None
    if args.mode in ('build', 'diagnose'):
        if not args.config or not args.output_dir:
            raise ValueError('Build needs --config and --output-dir')
        output = Path(args.output_dir).resolve()
        if output.exists() or not output.parent.is_dir():
            raise ValueError('Output must be fresh with an existing parent')
        config_sha = sha(args.config)
        config = json.loads(Path(args.config).read_text(encoding='utf8'))
        if config.get('source_distribution') != args.distribution:
            raise ValueError('Build distribution differs from explicit source config')
        command += [wsl_path(HERE/'userland.py'), args.mode, '--config', wsl_path(args.config),
                    '--output', wsl_path(output), '--queue-job-id', job['id']]
        timeout = 900
    elif args.mode == 'verify':
        if not args.manifest or not args.manifest_sha256:
            raise ValueError('Verify needs --manifest and --manifest-sha256')
        command += [wsl_path(HERE/'userland.py'), 'verify', '--manifest', wsl_path(args.manifest),
                    '--manifest-sha256', args.manifest_sha256, '--seconds', '25']
        timeout = 30
    else:
        command += [wsl_path(HERE/'test_userland.py')]
        timeout = 180
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            shell=False, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    after = {p.name: sha(p) for p in sorted(HERE.glob('*.py'))}
    unchanged = after == sources and (args.mode not in ('build', 'diagnose') or config_sha == sha(args.config))
    record = {'schema_version': 'userland-tool-invocation-1', 'queue_job_id': job['id'],
              'mode': args.mode, 'distribution': args.distribution, 'argv': command,
              'source_files_before': sources, 'source_files_after': after, 'sources_unchanged': unchanged,
              'returncode': result.returncode, 'stdout': result.stdout.decode('utf8', 'replace'),
              'stderr': result.stderr.decode('utf8', 'replace'), 'official_queue_completion_verified': False}
    if output is not None and output.is_dir():
        with (output/'host-invocation.json').open('x', encoding='utf8') as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
    print(json.dumps(record, sort_keys=True))
    return 0 if result.returncode == 0 and unchanged else 1


if __name__ == '__main__':
    raise SystemExit(main())
