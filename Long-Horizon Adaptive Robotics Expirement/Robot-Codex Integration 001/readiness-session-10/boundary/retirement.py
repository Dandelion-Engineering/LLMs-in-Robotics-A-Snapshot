"""Bounded retirement of one recorded WSL/bubblewrap invocation.

No process-name search or process-group kill is used. A forced Linux signal is
sent through a pidfd only after the recorded PID/start time matches. Bubblewrap
startup metadata provides its child PID namespace even after a quick normal
exit; an empty /proc match set for that namespace is required for success.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time


_CONTROL = r'''
import json,os,pathlib,re,signal,sys,time
request=json.loads(sys.argv[1]); root=pathlib.Path('/var/tmp/robot-codex-session10')
path=pathlib.Path(request['identity_path'])
if (path.is_symlink() or path.resolve(strict=True)!=path or
    path.parent.parent!=root or root.resolve(strict=True)!=root):
    raise SystemExit('Invalid recorded identity location')
raw=path.read_bytes()
if len(raw)>8192:raise SystemExit('Identity record exceeds bound')
identity=json.loads(raw);pid=identity.get('pid');ticks=str(identity.get('start_ticks',''))
if type(pid) is not int or pid<2 or not ticks.isdecimal():
    raise SystemExit('Invalid recorded process identity')
expected=request.get('expected')
if expected and (pid!=expected['pid'] or ticks!=str(expected['start_ticks'])):
    raise SystemExit('Recorded process identity changed')

def stat_for(number):
    try:
        text=(pathlib.Path('/proc')/str(number)/'stat').read_text()
        tail=text.rsplit(')',1)[1].split()
        return {'start_ticks':tail[19],'state':tail[0]}
    except FileNotFoundError:return None

namespaces=set(request.get('namespace_ids',[])); info=None; info_problem=None
info_path=identity.get('bubblewrap_info')
if info_path:
    ip=pathlib.Path(info_path)
    if ip.is_symlink() or ip.parent.resolve(strict=True)!=path.parent.resolve(strict=True):
        raise SystemExit('Invalid bubblewrap information location')
    try:
        data=ip.read_bytes()
        if len(data)>65536:raise ValueError('startup information exceeds bound')
        info=json.loads(data)
        namespace=info.get('pid-namespace')
        if type(namespace) is int and namespace>0:namespaces.add(namespace)
        elif isinstance(namespace,str) and namespace.isdecimal():namespaces.add(int(namespace))
    except (FileNotFoundError,ValueError) as error:
        info_problem=type(error).__name__

host_namespace=os.readlink('/proc/self/ns/pid')
if any(type(n) is not int or n<1 or f'pid:[{n}]'==host_namespace for n in namespaces):
    raise SystemExit('Refusing host or invalid PID namespace identity')
current=stat_for(pid)
matches=current is not None and current['start_ticks']==ticks
kill_sent=False;kill_reason=None
if request['action']=='kill':
    if not matches:kill_reason='recorded process absent or PID reused; no signal sent'
    else:
        fd=None
        try:
            fd=os.pidfd_open(pid,0)
            checked=stat_for(pid)
            if checked is None or checked['start_ticks']!=ticks:
                kill_reason='identity changed before pidfd signal; no signal sent'
            else:
                signal.pidfd_send_signal(fd,signal.SIGKILL)
                kill_sent=True
        except ProcessLookupError:
            kill_reason='recorded process exited before signal'
        finally:
            if fd is not None:os.close(fd)
elif request['action']!='inspect':raise SystemExit('Unknown retirement action')

# If startup namespace IDs are unavailable, positively capture only namespaces
# beneath the still-matching outer process. This is a compatibility fallback;
# absence of both sources never qualifies a namespace as empty.
current=stat_for(pid)
matches=current is not None and current['start_ticks']==ticks
if matches and not namespaces:
    pending=[pid];seen=set()
    while pending:
        number=pending.pop()
        if number in seen:continue
        seen.add(number)
        if len(seen)>256:raise SystemExit('Descendant observation exceeds bound')
        base=pathlib.Path('/proc')/str(number)
        try:
            ns=os.readlink(base/'ns/pid')
            if ns!=host_namespace:
                match=re.fullmatch(r'pid:\[(\d+)\]',ns)
                if match:namespaces.add(int(match.group(1)))
            for task in (base/'task').iterdir():
                try:pending.extend(int(v) for v in (task/'children').read_text().split())
                except FileNotFoundError:pass
        except FileNotFoundError:pass

members=[];denied=0
entries=[p for p in pathlib.Path('/proc').iterdir() if p.name.isdecimal()]
if len(entries)>8192:raise SystemExit('Process metadata inventory exceeds bound')
for entry in entries:
    try:
        ns=os.readlink(entry/'ns/pid')
        match=re.fullmatch(r'pid:\[(\d+)\]',ns)
        if match and int(match.group(1)) in namespaces:
            current_member=stat_for(int(entry.name))
            if current_member:members.append({'pid':int(entry.name),'namespace_id':int(match.group(1)),**current_member})
    except FileNotFoundError:pass
    except PermissionError:denied+=1
current=stat_for(pid)
same=current is not None and current['start_ticks']==ticks
print(json.dumps({'identity':{'pid':pid,'start_ticks':ticks},
    'outer_same_process':same,'outer_state':current['state'] if same else None,
    'outer_pid_reused':current is not None and not same,
    'namespace_ids':sorted(namespaces),'namespace_members':members,
    'namespace_evidence_available':bool(namespaces),'bubblewrap_info':info,
    'bubblewrap_info_problem':info_problem,'unreadable_other_process_namespace_links':denied,
    'kill_sent':kill_sent,'kill_reason':kill_reason,
    'retired':not same and bool(namespaces) and not members}))
'''


async def _control(identity_path: str, action: str, baseline: dict | None = None) -> dict:
    request = {'identity_path': str(identity_path), 'action': action}
    if baseline:
        request['expected'] = baseline['identity']
        request['namespace_ids'] = baseline['namespace_ids']
    child = await asyncio.create_subprocess_exec(
        'wsl.exe', '--distribution', 'Ubuntu-24.04', '--exec',
        '/usr/bin/python3', '-I', '-B', '-c', _CONTROL, json.dumps(request),
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(child.communicate(), 5)
    except BaseException:
        if child.returncode is None:
            child.kill()
            await asyncio.wait_for(child.wait(), 3)
        raise
    if child.returncode:
        raise RuntimeError('Recorded WSL retirement control failed: ' +
                           stderr.decode(errors='replace')[:2000])
    if len(stdout) > 512 * 1024:
        raise RuntimeError('Retirement metadata exceeded output bound')
    return json.loads(stdout)


async def retire(process, identity_path, evidence_path):
    """Retire one asyncio WSL child after its caller has closed stdin.

    Returns the durable evidence dictionary only after original Linux identity,
    recorded guest namespace, and Windows transport process have all retired.
    A PID mismatch is never signalled. Unknown or surviving Linux state raises.
    """
    evidence_path = Path(evidence_path)
    if evidence_path.exists():
        raise FileExistsError('Refusing to overwrite retirement evidence')
    result = {'qualified': False, 'identity_path': str(identity_path),
              'normal_wait_timed_out': False, 'windows_wrapper_killed_after_linux_retired': False,
              'observations': []}
    started = time.monotonic()
    baseline = None
    try:
        # Capture namespace identity before waiting; bwrap's sidecar also survives
        # a process that exited between stdin close and this first observation.
        baseline = await _control(str(identity_path), 'inspect')
        result['before_wait'] = baseline
        try:
            await asyncio.wait_for(process.wait(), 5)
        except asyncio.TimeoutError:
            result['normal_wait_timed_out'] = True
        observed = await _control(str(identity_path), 'inspect', baseline)
        result['observations'].append(observed)
        if observed['outer_same_process']:
            result['forced_retirement'] = await _control(str(identity_path), 'kill', baseline)
        deadline = time.monotonic() + 6
        while True:
            observed = await _control(str(identity_path), 'inspect', baseline)
            result['observations'].append(observed)
            if observed['retired']:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Original Linux process or its PID namespace did not retire, or namespace evidence is missing')
            await asyncio.sleep(.1)
        # Only this exact asyncio-owned Windows transport handle may be killed,
        # and only after the Linux boundary is positively known to be retired.
        if process.returncode is None:
            try:
                await asyncio.wait_for(process.wait(), 2)
            except asyncio.TimeoutError:
                process.kill()
                result['windows_wrapper_killed_after_linux_retired'] = True
                await asyncio.wait_for(process.wait(), 3)
        result['windows_exit_code'] = process.returncode
        result['qualified'] = True
        return result
    except BaseException as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)[:2000]}
        raise
    finally:
        result['elapsed_seconds'] = round(time.monotonic() - started, 4)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
