"""Trusted namespace entry point. Parent supplies only validated task paths."""
import argparse
from pathlib import Path
import os
import sys
import json
from namespace import command

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['canary', 'executor', 'codehost-canary', 'codehost'])
parser.add_argument('--workspace', required=True)
parser.add_argument('--socket', required=True)
parser.add_argument('--codex')
parser.add_argument('--codehost')
parser.add_argument('--identity-file')
args = parser.parse_args()
for value in (args.workspace, args.socket):
    if not Path(value).resolve(strict=True).is_relative_to('/tmp/robot-codex-session9'):
        raise SystemExit('Not a task scratch path')
info_fd = None
if args.identity_file:
    identity = Path(args.identity_file)
    if not identity.parent.resolve(strict=True).is_relative_to('/tmp/robot-codex-session9'):
        raise SystemExit('Invalid process identity path')
    # Capture bwrap's own startup metadata outside all guest mounts. Unlike the
    # pre-exec /proc/self/ns/pid, this records the new sandbox PID namespace.
    info_path = identity.with_name(identity.name + '.bwrap-info.json')
    info_fd = os.open(info_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.set_inheritable(info_fd, True)
    with identity.open('x') as file:
        stat_tail = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
        json.dump({'pid': os.getpid(), 'start_ticks': stat_tail[19],
                   'bubblewrap_info': str(info_path)}, file)
argv = command(args.workspace, args.socket, Path(__file__).resolve().parent, args.codex, args.codehost)
if info_fd is not None:
    argv[1:1] = ['--info-fd', str(info_fd)]
argv += [args.mode]
os.execv(argv[0], argv)
