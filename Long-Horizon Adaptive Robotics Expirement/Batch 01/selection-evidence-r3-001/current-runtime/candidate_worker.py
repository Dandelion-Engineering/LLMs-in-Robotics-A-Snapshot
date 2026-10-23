"""One stdlib-only candidate inside the OS sandbox; JSON-line IPC only.

The trusted wrapper applies hard rlimits and a no-new-privileges seccomp filter
before importing candidate code. Bubblewrap supplies filesystem/namespaces.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import zlib


def restrict(limits: dict) -> dict:
    hard_limits = {
        resource.RLIMIT_CPU: int(limits["cpu_seconds"]),
        resource.RLIMIT_AS: int(limits["memory_bytes"]),
        resource.RLIMIT_NPROC: 1,
        resource.RLIMIT_FSIZE: int(limits["file_bytes"]),
        resource.RLIMIT_NOFILE: int(limits["open_files"]),
        resource.RLIMIT_CORE: 0,
    }
    for key, value in hard_limits.items():
        resource.setrlimit(key, (value, value))
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "Cannot set no_new_privs")
    seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    seccomp.seccomp_rule_add.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("Cannot create seccomp filter")
    # NPROC is not sufficient on all UID/user-namespace configurations. Deny
    # child/thread creation directly as well, and deny executing other binaries.
    blocked = ["fork", "vfork", "clone", "clone3", "execve", "execveat",
               "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
               "mount", "umount2", "pivot_root", "chroot", "unshare", "setns",
               "ptrace", "process_vm_readv", "process_vm_writev", "perf_event_open",
               "bpf", "userfaultfd", "keyctl", "add_key", "request_key", "io_uring_setup",
               "reboot", "kexec_load", "kexec_file_load", "init_module", "finit_module",
               "delete_module", "swapon", "swapoff", "acct", "settimeofday", "clock_settime"]
    installed = []
    try:
        for name in blocked:
            number = seccomp.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number < 0:
                raise RuntimeError("Required syscall is unknown: " + name)
            status = seccomp.seccomp_rule_add(context, 0x80000000, number, 0)  # KILL_PROCESS, not catchable EPERM
            if status != 0:
                raise OSError(-status, "Cannot deny " + name)
            installed.append(name)
        status = seccomp.seccomp_load(context)
        if status != 0:
            raise OSError(-status, "Cannot install seccomp")
    finally:
        seccomp.seccomp_release(context)
    return {"seccomp_denied_syscalls": installed,
            "seccomp_denial_action":"KILL_PROCESS (SIGSYS); denied calls cannot be caught and relabeled successful",
            "hard_limits": {str(key): value for key, value in hard_limits.items()},
            "pid": os.getpid(), "uid": os.getuid(), "cwd": os.getcwd()}


def install_contract_audit():
    """Fail-closed API audit for the frozen Python/DSL runtime.

    This records Python-level attempts before exit; kernel namespaces/seccomp
    are still the access boundary. It is not a promise to audit arbitrary
    native machine code or a replacement for the restricted frozen DSL.
    """
    def fail(event, reason):
        message={'event':event,'reason':reason,'classification':'candidate_contract_violation'}
        os.write(2,('CANDIDATE_CONTRACT_VIOLATION '+json.dumps(message)+'\n').encode())
        os._exit(77)

    def permitted(path, write=False):
        if isinstance(path,int):return True  # only inherited stdio or already admitted descriptors
        if not isinstance(path,(str,bytes,os.PathLike)):return False
        resolved=os.path.realpath(os.fsdecode(path))
        roots=('/work','/tmp') if write else ('/work','/tmp','/code','/usr')
        return any(resolved==root or resolved.startswith(root+'/') for root in roots) or (not write and resolved in ('/dev/urandom','/dev/null'))

    def audit(event,args):
        if event=='open':
            path,mode,flags=args
            write=bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if not permitted(path,write):fail(event,'path outside permitted '+('writable' if write else 'readable')+' namespace: '+str(path))
        elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod','os.chown','os.truncate','os.utime'):
            if not permitted(args[0],True):fail(event,'mutation outside private storage')
        elif event in ('os.rename','os.link'):
            if not all(permitted(path,True) for path in args[:2]):fail(event,'cross-boundary filesystem mutation')
        elif event=='os.symlink':
            if not permitted(args[1],True) or not permitted(args[0]):fail(event,'symlink outside permitted namespace')
        elif event.startswith('socket.') or event in ('os.fork','os.forkpty','os.exec','os.posix_spawn','subprocess.Popen','ctypes.dlopen'):
            fail(event,'forbidden network/process/native-library operation')
    sys.addaudithook(audit)


def encode_candidate_message(message: dict, limit: int) -> bytes:
    """Lossless context-text compaction on IPC only; policy/disk bytes unchanged.

    Enforce the original uncompressed reply cap before compressing. The trusted
    receiver restores the exact UTF-8 text before evidence or consumers see it.
    The combined output quota counts actual compressed pipe bytes.
    """
    def encode(value):return json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii')+b'\n'
    original=encode(message)
    if len(original)>limit:raise ValueError('Candidate response exceeds the line limit')
    events=message.get('events')
    if not isinstance(events,list):return original
    compact=[];changed=False
    for event in events:
        if not isinstance(event,dict):compact.append(event);continue
        if '_context_transport' in event:raise ValueError('Candidate event uses a reserved transport field')
        text=event.get('content_utf8')
        if event.get('type') not in ('context_read','context_write') or not isinstance(text,str):
            compact.append(event);continue
        raw=text.encode('utf-8')
        if len(raw)<1024:compact.append(event);continue
        checksum=hashlib.sha256(raw).hexdigest()
        if type(event.get('byte_count')) is not int or event['byte_count']!=len(raw) or event.get('sha256')!=checksum:
            raise ValueError('Context event bytes differ from its declared length/hash')
        packed={key:value for key,value in event.items() if key!='content_utf8'}
        packed['_context_transport']={'codec':'zlib-base64-v1','decoded_bytes':len(raw),'sha256':checksum,
                                     'data':base64.b64encode(zlib.compress(raw,level=3)).decode('ascii')}
        if len(encode(packed))<len(encode(event)):compact.append(packed);changed=True
        else:compact.append(event)
    if not changed:return original
    wire=encode({**message,'events':compact})
    if len(wire)>limit:raise ValueError('Compacted candidate response exceeds the line limit')
    return wire


def emit(message: dict, limit: int) -> None:
    usage=resource.getrusage(resource.RUSAGE_SELF)
    message={**message,'runtime_usage':{'source':'fixed candidate wrapper getrusage(RUSAGE_SELF)',
             'user_cpu_s':usage.ru_utime,'system_cpu_s':usage.ru_stime,'maximum_rss_bytes':usage.ru_maxrss*1024,
             'input_blocks':usage.ru_inblock,'output_blocks':usage.ru_oublock,
             'scope':'this Linux candidate incarnation; final partial interval may be missing after abrupt termination'}}
    sys.stdout.buffer.write(encode_candidate_message(message,limit))
    sys.stdout.buffer.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", required=True)
    parser.add_argument("--persistent", choices=["0", "1"], required=True)
    parser.add_argument("--limits", required=True)
    args = parser.parse_args()
    limits = json.loads(args.limits)
    line_limit = int(limits["line_bytes"])
    try:
        restrictions = restrict(limits)
        install_contract_audit()
        spec = importlib.util.spec_from_file_location("candidates", "/code/candidates.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("Candidate module is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules["candidates"] = module
        spec.loader.exec_module(module)
        candidate = module.Candidate(args.kind, Path("/work"), args.persistent == "1")
        emit({"type": "ready", "restrictions": restrictions}, line_limit)
        while True:
            line = sys.stdin.buffer.readline(line_limit + 1)
            if not line:
                return 0
            if len(line) > line_limit or not line.endswith(b"\n"):
                raise ValueError("Invalid or oversized IPC input line")
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("IPC request must be an object")
            kind = request.get("type")
            response = None
            if kind == "step":
                response = candidate.step(request["packet"])
                if not isinstance(response, dict) or response.get("type") not in {"model", "action", "wait", "sensor_request"}:
                    raise ValueError("Candidate.step must return a model, action, sensor_request or wait object")
            elif kind == "model_response":
                candidate.accept_model(request["text"])
            elif kind == "feedback":
                candidate.accept_feedback(request["feedback"])
            elif kind == "sensor_response":
                candidate.accept_sensor(request["response"])
            elif kind == 'snapshot_resources':
                pass
            else:
                raise ValueError("Unknown IPC request type")
            events = candidate.drain_events()
            if not isinstance(events, list):
                raise ValueError("Candidate.drain_events must return a list")
            emit({"type": kind, "response": response, "events": events}, line_limit)
    except BaseException as exc:
        # Candidate paths contain no evaluator data. Report the actual exception
        # without returning a traceback of trusted host process state.
        try:
            emit({"type": "error", "error": type(exc).__name__, "message": str(exc)[:2000]}, line_limit)
        except BaseException:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
