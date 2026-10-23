"""Package an installed Linux runtime; verify its static tree without importing it.

Only the Windows queue wrapper launches build. verify is a bounded read-only
probe suitable for an already queued freeze/verification operation.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
import time

SCHEMA = 'project-candidate-userland-1'
SEEDS = ['python3-minimal', 'python3.12', 'libseccomp2', 'bubblewrap',
         'bash', 'dash', 'coreutils', 'mount', 'util-linux']
SCOPES = ['/usr', '/etc', '/bin', '/sbin', '/lib', '/lib64', '/home', '/root']
ALIASES = {'/bin': 'usr/bin', '/sbin': 'usr/sbin', '/lib': 'usr/lib', '/lib64': 'usr/lib64'}
PACKAGED_CONFIG = {'/etc/python3.12/sitecustomize.py': 'libpython3.12-minimal'}
FIELDS = ['binary:Package', 'Package', 'Architecture', 'Version', 'db:Status-Status',
          'Pre-Depends', 'Depends', 'Provides', 'Essential']


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_time(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise RuntimeError('Verification time bound exceeded; no identity established')


def file_sha(path, deadline=None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check_time(deadline)
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def run(argv):
    reply = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=False, timeout=30,
                           env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    if reply.returncode:
        raise RuntimeError('Command failed: ' + repr(argv) + ': ' + reply.stderr.decode('utf8', 'replace'))
    return reply.stdout.decode('utf8')


def package_inventory():
    raw = run(['/usr/bin/dpkg-query', '-W', '-f=' + '\t'.join('${' + x + '}' for x in FIELDS) + '\n'])
    rows = {}
    for line in raw.splitlines():
        values = line.split('\t')
        if len(values) != len(FIELDS):
            raise ValueError('Unexpected dpkg metadata shape')
        row = dict(zip(FIELDS, values))
        if row['db:Status-Status'] == 'installed':
            rows[row['binary:Package']] = row
    return rows, sha(raw.encode())


DEP = re.compile(r'^([a-z0-9][a-z0-9+.-]*)(?::([a-z0-9-]+))?(?:\s*\((<<|<=|=|>=|>>)\s*([^()\s]+)\))?$')


def parse_term(text):
    found = DEP.fullmatch(text.strip())
    if not found:
        raise ValueError('Unsupported installed dependency expression: ' + text)
    return found.groups()


def version_satisfies(actual, operator, required):
    if operator is None:
        return True
    if actual is None:
        return False
    result = subprocess.run(['/usr/bin/dpkg', '--compare-versions', actual, operator, required],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, timeout=5)
    if result.returncode not in (0, 1):
        raise ValueError('dpkg rejected version comparison')
    return result.returncode == 0


def resolve_packages(rows, seeds, native, compare=version_satisfies):
    providers = {}
    for key, row in rows.items():
        for term in filter(None, (x.strip() for x in row['Provides'].split(','))):
            name, qualifier, operator, version = parse_term(term)
            if qualifier or operator not in (None, '='):
                raise ValueError('Unsupported Provides: ' + term)
            providers.setdefault(name, []).append((key, version))
    selected, decisions = set(), []

    def choose(expression):
        for alternative in expression.split('|'):
            name, qualifier, operator, required = parse_term(alternative)
            architecture = native if qualifier in (None, 'native', 'any') else qualifier
            direct = [(key, row['Version']) for key, row in rows.items()
                      if row['Package'] == name and row['Architecture'] in (architecture, 'all')]
            virtual = [(key, version) for key, version in providers.get(name, [])
                       if rows[key]['Architecture'] in (architecture, 'all')]
            for key, version in sorted(direct) + sorted(virtual):
                if compare(version, operator, required):
                    decisions.append({'expression': expression, 'selected': key, 'alternative': alternative.strip()})
                    return key
        raise ValueError('No installed satisfying dependency: ' + expression)

    pending = [choose(name) for name in seeds]
    # Debian dependencies may assume Essential packages without naming them.
    pending += sorted(key for key, row in rows.items() if row['Essential'] == 'yes'
                      and row['Architecture'] in (native, 'all'))
    while pending:
        key = pending.pop()
        if key in selected:
            continue
        selected.add(key)
        row = rows[key]
        for field in ('Pre-Depends', 'Depends'):
            pending += [choose(x.strip()) for x in row[field].split(',') if x.strip()]
    return sorted(selected), decisions


def normalized_package_path(name, package_name=None):
    path = PurePosixPath(name)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe package path: ' + name)
    if name in PACKAGED_CONFIG:
        if package_name != PACKAGED_CONFIG[name]:
            raise ValueError('Allowlisted runtime config has unexpected package owner: ' + name)
        return name
    for old, new in ALIASES.items():
        if name == old:
            return '/'+new
        if name.startswith(old + '/'):
            name = '/' + new + name[len(old):]
            break
    if name != '/usr' and not name.startswith('/usr/'):
        return None
    if name == '/usr/local' or name.startswith('/usr/local/') or name == '/usr/lib/wsl' or name.startswith('/usr/lib/wsl/'):
        return None  # Explicit exclusion; never descend into host/private content.
    return name


def describe(path, deadline=None):
    check_time(deadline)
    info = path.lstat()
    value = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
    if stat.S_ISREG(info.st_mode):
        value.update(type='file', bytes=info.st_size, sha256=file_sha(path, deadline))
    elif stat.S_ISLNK(info.st_mode):
        value.update(type='symlink', target=os.readlink(path))
    elif stat.S_ISDIR(info.st_mode):
        value.update(type='directory')
    else:
        raise ValueError('Unsupported special static file: ' + str(path))
    return value


def inventory_paths(root, names, deadline=None):
    root = Path(root)
    return {name: describe(root / name.lstrip('/'), deadline) for name in sorted(names)}


def walk_scope(root, scopes=SCOPES, deadline=None):
    names = set()
    def visit(name):
        check_time(deadline)
        path = Path(root) / name.lstrip('/')
        if not path.exists() and not path.is_symlink():
            raise ValueError('Required static scope missing: ' + name)
        names.add(name)
        if path.is_dir() and not path.is_symlink():
            for child in sorted(path.iterdir()):
                visit(name + '/' + child.name)
    for scope in scopes:
        visit(scope)
    return names


def generated(config):
    user, uid, gid, shell = config['username'], config['uid'], config['gid'], config['shell']
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', user) or user == 'root':
        raise ValueError('Explicit non-root username required')
    if type(uid) is not int or type(gid) is not int or uid <= 0 or gid <= 0:
        raise ValueError('Explicit positive integer UID/GID required')
    if shell not in ('/bin/bash', '/bin/dash', '/bin/sh'):
        raise ValueError('Unsupported explicit login shell')
    wsl = (f'[boot]\nsystemd=false\n[user]\ndefault={user}\n'
           '[automount]\nenabled=true\nroot=/mnt/\nmountFsTab=false\nldconfig=false\n'
           '[interop]\nenabled=false\nappendWindowsPath=false\n'
           '[gpu]\nenabled=false\nappendLibPath=false\n'
           '[network]\ngenerateHosts=false\ngenerateResolvConf=false\n'
           '[time]\nuseWindowsTimezone=false\n')
    files = {
        '/etc/wsl.conf': wsl,
        '/etc/passwd': f'root:x:0:0:root:/root:/bin/sh\n{user}:x:{uid}:{gid}:Project candidate:/home/{user}:{shell}\n',
        '/etc/group': f'root:x:0:\n{user}:x:{gid}:\n',
        '/etc/nsswitch.conf': 'passwd: files\ngroup: files\nshadow: files\nhosts: files\n',
        '/etc/hosts': '127.0.0.1 localhost\n::1 localhost\n',
        '/etc/fstab': '', '/etc/resolv.conf': '', '/etc/timezone': 'Etc/UTC\n',
    }
    rows, payloads = {}, {}
    for name in ('/usr', '/etc', '/home', '/root', '/proc', '/sys', '/dev', '/run', '/tmp', '/mnt', '/home/'+user):
        rows[name] = {'type': 'directory', 'mode': 0o1777 if name == '/tmp' else (0o700 if name == '/root' else 0o755),
                      'uid': uid if name == '/home/'+user else 0, 'gid': gid if name == '/home/'+user else 0}
    for name, target in ALIASES.items():
        rows[name] = {'type': 'symlink', 'mode': 0o777, 'uid': 0, 'gid': 0, 'target': target}
    for name, content in files.items():
        payloads[name] = content.encode('utf8')
        rows[name] = {'type': 'file', 'mode': 0o644, 'uid': 0, 'gid': 0,
                      'bytes': len(payloads[name]), 'sha256': sha(payloads[name])}
    rows['/etc/localtime'] = {'type': 'symlink', 'mode': 0o777, 'uid': 0, 'gid': 0,
                             'target': '/usr/share/zoneinfo/Etc/UTC'}
    return rows, payloads


def resolve_image_link(name, rows):
    """Resolve image symlinks lexically, never against the host filesystem."""
    parts, pending, hops = [], name.split('/'), 0
    while pending:
        part = pending.pop(0)
        if part in ('', '.'):
            continue
        if part == '..':
            if not parts:
                raise ValueError('Image link escapes root: ' + name)
            parts.pop(); continue
        parts.append(part)
        current = '/' + '/'.join(parts)
        row = rows.get(current)
        if row is not None and row['type'] == 'symlink':
            hops += 1
            if hops > 40:
                raise ValueError('Image symlink cycle: ' + name)
            target = row['target']; parts.pop()
            if target.startswith('/'):
                parts = []
            pending = target.split('/') + pending
    return '/' + '/'.join(parts)


def validate_links(rows, optional=None):
    optional = optional or {}
    for name, target in optional.items():
        if (not re.fullmatch(r'/usr/share/locale/[A-Za-z0-9_@.-]+/LC_TIME/coreutils\.mo', name)
                or target != name.replace('/LC_TIME/', '/LC_MESSAGES/')
                or rows.get(name, {}).get('type') != 'symlink'
                or rows[name]['target'] != '../LC_MESSAGES/coreutils.mo'
                or resolve_image_link(name, rows) != target or target in rows):
            raise ValueError('Optional locale link no longer matches measured absence: ' + name)
    for name, row in rows.items():
        if row['type'] == 'symlink' and resolve_image_link(name, rows) not in rows:
            if name not in optional:
                raise ValueError('Selected package link target missing from image: ' + name)


def bound_json(base, ref):
    path = (Path(base)/ref['path']).resolve(); raw = path.read_bytes()
    if sha(raw) != ref['sha256'] or len(raw) != ref['bytes']:
        raise ValueError('Optional locale evidence hash/size mismatch: ' + str(path))
    return json.loads(raw), {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def load_optional_links(config, config_path):
    base = Path(config_path).parent
    policy, policy_ref = bound_json(base, config['optional_locale_links'])
    if policy.get('schema_version') != 'measured-optional-locale-links-1':
        raise ValueError('Unsupported optional locale policy')
    diagnostic, diagnostic_ref = bound_json(base, policy['source_diagnostic'])
    receipt, receipt_ref = bound_json(base, policy['official_receipt'])
    if (diagnostic.get('status') != 'complete' or diagnostic.get('inputs_unchanged') is not True
            or receipt.get('id') != diagnostic.get('queue_job_id') or receipt.get('state') != 'succeeded'
            or type(receipt.get('exit_status')) is not int or receipt['exit_status'] != 0):
        raise ValueError('Optional locale evidence lacks successful unchanged diagnostic authority')
    observed = {}
    for row in diagnostic['unresolved_links']:
        target = row['image_resolved_target']; name = row['path']
        host = row['host_metadata'][target]; owners = row['package_ownership']
        if (row['reason'] != 'target_absent_from_selected_image' or host['exists'] is not False
                or host['is_symlink'] is not False or owners[target]['returncode'] != 1 or owners[name]['returncode'] != 0
                or owners[name]['stdout'] != 'coreutils: ' + name + '\n'):
            raise ValueError('Diagnostic does not establish an optional source-dangling locale link')
        observed[name] = {'path': name, 'link_target': row['link_target'],
                          'required_absent_target': target, 'source_package': 'coreutils'}
    supplied = {row['path']: row for row in policy['links']}
    if len(policy['links']) != 45 or len(diagnostic['unresolved_links']) != 45 or len(observed) != 45 or diagnostic['unresolved_link_count'] != 45 or supplied != observed:
        raise ValueError('Optional locale policy differs from the exact45 measured links')
    optional = {name: row['required_absent_target'] for name, row in supplied.items()}
    return optional, {'policy': policy_ref, 'diagnostic': diagnostic_ref, 'official_receipt': receipt_ref}


def optional_source_absence(optional, root='/'):
    observations = {}
    for name, target in sorted(optional.items()):
        source = Path(root)/name.lstrip('/'); absent = Path(root)/target.lstrip('/')
        if not source.is_symlink() or os.readlink(source) != '../LC_MESSAGES/coreutils.mo':
            raise ValueError('Source optional locale link changed: ' + name)
        if absent.exists() or absent.is_symlink():
            raise ValueError('Source optional locale target is no longer absent: ' + target)
        observations[target] = {'exists': False, 'is_symlink': False}
    return observations


def write_json(path, value):
    with Path(path).open('xb') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b'\n')


def collect_owned_paths(selected, package_rows):
    owned, lists, packaged_config_owners = {}, {}, {}
    for package in selected:
        listing = run(['/usr/bin/dpkg-query', '-L', package]); lists[package] = sha(listing.encode())
        for name in listing.splitlines():
            if not name.startswith('/'):
                continue  # dpkg diversion annotations are not path entries.
            normalized = normalized_package_path(name, package_rows[package]['Package'])
            if normalized is not None:
                owned[normalized] = normalized
                if normalized in PACKAGED_CONFIG:
                    packaged_config_owners[normalized] = package
    # Add ancestor directories only; never recursively copy unowned contents.
    for name in list(owned):
        parent = PurePosixPath(name).parent
        while str(parent) != '/':
            owned[str(parent)] = str(parent); parent = parent.parent
    return owned, lists, packaged_config_owners


def host_link_metadata(name):
    """Metadata only outside the proposed image; never read target file contents."""
    path = Path(name)
    result = {'path': name, 'exists': path.exists(), 'is_symlink': path.is_symlink()}
    if path.exists() or path.is_symlink():
        info = path.lstat()
        result.update(mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid,
                      type='symlink' if path.is_symlink() else ('directory' if path.is_dir() else 'file'))
        if path.is_symlink():
            result['link_target'] = os.readlink(path)
        try:
            result['resolved_path'] = str(path.resolve(strict=True))
        except (OSError, RuntimeError) as exc:
            result['resolve_error'] = type(exc).__name__ + ': ' + str(exc)
    return result


def package_ownership(name):
    reply = subprocess.run(['/usr/bin/dpkg-query', '-S', name], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
    if reply.returncode not in (0, 1):
        raise RuntimeError('dpkg ownership query failed for ' + name)
    return {'path': name, 'returncode': reply.returncode,
            'stdout': reply.stdout.decode('utf8'), 'stderr': reply.stderr.decode('utf8')}


def unresolved_link_rows(image, metadata=host_link_metadata, ownership=package_ownership):
    findings, owner_cache = [], {}
    for name, row in sorted(image.items()):
        if row['type'] != 'symlink':
            continue
        issue = {'path': name, 'link_target': row['target']}
        try:
            target = resolve_image_link(name, image)
            if target in image:
                continue
            issue['image_resolved_target'] = target
            issue['reason'] = 'target_absent_from_selected_image'
        except ValueError as exc:
            target = None; issue.update(reason='image_link_resolution_error', error=str(exc))
        paths = {name}
        if target is not None:
            paths.add(target)
        observations = {path: metadata(path) for path in sorted(paths)}
        for observation in list(observations.values()):
            resolved = observation.get('resolved_path')
            if resolved and resolved not in observations:
                observations[resolved] = metadata(resolved)
        for path in observations:
            if path not in owner_cache:
                owner_cache[path] = ownership(path)
        issue['host_metadata'] = observations
        issue['package_ownership'] = {path: owner_cache[path] for path in observations}
        findings.append(issue)
    return findings


def diagnose(config_path, output, queue_job_id):
    if os.name != 'posix' or not queue_job_id:
        raise ValueError('Diagnostic requires Linux and the owning Windows queue identity')
    output = Path(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Use a fresh diagnostic output directory with existing parent')
    config_path = Path(config_path); config_bytes = config_path.read_bytes(); config = json.loads(config_bytes)
    image, _ = generated(config)
    before, metadata_sha = package_inventory()
    native = run(['/usr/bin/dpkg', '--print-architecture']).strip()
    seeds = config.get('seed_packages', SEEDS + ['tzdata'])
    if not isinstance(seeds, list) or not set(SEEDS + ['tzdata']) <= set(seeds) or not all(isinstance(x, str) for x in seeds):
        raise ValueError('Seed list must include the required runtime tools')
    selected, decisions = resolve_packages(before, seeds, native)
    owned, lists, packaged_config_owners = collect_owned_paths(selected, before)
    sources = inventory_paths('/', owned); image.update(sources)
    findings = unresolved_link_rows(image)
    after, after_metadata_sha = package_inventory()
    after_owned, after_lists, after_config_owners = collect_owned_paths(selected, after)
    after_sources = inventory_paths('/', after_owned)
    unchanged = (before == after and metadata_sha == after_metadata_sha and owned == after_owned
                 and sources == after_sources and lists == after_lists
                 and packaged_config_owners == after_config_owners and config_bytes == config_path.read_bytes())
    record = {'schema_version': 'userland-package-link-diagnostic-1',
              'status': 'complete' if unchanged else 'failed', 'queue_job_id': queue_job_id,
              'config_sha256': sha(config_bytes), 'selected_packages': {p: before[p] for p in selected},
              'dependency_choices': decisions, 'packaged_config_owners': packaged_config_owners,
              'selected_image_path_count': len(image),
              'selected_image_symlink_count': sum(r['type'] == 'symlink' for r in image.values()),
              'unresolved_link_count': len(findings), 'unresolved_links': findings,
              'source_before_sha256': sha(canonical(sources)), 'source_after_sha256': sha(canonical(after_sources)),
              'package_metadata_before_sha256': metadata_sha, 'package_metadata_after_sha256': after_metadata_sha,
              'package_lists_before': lists, 'package_lists_after': after_lists,
              'inputs_unchanged': unchanged, 'copies_runtime_files': False,
              'interpretation': 'All unresolved selected-image links; no automatic additions, exclusions, or package installs'}
    output.mkdir(); write_json(output/'diagnostic.json', record)
    if not unchanged:
        raise ValueError('Diagnostic source changed during observation; report retained')
    return {'status': 'complete', 'queue_job_id': queue_job_id,
            'diagnostic_sha256': file_sha(output/'diagnostic.json'),
            'unresolved_link_count': len(findings), 'inputs_unchanged': True}


def build(config_path, output, queue_job_id):
    if os.name != 'posix' or not queue_job_id:
        raise ValueError('Build requires Linux and the owning Windows queue job identity')
    output = Path(output)
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Use a fresh output directory with an existing parent')
    config_path = Path(config_path); config_bytes = config_path.read_bytes(); config = json.loads(config_bytes)
    optional, optional_refs = load_optional_links(config, config_path)
    absence_before = optional_source_absence(optional)
    image, payloads = generated(config)
    actual = run(['/usr/bin/id', config['username']]).strip()
    account = run(['/usr/bin/getent', 'passwd', config['username']]).strip().split(':')
    if len(account) != 7 or int(account[2]) != config['uid'] or int(account[3]) != config['gid'] or account[5] != '/home/'+config['username'] or account[6] != config['shell']:
        raise ValueError('Provided user identity differs from installed source account')
    before, metadata_sha = package_inventory()
    native = run(['/usr/bin/dpkg', '--print-architecture']).strip()
    seeds = config.get('seed_packages', SEEDS + ['tzdata'])
    if not isinstance(seeds, list) or not set(SEEDS + ['tzdata']) <= set(seeds) or not all(isinstance(x, str) for x in seeds):
        raise ValueError('Seed list must include the required runtime tools')
    selected, decisions = resolve_packages(before, seeds, native)
    owned, lists, packaged_config_owners = collect_owned_paths(selected, before)
    sources = inventory_paths('/', owned)
    image.update(sources)
    validate_links(image, optional)
    for required in ('/usr/bin/python3', '/usr/bin/bwrap', '/usr/lib/x86_64-linux-gnu/libseccomp.so.2', config['shell']):
        resolved = resolve_image_link(required, image)
        if resolved not in image or image[resolved]['type'] != 'file':
            raise ValueError('Required runtime file absent: ' + required)
    if native != 'amd64':
        raise ValueError('This measured runtime preparation supports installed amd64 only')
    copyrights = {}
    for package in selected:
        name = '/usr/share/doc/' + before[package]['Package'] + '/copyright'
        resolved = resolve_image_link(name, image)
        if resolved not in image or image[resolved]['type'] != 'file':
            raise ValueError('Selected package copyright missing: ' + package)
        copyrights[package] = {'path': name, 'resolved': resolved, 'sha256': image[resolved]['sha256']}
    output.mkdir()
    write_json(output/'started.json', {'schema_version': SCHEMA, 'queue_job_id': queue_job_id,
        'config_sha256': sha(config_bytes), 'purpose': 'fresh project userland artifact; no release readiness'})
    try:
        archive = output/'rootfs.tar'
        with tarfile.open(archive, mode='x', format=tarfile.PAX_FORMAT) as tar:
            for name, row in sorted(image.items()):
                info = tarfile.TarInfo(name.lstrip('/')); info.mode = row['mode']
                info.uid = row['uid']; info.gid = row['gid']; info.mtime = 0
                if row['type'] == 'directory':
                    info.type = tarfile.DIRTYPE; tar.addfile(info)
                elif row['type'] == 'symlink':
                    info.type = tarfile.SYMTYPE; info.linkname = row['target']; tar.addfile(info)
                else:
                    info.size = row['bytes']
                    data = payloads[name] if name in payloads else Path(name).read_bytes()
                    if len(data) != row['bytes'] or sha(data) != row['sha256']:
                        raise ValueError('Source changed while copied: ' + name)
                    tar.addfile(info, io.BytesIO(data))
        after, after_metadata_sha = package_inventory()
        after_sources = inventory_paths('/', owned)
        after_lists = {p: sha(run(['/usr/bin/dpkg-query', '-L', p]).encode()) for p in selected}
        after_optional, after_optional_refs = load_optional_links(config, config_path)
        absence_after = optional_source_absence(optional)
        if before != after or metadata_sha != after_metadata_sha or sources != after_sources or lists != after_lists or config_bytes != config_path.read_bytes():
            raise ValueError('Package/source/config changed while copying; partial output retained')
        if optional != after_optional or optional_refs != after_optional_refs or absence_before != absence_after:
            raise ValueError('Optional locale link evidence or target absence changed during copy')
        expected = {k: v for k, v in image.items() if any(k == s or k.startswith(s+'/') for s in SCOPES)}
        manifest = {'schema_version': SCHEMA, 'queue_job_id': queue_job_id, 'status': 'complete',
            'config': config, 'config_sha256': sha(config_bytes), 'source_account': actual,
            'architecture': native, 'seeds': seeds, 'packages': {p: before[p] for p in selected},
            'dependency_choices': decisions, 'copyrights': copyrights,
            'packaged_config_owners': packaged_config_owners,
            'optional_locale_links': optional, 'optional_locale_evidence': optional_refs,
            'optional_target_absence_before': absence_before, 'optional_target_absence_after': absence_after,
            'package_metadata_before_sha256': metadata_sha, 'package_metadata_after_sha256': after_metadata_sha,
            'package_lists_sha256': lists, 'source_before_sha256': sha(canonical(sources)),
            'source_after_sha256': sha(canonical(after_sources)), 'inputs_unchanged': True,
            'scopes': SCOPES, 'entries': expected, 'tree_sha256': sha(canonical(expected)),
            'required_absent': ['/etc/ld.so.cache', '/etc/ld.so.preload', '/usr/lib/wsl', '/usr/local'] + sorted(optional.values()),
            'archive': {'path': str(archive.resolve()), 'sha256': file_sha(archive), 'bytes': archive.stat().st_size},
            'archive_entries': image,
            'limitations': ['Pins userland, not shared WSL kernel/Windows/GPU or future timing',
                'Package versions describe installed provenance; copied bytes are authoritative',
                'Before/after identity cannot prove absence of an undetected change-and-restore between reads',
                'Dynamic /proc,/sys,/dev,/run,/tmp,/mnt contents and WSL root-level infrastructure are outside static scopes',
                'No inferred WSL injection exclusions: any extra /usr or /etc entry fails verification']}
        write_json(output/'manifest.json', manifest)
        return {'status': 'complete', 'manifest_sha256': file_sha(output/'manifest.json'),
                'tree_sha256': manifest['tree_sha256'], 'archive': manifest['archive'], 'queue_job_id': queue_job_id}
    except BaseException as exc:
        write_json(output/'failure.json', {'status': 'failed', 'error': type(exc).__name__ + ': ' + str(exc), 'queue_job_id': queue_job_id})
        raise


def verify(root, manifest_path, expected_sha, seconds=25):
    if not 0 < seconds <= 28 or not re.fullmatch('[0-9a-f]{64}', expected_sha):
        raise ValueError('Require exact manifest SHA and deadline <=28s')
    deadline = time.monotonic()+seconds
    raw = Path(manifest_path).read_bytes()
    if sha(raw) != expected_sha:
        raise ValueError('Manifest hash mismatch')
    manifest = json.loads(raw)
    if manifest.get('schema_version') != SCHEMA or manifest.get('status') != 'complete' or manifest.get('inputs_unchanged') is not True or manifest.get('scopes') != SCOPES:
        raise ValueError('Incomplete or unsupported userland manifest')
    expected = manifest['entries']
    if sha(canonical(expected)) != manifest['tree_sha256']:
        raise ValueError('Manifest tree digest mismatch')
    for name in manifest['required_absent']:
        path = Path(root)/name.lstrip('/')
        if path.exists() or path.is_symlink():
            raise ValueError('Required absent path exists: ' + name)
    names = walk_scope(root, deadline=deadline)
    if names != set(expected):
        raise ValueError('Static path set differs: ' + repr({'extra': sorted(names-set(expected))[:10], 'missing': sorted(set(expected)-names)[:10]}))
    actual = inventory_paths(root, names, deadline)
    if actual != expected:
        changed = [name for name in expected if actual.get(name) != expected[name]]
        raise ValueError('Static content/type/link/mode/owner differs: ' + repr(changed[:10]))
    check_time(deadline)
    return {'schema_version': SCHEMA, 'tree_sha256': manifest['tree_sha256'], 'verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    for name in ('build', 'diagnose'):
        p = sub.add_parser(name); p.add_argument('--config', required=True); p.add_argument('--output', required=True); p.add_argument('--queue-job-id', required=True)
    p = sub.add_parser('verify'); p.add_argument('--manifest', required=True); p.add_argument('--manifest-sha256', required=True); p.add_argument('--root', default='/'); p.add_argument('--seconds', type=float, default=25)
    args = parser.parse_args()
    if args.command in ('build', 'diagnose'):
        result = (build if args.command == 'build' else diagnose)(args.config, args.output, args.queue_job_id)
    else:
        result = verify(args.root, args.manifest, args.manifest_sha256, args.seconds)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
