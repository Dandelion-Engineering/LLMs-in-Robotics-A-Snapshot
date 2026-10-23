"""Queue-owned fresh project WSL import plus read-only identity checks.

Never unregisters, overwrites, repairs, starts apt, shuts down WSL, or changes
global configuration. Any partial import is retained and requires review.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2]
TOOLS = HERE.parent / 'userland-tools'
TARGET = 'LLMs-Robotics-Candidate-001'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def local_path(value):
    path = Path(value)
    if not path.is_absolute() or len(path.drive) != 2 or path.drive[1] != ':':
        raise ValueError('Absolute local Windows drive path required')
    for ancestor in (path, *path.parents):
        if ancestor.exists() and getattr(ancestor.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Reparse path is not supported: ' + str(ancestor))
    return path.resolve()


def wsl_path(path):
    path = local_path(path)
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]


def decode(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    if b'\x00' in raw:
        return raw.decode('utf-16-le')
    return raw.decode('utf-8-sig', 'replace')


def receipt_argument(receipt, flag):
    argv = receipt['argv']
    if argv.count(flag) != 1 or argv.index(flag) + 1 >= len(argv):
        raise ValueError('Build receipt lacks one exact argument: ' + flag)
    value = Path(argv[argv.index(flag) + 1])
    return local_path(value if value.is_absolute() else Path(receipt['cwd']) / value)


IDENTITY = r'''
import ctypes,hashlib,json,os,pathlib,pwd,subprocess,sys
account=pwd.getpwuid(os.getuid())
assert (os.getuid(),os.geteuid(),os.getgid(),account.pw_name,account.pw_dir,account.pw_shell)==(1000,1000,1000,'dandelion','/home/dandelion','/bin/bash')
paths={'python':pathlib.Path(sys.executable).resolve(),'bubblewrap':pathlib.Path('/usr/bin/bwrap').resolve(),'libseccomp':pathlib.Path('/usr/lib/x86_64-linux-gnu/libseccomp.so.2').resolve()}
lib=ctypes.CDLL(str(paths['libseccomp']),use_errno=True)
lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]
lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
read_number=lib.seccomp_syscall_resolve_name(b'read')
assert read_number>=0
version=subprocess.run(['/usr/bin/bwrap','--version'],stdin=subprocess.DEVNULL,capture_output=True,timeout=5,check=True)
print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'account':account.pw_name,'home':account.pw_dir,'shell':account.pw_shell,'python_version':sys.version,'bubblewrap_version':version.stdout.decode().strip(),'libseccomp_read_syscall_number':read_number,'files':{k:{'path':str(v),'sha256':hashlib.sha256(v.read_bytes()).hexdigest()} for k,v in paths.items()},'scope':'Native identity only; sandbox/adversarial/resource/restart tests remain separate'},sort_keys=True))
'''


def main(args):
    if os.name != 'nt':
        raise ValueError('Use the installed Windows queue')
    sys.path.insert(0, str(EXP / 'Runtime'))
    import release_runner as runner
    job = runner.queued_job(expected_script=str(Path(__file__).resolve()))
    output, instance = local_path(args.output), local_path(args.instance_dir)
    manifest_path, archive = local_path(args.manifest), local_path(args.archive)
    receipt_path = local_path(args.build_receipt)
    owned_roots = (EXP.parents[0].resolve(), Path('D:/CodexEvidence/LLMs-in-Robotics').resolve())
    if not any(instance.is_relative_to(root) and instance != root for root in owned_roots):
        raise ValueError('Instance must be inside the project workspace or its D: evidence root')
    if instance.exists() or not instance.parent.is_dir() or output.exists() or not output.parent.is_dir():
        raise ValueError('Fresh instance/output with existing parent directories required')
    if any(p.is_relative_to(instance) or instance.is_relative_to(p) for p in (output, manifest_path, archive)):
        raise ValueError('Instance must not overlap metadata or build artifacts')
    output.mkdir()
    sources = {str(p): digest(p) for p in [Path(__file__), *sorted(TOOLS.glob('*.py'))]}
    write(output / 'started.json', {'queue_job_id': job['id'], 'started_at_utc': datetime.now(timezone.utc).isoformat(),
          'target_distribution': TARGET, 'instance_dir': str(instance), 'sources': sources,
          'build_receipt': str(receipt_path), 'manifest': str(manifest_path), 'archive': str(archive)})
    calls = []

    def command(label, argv, timeout):
        prefix = output / ('%02d-%s' % (len(calls) + 1, label))
        record = {'label': label, 'argv': [str(a) for a in argv], 'timeout_s': timeout,
                  'started_at_utc': datetime.now(timezone.utc).isoformat()}
        calls.append(record)
        write(prefix.with_suffix('.started.json'), record)
        try:
            result = subprocess.run(record['argv'], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE, shell=False, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
            stdout, stderr = result.stdout, result.stderr
            record['returncode'] = result.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b'', error.stderr or b''
            record.update(returncode=None, error='TimeoutExpired; completion/import state unknown; no cleanup attempted')
        except OSError as error:
            stdout, stderr = b'', b''
            record.update(returncode=None, error=type(error).__name__ + ': ' + str(error))
        prefix.with_suffix('.stdout.bin').write_bytes(stdout)
        prefix.with_suffix('.stderr.bin').write_bytes(stderr)
        record.update(stdout=decode(stdout), stderr=decode(stderr),
                      ended_at_utc=datetime.now(timezone.utc).isoformat())
        write(prefix.with_suffix('.result.json'), record)
        if record['returncode'] != 0:
            raise RuntimeError('Command failed; exact outputs retained: ' + label)
        return record['stdout']

    imported = False
    try:
        receipt = load(receipt_path)
        if type(receipt.get('exit_status')) is not int or receipt['exit_status'] != 0:
            raise ValueError('Actual successful build receipt required')
        runner.verify_queue_receipt(receipt['id'], receipt_path)
        if runner.python_entrypoint(receipt['argv'], receipt['cwd']) != (TOOLS / 'package_userland.py').resolve():
            raise ValueError('Receipt is not the exact userland builder entrypoint')
        if 'build' not in receipt['argv'] or receipt_argument(receipt, '--output-dir') != manifest_path.parent:
            raise ValueError('Receipt does not identify this build output')
        config_path = receipt_argument(receipt, '--config')
        manifest, host = load(manifest_path), load(manifest_path.parent / 'host-invocation.json')
        config = manifest['config']
        if (manifest.get('schema_version') != 'project-candidate-userland-1' or manifest.get('status') != 'complete'
                or manifest.get('queue_job_id') != receipt['id'] or manifest.get('inputs_unchanged') is not True
                or config.get('target_distribution') != TARGET or config.get('source_distribution') == TARGET
                or (config.get('username'), config.get('uid'), config.get('gid'), config.get('shell')) != ('dandelion', 1000, 1000, '/bin/bash')):
            raise ValueError('Unsupported/incomplete build or target account configuration')
        current_tools = {p.name: digest(p) for p in sorted(TOOLS.glob('*.py'))}
        if (host.get('mode') != 'build' or host.get('queue_job_id') != receipt['id']
                or type(host.get('returncode')) is not int or host['returncode'] != 0
                or host.get('sources_unchanged') is not True
                or host.get('source_files_before') != current_tools or host.get('source_files_after') != current_tools
                or host.get('distribution') != config['source_distribution']
                or digest(config_path) != manifest['config_sha256'] or load(config_path) != config
                or manifest['source_before_sha256'] != manifest['source_after_sha256']
                or manifest['package_metadata_before_sha256'] != manifest['package_metadata_after_sha256']):
            raise ValueError('Builder sources/config/input identity changed')
        built = json.loads(host['stdout'])
        manifest_sha = digest(manifest_path)
        if built.get('manifest_sha256') != manifest_sha or built.get('status') != 'complete' or built.get('archive') != manifest['archive']:
            raise ValueError('Manifest differs from retained successful builder output')
        if (archive != manifest_path.parent / 'rootfs.tar' or wsl_path(archive) != manifest['archive']['path']
                or archive.stat().st_size != manifest['archive']['bytes'] or digest(archive) != manifest['archive']['sha256']):
            raise ValueError('Rootfs archive path/size/SHA256 differs from successful build')
        bound = {str(p): digest(p) for p in (manifest_path, receipt_path, config_path, manifest_path.parent / 'host-invocation.json')}
        bound[str(archive)] = manifest['archive']['sha256']
        write(output / 'verified-build.json', {'queue_job_id': receipt['id'], 'files': bound,
              'archive': manifest['archive'], 'sources': sources, 'manifest_sha256': manifest_sha})
        wsl = str(Path(os.environ['SystemRoot']) / 'System32/wsl.exe')
        names = [line.strip() for line in command('list-before', [wsl, '--list', '--quiet'], 15).splitlines() if line.strip()]
        if TARGET.casefold() in {name.casefold() for name in names} or instance.exists():
            raise ValueError('Target distribution or instance already exists; no overwrite/unregister allowed')
        command('import', [wsl, '--import', TARGET, str(instance), str(archive), '--version', '2'], 300)
        imported = True
        verify = [wsl, '--distribution', TARGET, '--user', 'root', '--exec', '/usr/bin/python3', '-I', '-B',
                  wsl_path(TOOLS / 'userland.py'), 'verify', '--root', '/', '--manifest', wsl_path(manifest_path),
                  '--manifest-sha256', manifest_sha, '--seconds', '25']
        verified_before = json.loads(command('tree-before', verify, 30))
        identity = json.loads(command('default-account-native-identity',
            [wsl, '--distribution', TARGET, '--exec', '/usr/bin/python3', '-I', '-B', '-c', IDENTITY], 20))
        verified_after = json.loads(command('tree-after', verify, 30))
        if any(v.get('verified') is not True or v.get('tree_sha256') != manifest['tree_sha256'] for v in (verified_before, verified_after)):
            raise ValueError('Verifier did not establish exact static tree identity')
        if any(digest(path) != value for path, value in {**sources, **bound}.items()):
            raise ValueError('Source/build metadata changed during import/verification')
        write(output / 'result.json', {'status': 'verified', 'queue_job_id': job['id'], 'build_queue_job_id': receipt['id'],
              'target_distribution': TARGET, 'instance_dir': str(instance), 'manifest_sha256': manifest_sha,
              'tree_before': verified_before, 'native_identity': identity, 'tree_after': verified_after,
              'sources_unchanged': True, 'official_queue_completion_verified': False,
              'scope': 'Imported userland identity only; isolation/resource/physics/restart/readiness remain separate'})
        print(json.dumps({'status': 'verified', 'output': str(output), 'target_distribution': TARGET, 'manifest_sha256': manifest_sha}))
    except BaseException as error:
        write(output / 'failure.json', {'status': 'failed', 'queue_job_id': job['id'], 'import_command_returned_zero': imported,
              'partial_import_may_exist': any(c['label'] == 'import' for c in calls),
              'error': type(error).__name__ + ': ' + str(error), 'cleanup_attempted': False,
              'sources_unchanged': all(Path(p).is_file() and digest(p) == value for p, value in sources.items())})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('build-receipt', 'manifest', 'archive', 'instance-dir', 'output'):
        parser.add_argument('--' + option, required=True, type=Path)
    main(parser.parse_args())
