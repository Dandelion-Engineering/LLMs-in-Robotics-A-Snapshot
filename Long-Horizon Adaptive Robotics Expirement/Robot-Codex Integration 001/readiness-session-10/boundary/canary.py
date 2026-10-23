"""Adversarial boundary checks using only task-created, nonsecret canaries."""
import errno
import json
import os
from pathlib import Path
import socket
import subprocess
import urllib.error
import urllib.request

checks, details = {}, {}
workspace = Path('/workspace')
fixture = json.loads((workspace / 'live/canaries.json').read_text())


def denied_file(label, path):
    try:
        Path(path).read_bytes()
        checks[label] = False
    except OSError as error:
        checks[label] = error.errno in (errno.ENOENT, errno.EACCES, errno.EPERM)
        details[label] = {'errno': error.errno}


checks['workspace_read'] = (workspace / 'RobotAgentPrompt.md').is_file()
for label, path in fixture['protected'].items():
    denied_file(label, path)
for path in ('/mnt/c', '/mnt/d', '/home', '/init', '/proc/1/root/mnt/c'):
    checks['hidden:' + path] = not Path(path).exists()
for path in ('RobotAgentPrompt.md', 'Tasks.md', 'Tools.md', 'live/state.json'):
    try:
        with (workspace / path).open('r+b'):
            pass
        checks['readonly:' + path] = False
    except OSError as error:
        checks['readonly:' + path] = error.errno in (errno.EROFS, errno.EACCES, errno.EPERM)
for name in ('notes', 'programs'):
    path = workspace / name / 'canary-write.txt'
    path.write_text('synthetic-write')
    checks['write:' + name] = path.read_text() == 'synthetic-write'
    path.unlink()
with (workspace / 'Continuity.md').open('r+b') as file:
    data = file.read()
    file.seek(0)
    file.write(data)
checks['write:Continuity.md'] = True
# The public symlink stays in the read-only root. Atomic replacement happens
# only inside its dedicated writable backing directory, and restores old bytes.
target = (workspace / 'Continuity.md').resolve(strict=True)
checks['continuity_fixed_link'] = (workspace / 'Continuity.md').is_symlink() and target == workspace / '.continuity/Continuity.md'
temporary = target.with_name('canary-continuity.tmp')
temporary.write_bytes(data)
os.replace(temporary, target)
checks['continuity_atomic_replace'] = (workspace / 'Continuity.md').read_bytes() == data
for label, operation in [
    ('workspace_root_write_denied', lambda: (workspace / 'not-approved.txt').write_text('denied')),
    ('continuity_public_link_replace_denied', lambda: os.replace(workspace / 'notes/canary-public.tmp', workspace / 'Continuity.md')),
]:
    (workspace / 'notes/canary-public.tmp').write_text('synthetic')
    try:
        operation()
        checks[label] = False
    except OSError as error:
        checks[label] = error.errno in (errno.EROFS, errno.EACCES, errno.EPERM, errno.EXDEV)
    (workspace / 'notes/canary-public.tmp').unlink(missing_ok=True)
escape = workspace / 'notes' / 'escape-link'
escape.symlink_to(fixture['protected']['repository_canary'])
denied_file('symlink_escape_denied', escape)
escape.unlink()
for label, address, family in [
    ('external_ipv4', ('1.1.1.1', 443), socket.AF_INET),
    ('host_loopback_other_port', ('127.0.0.1', fixture['other_port']), socket.AF_INET),
    ('external_ipv6', ('2606:4700:4700::1111', 443), socket.AF_INET6),
]:
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect(address)
            checks[label + '_denied'] = False
        except OSError as error:
            checks[label + '_denied'] = error.errno in (errno.ENETUNREACH, errno.ECONNREFUSED, errno.EACCES, errno.EPERM)
            details[label] = {'errno': error.errno}
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    try:
        sock.sendto(b'synthetic-canary', ('1.1.1.1', 53))
        checks['udp_egress_denied'] = False
    except OSError as error:
        checks['udp_egress_denied'] = error.errno in (errno.ENETUNREACH, errno.EACCES, errno.EPERM)
        details['udp_egress'] = {'errno': error.errno}
endpoint = json.loads((workspace / 'live/endpoint.json').read_text())
request = urllib.request.Request(endpoint['url'] + '/status', headers={'X-Robot-Capability': endpoint['capability']})
with urllib.request.urlopen(request, timeout=8) as response:
    status = json.load(response)
checks['approved_loopback_gateway'] = status.get('ok') is True and 'authority_epoch' in status
for label, suffix in [('unknown_endpoint', '/not-approved'), ('arbitrary_url', '/http://example.com')]:
    try:
        with urllib.request.urlopen(endpoint['url'] + suffix, timeout=5):
            checks[label + '_denied'] = False
    except urllib.error.HTTPError as error:
        checks[label + '_denied'] = error.code == 403
for method, path in [('GET', '/operator/status'), ('POST', '/operator/start-invocation'),
                     ('POST', '/operator/retire-invocation'), ('POST', '/operator/stop'),
                     ('POST', '/restart-agent'), ('POST', '/run-program'),
                     ('GET', '/history?after=0&limit=201'),
                     ('GET', '/history?after=0&limit=1&url=http://example.com'),
                     ('GET', '/command/../status'), ('GET', '/%73tatus'),
                     ('POST', '/status'), ('GET', '/observe')]:
    query = urllib.request.Request(endpoint['url'] + path, method=method,
                                   data=b'{}' if method == 'POST' else None,
                                   headers={'X-Robot-Capability': endpoint['capability']})
    try:
        urllib.request.urlopen(query, timeout=5)
        checks['route_denied:' + method + ':' + path] = False
    except urllib.error.HTTPError as error:
        checks['route_denied:' + method + ':' + path] = error.code == 403
# Direct IPC must enforce the same vocabulary even if the HTTP facade is skipped.
with socket.socket(socket.AF_UNIX) as client:
    client.settimeout(5)
    client.connect('/gateway.sock')
    client.sendall((json.dumps({'method': 'POST', 'path': '/operator/stop',
                               'capability': endpoint['capability'], 'body': '{}'}) + '\n').encode())
    reply = json.loads(client.makefile('rb').readline(4096))
    checks['direct_ipc_operator_denied'] = reply['status'] == 403
try:
    urllib.request.urlopen(endpoint['url'] + '/status', timeout=5)
    checks['gateway_authentication'] = False
except urllib.error.HTTPError as error:
    checks['gateway_authentication'] = error.code == 403
child = subprocess.run(['/bin/sh', '-c', 'test ! -e /mnt/c && test ! -e /home && test ! -e /init'])
checks['child_inherits_boundary'] = child.returncode == 0
nested = subprocess.run(['/usr/bin/unshare', '-Ur', '/bin/true'], capture_output=True)
checks['nested_user_namespace_denied'] = nested.returncode != 0
details['nested_namespace_stderr'] = nested.stderr.decode(errors='replace').strip()
result = {'qualified': all(checks.values()), 'checks': checks, 'details': details,
          'scope': 'nonmodel boundary canaries; read-only status against protected gateway; no actuator submissions by these checks'}
print(json.dumps(result), flush=True)
raise SystemExit(0 if result['qualified'] else 1)
