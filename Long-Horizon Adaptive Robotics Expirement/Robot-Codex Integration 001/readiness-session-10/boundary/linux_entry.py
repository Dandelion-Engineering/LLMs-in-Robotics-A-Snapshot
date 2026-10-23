"""Trusted durable namespace entry; no user-selected runtime root."""
import argparse
import json
import os
from pathlib import Path
import resource
import stat
from namespace import command
from runtime_layout import validate_workspace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['canary', 'executor', 'codehost-canary', 'codehost'])
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--socket', required=True)
    parser.add_argument('--codex')
    parser.add_argument('--codehost')
    parser.add_argument('--identity-file')
    args = parser.parse_args()
    workspace = validate_workspace(args.workspace)
    sock = Path(args.socket)
    if sock.parent != workspace.parent or sock.resolve(strict=True) != sock or not stat.S_ISSOCK(sock.stat().st_mode):
        raise SystemExit('Socket outside exact invocation runtime')
    info_fd = None
    if args.identity_file:
        identity = Path(args.identity_file)
        if identity.parent != workspace.parent or identity.parent.resolve(strict=True) != identity.parent:
            raise SystemExit('Invalid process identity path')
        info_path = identity.with_name(identity.name + '.bwrap-info.json')
        info_fd = os.open(info_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.set_inheritable(info_fd, True)
        with identity.open('x') as file:
            stat_tail = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
            json.dump({'pid': os.getpid(), 'start_ticks': stat_tail[19],
                       'bubblewrap_info': str(info_path)}, file)
            file.flush()
            os.fsync(file.fileno())
    # Inherited per-process limits, not a claim of cgroup/whole-host accounting.
    # V8 reserves a large address region, so RLIMIT_AS is deliberately not used.
    for kind, limit in ((resource.RLIMIT_CORE, 0), (resource.RLIMIT_NOFILE, 1024),
                        (resource.RLIMIT_FSIZE, 64 * 1024 * 1024), (resource.RLIMIT_CPU, 1800)):
        resource.setrlimit(kind, (limit, limit))
    argv = command(workspace, sock, Path(__file__).resolve().parent, args.codex, args.codehost)
    if info_fd is not None:
        argv[1:1] = ['--info-fd', str(info_fd)]
    os.execv(argv[0], argv + [args.mode])


if __name__ == '__main__':
    main()
