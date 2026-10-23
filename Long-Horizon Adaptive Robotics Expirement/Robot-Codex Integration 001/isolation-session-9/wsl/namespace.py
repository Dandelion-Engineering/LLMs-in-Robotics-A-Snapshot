"""Outer namespace policy; trusted code, never an agent-editable launcher."""
from pathlib import Path


def command(workspace, bridge_socket, source, executable=None, codehost=None):
    workspace, source = Path(workspace), Path(source)
    args = [
        '/usr/bin/bwrap', '--unshare-all', '--unshare-user', '--disable-userns',
        '--assert-userns-disabled', '--die-with-parent', '--new-session',
        '--cap-drop', 'ALL', '--clearenv',
        '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
        '--setenv', 'HOME', '/workspace', '--setenv', 'TMPDIR', '/tmp',
        '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
        '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
        '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
        '--ro-bind', str(workspace), '/workspace',
        '--bind', str(workspace / 'notes'), '/workspace/notes',
        '--bind', str(workspace / 'programs'), '/workspace/programs',
        '--bind', str(workspace / 'Continuity.md'), '/workspace/Continuity.md',
        '--ro-bind', str(bridge_socket), '/gateway.sock',
        '--ro-bind', str(source / 'inside.py'), '/inside.py',
        '--ro-bind', str(source / 'canary.py'), '/canary.py',
        '--chdir', '/workspace',
    ]
    if executable:
        args += ['--ro-bind', str(executable), '/codex']
    if codehost:
        args += ['--ro-bind', str(codehost), '/code-mode-host',
                 '--ro-bind', str(source / 'codehost_canary.py'), '/codehost_canary.py']
    args += ['--remount-ro', '/', '/usr/bin/python3', '-I', '-B', '/inside.py']
    return args
