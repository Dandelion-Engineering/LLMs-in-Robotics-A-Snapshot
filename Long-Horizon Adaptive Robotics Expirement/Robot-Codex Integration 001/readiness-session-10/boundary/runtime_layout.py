"""Trusted, durable Linux layout; model runtime never imports this module."""
from pathlib import Path, PurePosixPath
import hashlib
import os
import re
import stat
import uuid

RUNTIME_ROOT = Path('/var/tmp/robot-codex-session10')
CONTINUITY_LINK = '.continuity/Continuity.md'


def checked_run(path, must_exist=True):
    path = Path(path)
    if path.parent != RUNTIME_ROOT or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', path.name):
        raise ValueError('not a dedicated Session10 run')
    if path.resolve(strict=must_exist) != path or RUNTIME_ROOT.resolve(strict=must_exist) != RUNTIME_ROOT:
        raise ValueError('runtime path alias')
    return path


def validate_workspace(workspace):
    workspace = Path(workspace)
    checked_run(workspace.parent)
    if workspace.name != 'workspace' or workspace.resolve(strict=True) != workspace:
        raise ValueError('invalid workspace')
    for name in ('notes', 'programs', '.continuity'):
        path = workspace / name
        if not path.is_dir() or path.resolve(strict=True) != path:
            raise ValueError('writable directory alias')
    link = workspace / 'Continuity.md'
    if not link.is_symlink() or os.readlink(link) != CONTINUITY_LINK:
        raise ValueError('fixed continuity link missing or changed')
    target = workspace / CONTINUITY_LINK
    if not stat.S_ISREG(target.lstat().st_mode):
        raise ValueError('continuity backing must be a regular file')
    return workspace


def atomic_continuity(workspace, content):
    """Replace only the known backing file; never follow agent-created links."""
    if type(content) is not str or len(content.encode('utf-8')) > 32768:
        raise ValueError('continuity content limit')
    workspace = Path(workspace)
    checked_run(workspace.parent)
    if workspace.name != 'workspace' or workspace.resolve(strict=True) != workspace:
        raise ValueError('workspace path alias')
    directory = workspace / '.continuity'
    if directory.resolve(strict=True) != directory:
        raise ValueError('continuity directory alias')
    # Directory descriptors and O_NOFOLLOW prevent writes through a malicious
    # guest file symlink. os.replace overwrites that link, never its target.
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temp = '.pending-' + uuid.uuid4().hex
    payload = content.encode('utf-8')
    try:
        out = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(out, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, 'Continuity.md', src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(temp, dir_fd=fd)
        except FileNotFoundError:
            pass
        os.close(fd)
    return {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


def prepare_workspace(run, files):
    """Create a fresh run from a trusted text mapping. Existing runs are refused.

    Subsequent invocations reuse this workspace; parent refreshes only trusted
    live files and never calls this function to clear existing notes/programs.
    """
    run = checked_run(run, must_exist=False)
    RUNTIME_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if RUNTIME_ROOT.stat().st_uid != os.getuid():
        raise ValueError('runtime root owner mismatch')
    RUNTIME_ROOT.chmod(0o700)
    run.mkdir(mode=0o700)
    workspace = run / 'workspace'
    workspace.mkdir(mode=0o700)
    for name in ('notes', 'programs', '.continuity'):
        (workspace / name).mkdir(mode=0o700)
    for name, content in files.items():
        relative = PurePosixPath(name)
        if (relative.is_absolute() or '..' in relative.parts or '\\' in name or
                not relative.parts or relative.parts[0] == '.continuity' or type(content) is not str):
            raise ValueError('invalid trusted workspace file')
        if name == 'Continuity.md':
            continue
        path = workspace.joinpath(*relative.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
    atomic_continuity(workspace, files.get('Continuity.md', ''))
    (workspace / 'Continuity.md').symlink_to(CONTINUITY_LINK)
    validate_workspace(workspace)
    return {'run': str(run), 'workspace': str(workspace),
            'continuity_backing': str(workspace / CONTINUITY_LINK),
            'continuity_link': CONTINUITY_LINK, 'persistent_root': str(RUNTIME_ROOT)}
