"""Verify the complete installed userland plus explicit WSL integration identity.

Windows entry point requires its own queued job. Linux modes are bounded,
read-only probes for that wrapper or the separately queued artifact freezer.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2]
USERLAND = HERE.parent/'userland-tools'/'userland.py'


def ref(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': checksum, 'bytes': path.stat().st_size}


def write(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def load_bound(args):
    raw = Path(args.manifest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.manifest_sha256:
        raise ValueError('Installed manifest SHA mismatch')
    manifest = json.loads(raw)
    spec = importlib.util.spec_from_file_location('held_userland_verify', USERLAND)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    integration = manifest.get('installed_integration')
    if (manifest.get('schema_version') != module.SCHEMA or manifest.get('status') != 'complete'
            or manifest.get('inputs_unchanged') is not True or manifest.get('scopes') != module.SCOPES
            or module.sha(module.canonical(manifest['entries'])) != manifest['tree_sha256']
            or not isinstance(integration, dict) or not isinstance(integration.get('init'), dict)
            or not isinstance(integration.get('uname'), list) or len(integration['uname']) != 5
            or not isinstance(integration.get('base_manifest'), dict)):
        raise ValueError('Incomplete installed tree/integration manifest')
    return module, manifest, raw


def linux_verify(args):
    started = time.monotonic(); deadline = started+25
    if os.name != 'posix':
        raise ValueError('Linux probe required')
    module, manifest, raw = load_bound(args)
    if args.linux_identity:
        import pwd
        account = pwd.getpwuid(os.getuid()); config = manifest['config']
        identity = {'username': account.pw_name, 'uid': os.getuid(), 'gid': os.getgid(),
                    'home': account.pw_dir, 'shell': account.pw_shell}
        if (identity != {'username': config['username'], 'uid': config['uid'], 'gid': config['gid'],
                         'home': '/home/'+config['username'], 'shell': config['shell']}):
            raise ValueError('Actual default candidate account differs from fixed configuration')
        files = {}
        for role, name in [('python', '/usr/bin/python3'), ('bubblewrap', '/usr/bin/bwrap'),
                           ('seccomp', '/usr/lib/x86_64-linux-gnu/libseccomp.so.2')]:
            actual_path = Path(name).resolve(strict=True)
            expected_path = module.resolve_image_link(name, manifest['entries'])
            actual = module.describe(actual_path, deadline)
            if str(actual_path) != expected_path or actual != manifest['entries'].get(expected_path):
                raise ValueError('Candidate native identity differs: ' + role)
            files[role] = {'path': expected_path, 'identity': actual}
        if str(Path(sys.executable).resolve(strict=True)) != files['python']['path']:
            raise ValueError('Probe is not running the pinned candidate Python')
        # Confirm the unchanged worker's default libseccomp load resolves inside
        # the exact tree; /proc maps expose the actual loaded native file.
        seccomp = ctypes.CDLL('libseccomp.so.2')
        loaded = {line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                  if 'libseccomp.so' in line}
        if loaded != {files['seccomp']['path']}:
            raise ValueError('Default seccomp loader resolves an unexpected backing file')
        remaining = deadline-time.monotonic()
        module.check_time(deadline)
        version = subprocess.run(['/usr/bin/bwrap', '--version'], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=min(5, remaining), check=False)
        if version.returncode != 0:
            raise ValueError('Pinned bubblewrap version probe failed')
        result = {'schema_version': 'installed-candidate-native-identity-1', 'verified': True,
                  'account': identity, 'python_version': sys.version, 'native_files': files,
                  'bubblewrap_version': version.stdout.decode('utf8'),
                  'seccomp_loaded_path': files['seccomp']['path']}
    else:
        if os.getuid() != 0:
            raise ValueError('Read-only full static verification requires project-distro root')
        remaining = deadline-time.monotonic(); module.check_time(deadline)
        tree = module.verify('/', args.manifest, args.manifest_sha256, seconds=remaining)
        init = module.describe(Path('/init'), deadline); uname = list(os.uname())
        if init != manifest['installed_integration']['init']:
            raise ValueError('WSL /init differs from explicitly accepted integration identity')
        if uname != manifest['installed_integration']['uname']:
            raise ValueError('WSL kernel identity differs from installed manifest')
        result = {'schema_version': 'installed-candidate-userland-verification-1', 'verified': True,
                  'tree_sha256': tree['tree_sha256'], 'init': init, 'uname': uname}
    if Path(args.manifest).read_bytes() != raw:
        raise ValueError('Installed manifest changed during probe')
    module.check_time(deadline)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


def wsl_path(path):
    path = Path(path).resolve()
    if len(path.drive) != 2 or path.drive[1] != ':':
        raise ValueError('Require a local Windows drive path')
    return '/mnt/'+path.drive[0].lower()+path.as_posix()[2:]


def windows_verify(args):
    sys.path.insert(0, str(EXP/'Runtime'))
    import release_runner
    job = release_runner.queued_job(Path(__file__).resolve())
    manifest_path = Path(args.manifest).resolve()
    if ref(manifest_path)['sha256'] != args.manifest_sha256:
        raise ValueError('Installed manifest differs before launch')
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['config']['target_distribution'] != args.distribution:
        raise ValueError('Distro differs from fixed project configuration')
    output = Path(args.output_dir).resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Use a fresh verification output with existing parent')
    paths = (Path(__file__), USERLAND, manifest_path)
    before = {str(path.resolve()): ref(path) for path in paths}
    output.mkdir(); write(output/'started.json', {'queue_job_id': job['id'], 'inputs_before': before,
                                                  'distribution': args.distribution})
    base = [str(Path(os.environ['SystemRoot'])/'System32'/'wsl.exe'), '--distribution', args.distribution]
    replies = {}
    for mode in ('identity', 'probe'):
        argv = base + (['--user', 'root'] if mode == 'probe' else []) + ['--exec', '/usr/bin/python3', '-I', '-B',
            wsl_path(__file__), '--linux-'+mode, '--manifest', wsl_path(manifest_path),
            '--manifest-sha256', args.manifest_sha256]
        reply = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        observation = {'argv': argv, 'returncode': reply.returncode,
            'stdout': reply.stdout.decode('utf8', 'replace'), 'stderr': reply.stderr.decode('utf8', 'replace')}
        if reply.returncode == 0:
            try: observation['value'] = json.loads(reply.stdout)
            except ValueError: observation['parse_failed'] = True
        replies[mode] = observation
        write(output/(mode+'.json'), observation)
    after = {str(path.resolve()): ref(path) for path in paths}
    success = (before == after and all(r['returncode'] == 0 and r.get('value', {}).get('verified') is True for r in replies.values()))
    result = {'schema_version': 'installed-userland-verification-receipt-1',
        'status': 'passed' if success else 'failed', 'queue_job_id': job['id'],
        'distribution': args.distribution, 'manifest': ref(manifest_path),
        'inputs_before': before, 'inputs_after': after, 'inputs_unchanged': before == after,
        'observations': replies, 'official_queue_completion_verified': False,
        'scope': 'Pinned userland/default account/native identities and explicit WSL integration; no timing/isolation readiness claim'}
    write(output/'verification.json', result); print(json.dumps(result, sort_keys=True))
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', default='LLMs-Robotics-Candidate-001')
    parser.add_argument('--manifest', required=True); parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output-dir')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--linux-probe', action='store_true'); modes.add_argument('--linux-identity', action='store_true')
    args = parser.parse_args()
    if args.linux_probe or args.linux_identity:
        return linux_verify(args)
    if os.name != 'nt' or not args.output_dir:
        raise ValueError('Windows queue wrapper requires --output-dir')
    return windows_verify(args)


if __name__ == '__main__': raise SystemExit(main())
