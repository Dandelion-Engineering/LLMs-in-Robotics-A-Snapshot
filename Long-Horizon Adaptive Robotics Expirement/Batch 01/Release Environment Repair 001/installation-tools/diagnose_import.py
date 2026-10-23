"""Queue-owned, read-only imported-userland difference inventory.

No rootfs modifications, accepted overlays, exclusions, imports or queue calls.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2]
USERLAND = HERE.parent/'userland-tools'/'userland.py'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}


def write(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def load_userland():
    spec = importlib.util.spec_from_file_location('held_userland_reader', USERLAND)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def observed_tree(module, deadline):
    scopes = [name for name in module.SCOPES if Path(name).exists() or Path(name).is_symlink()]
    names = module.walk_scope('/', scopes=scopes, deadline=deadline)
    rows = {}
    for index, name in enumerate(sorted(names)):
        module.check_time(deadline)
        info = Path(name).lstat()
        if stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            rows[name] = module.describe(Path(name), deadline)
        else:
            rows[name] = {'type': 'unsupported_special', 'mode': stat.S_IMODE(info.st_mode),
                          'uid': info.st_uid, 'gid': info.st_gid, 'native_mode': info.st_mode}
        if index and index % 2000 == 0:
            print(json.dumps({'progress': 'static_tree', 'paths_described': index, 'total_paths': len(names)}), flush=True)
    return rows


def external_link_observations(rows, module, deadline):
    observations = {}
    for name, row in rows.items():
        if row['type'] != 'symlink':
            continue
        path = Path(name)
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            observations[name] = {'link_target': row['target'], 'resolve_error': type(exc).__name__+': '+str(exc)}
            continue
        target = str(resolved)
        if not any(target == scope or target.startswith(scope+'/') for scope in module.SCOPES):
            value = {'link_target': row['target'], 'resolved_target': target,
                     'target_hashed': False, 'reason': 'outside declared static scopes; no inferred approval'}
            if target == '/init':
                value.update(target_identity=module.describe(resolved, deadline), target_hashed=True)
            observations[name] = value
    return observations


def linux_inspect(args):
    if os.name != 'posix' or os.getuid() != 0:
        raise ValueError('Read-only complete static inventory requires project-distro root')
    module = load_userland(); sources_before = {str(p): ref(p) for p in (Path(__file__), USERLAND)}
    manifest_path = Path(args.manifest); raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.manifest_sha256:
        raise ValueError('Expected exact manifest SHA differs')
    manifest = json.loads(raw)
    if (manifest.get('schema_version') != module.SCHEMA or manifest.get('status') != 'complete'
            or manifest.get('inputs_unchanged') is not True or manifest.get('scopes') != module.SCOPES
            or module.sha(module.canonical(manifest['entries'])) != manifest['tree_sha256']):
        raise ValueError('Incomplete/unsupported original build manifest')
    output = Path(args.output_dir)
    if not output.is_dir() or not (output/'started.json').is_file() or (output/'diagnostic.json').exists():
        raise ValueError('Diagnostic output lacks fresh owning wrapper start')
    deadline = time.monotonic()+600
    print(json.dumps({'progress': 'first_complete_static_inventory'}), flush=True)
    actual = observed_tree(module, deadline)
    links_before = external_link_observations(actual, module, deadline)
    expected = manifest['entries']; extra = sorted(set(actual)-set(expected)); missing = sorted(set(expected)-set(actual))
    changed = {name: {'expected': expected[name], 'actual': actual[name]}
               for name in sorted(set(expected)&set(actual)) if expected[name] != actual[name]}
    forbidden = {name: actual.get(name) for name in manifest['required_absent']
                 if Path(name).exists() or Path(name).is_symlink()}
    print(json.dumps({'progress': 'second_complete_static_inventory', 'extra': len(extra),
                      'missing': len(missing), 'changed': len(changed)}), flush=True)
    after = observed_tree(module, deadline)
    links_after = external_link_observations(after, module, deadline)
    sources_after = {str(p): ref(p) for p in (Path(__file__), USERLAND)}
    unchanged = (actual == after and links_before == links_after and sources_before == sources_after
                 and manifest_path.read_bytes() == raw)
    record = {'schema_version': 'imported-userland-difference-diagnostic-1',
        'status': 'complete' if unchanged else 'failed', 'queue_job_id': args.queue_job_id,
        'manifest': ref(manifest_path), 'expected_tree_sha256': manifest['tree_sha256'],
        'actual_tree_before_sha256': module.sha(module.canonical(actual)),
        'actual_tree_after_sha256': module.sha(module.canonical(after)),
        'counts': {'expected': len(expected), 'actual': len(actual), 'extra': len(extra),
                   'missing': len(missing), 'changed': len(changed)},
        'extra': {name: actual[name] for name in extra}, 'missing': {name: expected[name] for name in missing},
        'changed': changed, 'required_absence_violations': forbidden,
        'external_or_unresolved_links_before': links_before, 'external_or_unresolved_links_after': links_after,
        'source_files_before': sources_before, 'source_files_after': sources_after,
        'inputs_unchanged': unchanged, 'linux_root_inspection_uid': os.getuid(),
        'uname': list(os.uname()), 'python_version': sys.version,
        'python_executable': {'path': sys.executable, 'sha256': module.file_sha(sys.executable, deadline)},
        'accepted_overlay': False, 'original_tree_verification_passed': not (extra or missing or changed or forbidden),
        'limitations': ['Static userland inventory only, not runtime/isolation/timing acceptance',
            'Only observed links resolving exactly to /init cause outside-scope bytes to be hashed',
            'No unknown extra path is excluded or approved by this report']}
    write(output/'tree-before.json', actual); write(output/'tree-after.json', after)
    record['tree_inventory_files'] = {'before': ref(output/'tree-before.json'), 'after': ref(output/'tree-after.json')}
    write(output/'diagnostic.json', record)
    print(json.dumps({'status': record['status'], 'diagnostic': ref(output/'diagnostic.json'),
                      'counts': record['counts'], 'original_tree_verification_passed': record['original_tree_verification_passed']}), flush=True)
    return 0 if unchanged else 1


def wsl_path(path):
    path = Path(path).resolve()
    if len(path.drive) != 2 or path.drive[1] != ':':
        raise ValueError('Use a local Windows drive path')
    return '/mnt/'+path.drive[0].lower()+path.as_posix()[2:]


def windows_run(args):
    sys.path.insert(0, str(EXP/'Runtime'))
    import release_runner
    job = release_runner.queued_job(Path(__file__).resolve())
    manifest = Path(args.manifest).resolve()
    if digest(manifest) != args.manifest_sha256:
        raise ValueError('Manifest SHA differs before WSL launch')
    value = json.loads(manifest.read_bytes())
    if value['config']['target_distribution'] != args.distribution:
        raise ValueError('Explicit target distro differs from build config')
    output = Path(args.output_dir).resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Require fresh diagnostic directory with existing parent')
    inputs_before = {str(p): ref(p) for p in (Path(__file__), USERLAND, manifest)}
    output.mkdir(); write(output/'started.json', {'queue_job_id': job['id'], 'purpose': 'read-only imported tree differences',
        'distribution': args.distribution, 'inputs_before': inputs_before})
    base = [str(Path(os.environ['SystemRoot'])/'System32'/'wsl.exe'), '--distribution', args.distribution]
    identity_code = "import json,os,pwd; p=pwd.getpwuid(os.getuid()); print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups(),'username':p.pw_name,'home':p.pw_dir,'shell':p.pw_shell},sort_keys=True))"
    identity_argv = base + ['--exec', '/usr/bin/python3', '-I', '-B', '-c', identity_code]
    identity = subprocess.run(identity_argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    identity_record = {'argv': identity_argv, 'returncode': identity.returncode,
        'stdout': identity.stdout.decode('utf8', 'replace'), 'stderr': identity.stderr.decode('utf8', 'replace')}
    if identity.returncode == 0:
        try: identity_record['observed_identity'] = json.loads(identity.stdout)
        except ValueError: identity_record['parse_failed'] = True
    write(output/'default-user.json', identity_record)
    argv = base + ['--user', 'root', '--exec', '/usr/bin/python3', '-I', '-B', wsl_path(__file__), '--linux-inspect',
        '--manifest', wsl_path(manifest), '--manifest-sha256', args.manifest_sha256,
        '--output-dir', wsl_path(output), '--queue-job-id', job['id']]
    reply = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=660, creationflags=subprocess.CREATE_NO_WINDOW)
    inputs_after = {str(p): ref(p) for p in (Path(__file__), USERLAND, manifest)}
    unchanged = inputs_before == inputs_after
    record = {'schema_version': 'import-diagnostic-host-invocation-1', 'queue_job_id': job['id'],
        'argv': argv, 'returncode': reply.returncode, 'stdout': reply.stdout.decode('utf8', 'replace'),
        'stderr': reply.stderr.decode('utf8', 'replace'), 'inputs_before': inputs_before, 'inputs_after': inputs_after,
        'inputs_unchanged': unchanged, 'default_user': identity_record, 'official_queue_completion_verified': False,
        'modifies_distribution': False, 'accepted_overlay': False}
    if (output/'diagnostic.json').is_file(): record['diagnostic'] = ref(output/'diagnostic.json')
    write(output/'host-invocation.json', record); print(json.dumps(record, sort_keys=True))
    return 0 if reply.returncode == 0 and unchanged and identity.returncode == 0 and 'observed_identity' in identity_record else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', default='LLMs-Robotics-Candidate-001')
    parser.add_argument('--manifest', required=True); parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output-dir', required=True); parser.add_argument('--linux-inspect', action='store_true')
    parser.add_argument('--queue-job-id')
    args = parser.parse_args()
    if args.linux_inspect:
        if not args.queue_job_id: raise ValueError('Missing owning queue job identity')
        return linux_inspect(args)
    if os.name != 'nt': raise ValueError('Launch through the installed Windows queue')
    return windows_run(args)


if __name__ == '__main__': raise SystemExit(main())
