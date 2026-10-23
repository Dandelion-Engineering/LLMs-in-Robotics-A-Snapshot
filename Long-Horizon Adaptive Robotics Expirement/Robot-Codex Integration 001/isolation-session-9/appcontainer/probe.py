"""Bounded task-owned AppContainer canary; no model, credentials, or real robot.

Creates a unique profile, gives its package SID access only to task-created
runtime/read-only and mailbox/write directories, launches one CLR canary process
with zero capabilities, and deletes the profile. Scratch ACLs alone are changed.
Normal AppContainer has OS-wide default resources: this is not a full-machine
filesystem allowlist proof. The mailbox is an illustrative fixed-operation broker.
"""
import ctypes as C
from ctypes import wintypes as W
import http.client
import http.server
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent
RUN = HERE / ('attempt-' + time.strftime('%Y%m%d-%H%M%S'))
RUN.mkdir()
LOG = RUN / 'events.jsonl'
def event(kind, **data):
    row = dict(time=time.time(), kind=kind, **data)
    with LOG.open('a', encoding='utf-8') as f: f.write(json.dumps(row) + '\n')
    print(json.dumps(row), flush=True)

k = C.WinDLL('kernel32', use_last_error=True)
a = C.WinDLL('advapi32', use_last_error=True)
u = C.WinDLL('userenv', use_last_error=True)
def api(dll, name, result, args):
    f = getattr(dll, name); f.restype = result; f.argtypes = args; return f
ptr = C.c_void_p
CreateProfile = api(u, 'CreateAppContainerProfile', W.LONG, [W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,ptr,W.DWORD,C.POINTER(ptr)])
DeleteProfile = api(u, 'DeleteAppContainerProfile', W.LONG, [W.LPCWSTR])
ConvertSid = api(a, 'ConvertSidToStringSidW', W.BOOL, [ptr,C.POINTER(W.LPWSTR)])
FreeSid = api(a, 'FreeSid', ptr, [ptr])
LocalFree = api(k, 'LocalFree', ptr, [ptr])
GetCurrentProcess = api(k,'GetCurrentProcess',W.HANDLE,[])
OpenToken = api(a,'OpenProcessToken',W.BOOL,[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)])
GetToken = api(a,'GetTokenInformation',W.BOOL,[W.HANDLE,C.c_int,ptr,W.DWORD,C.POINTER(W.DWORD)])
CloseHandle = api(k,'CloseHandle',W.BOOL,[W.HANDLE])
ConvertSD = api(a,'ConvertStringSecurityDescriptorToSecurityDescriptorW',W.BOOL,[W.LPCWSTR,W.DWORD,C.POINTER(ptr),C.POINTER(W.DWORD)])
SetFileSecurity = api(a,'SetFileSecurityW',W.BOOL,[W.LPCWSTR,W.DWORD,ptr])

class STARTUPINFO(C.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),('x',W.DWORD),('y',W.DWORD),('xs',W.DWORD),('ys',W.DWORD),('xc',W.DWORD),('yc',W.DWORD),('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('reserved2n',W.WORD),('reserved2',ptr),('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class STARTUPINFOEX(C.Structure): _fields_=[('si',STARTUPINFO),('attrs',ptr)]
class PROCESS_INFORMATION(C.Structure): _fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
class CAPS(C.Structure): _fields_=[('sid',ptr),('caps',ptr),('count',W.DWORD),('reserved',W.DWORD)]
class BASIC_LIMIT(C.Structure):
    _fields_=[('per_process',C.c_int64),('per_job',C.c_int64),('flags',W.DWORD),('min_ws',C.c_size_t),('max_ws',C.c_size_t),('active',W.DWORD),('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class IO_COUNTERS(C.Structure): _fields_=[(x,C.c_uint64) for x in ('ro','wo','oo','rt','wt','ot')]
class EXT_LIMIT(C.Structure): _fields_=[('basic',BASIC_LIMIT),('io',IO_COUNTERS),('process_mem',C.c_size_t),('job_mem',C.c_size_t),('peak_process',C.c_size_t),('peak_job',C.c_size_t)]
InitAttr=api(k,'InitializeProcThreadAttributeList',W.BOOL,[ptr,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)])
UpdateAttr=api(k,'UpdateProcThreadAttribute',W.BOOL,[ptr,W.DWORD,C.c_size_t,ptr,C.c_size_t,ptr,ptr])
DeleteAttr=api(k,'DeleteProcThreadAttributeList',None,[ptr])
CreateProcess=api(k,'CreateProcessW',W.BOOL,[W.LPCWSTR,W.LPWSTR,ptr,ptr,W.BOOL,W.DWORD,ptr,W.LPCWSTR,C.POINTER(STARTUPINFOEX),C.POINTER(PROCESS_INFORMATION)])
CreateJob=api(k,'CreateJobObjectW',W.HANDLE,[ptr,W.LPCWSTR])
SetJob=api(k,'SetInformationJobObject',W.BOOL,[W.HANDLE,C.c_int,ptr,W.DWORD])
AssignJob=api(k,'AssignProcessToJobObject',W.BOOL,[W.HANDLE,W.HANDLE])
Resume=api(k,'ResumeThread',W.DWORD,[W.HANDLE])
Wait=api(k,'WaitForSingleObject',W.DWORD,[W.HANDLE,W.DWORD])
TerminateJob=api(k,'TerminateJobObject',W.BOOL,[W.HANDLE,W.UINT])
TerminateProcess=api(k,'TerminateProcess',W.BOOL,[W.HANDLE,W.UINT])
ExitCode=api(k,'GetExitCodeProcess',W.BOOL,[W.HANDLE,C.POINTER(W.DWORD)])
def checked(ok, name):
    if not ok: raise C.WinError(C.get_last_error())
    return ok
def sid_text(sid):
    s=W.LPWSTR(); checked(ConvertSid(sid,C.byref(s)), 'ConvertSid'); v=s.value; LocalFree(s); return v
def user_sid():
    tok=W.HANDLE(); checked(OpenToken(GetCurrentProcess(),8,C.byref(tok)), 'OpenToken')
    try:
        n=W.DWORD(); GetToken(tok,1,None,0,C.byref(n)); b=C.create_string_buffer(n.value)
        checked(GetToken(tok,1,b,n,C.byref(n)), 'GetToken')
        return sid_text(C.cast(b,C.POINTER(ptr))[0])
    finally: CloseHandle(tok)
def acl(path, sddl):
    # Never accept an ancestor, symlink or existing arbitrary path.
    path=path.resolve(); path.relative_to(RUN.resolve())
    sd=ptr(); checked(ConvertSD(sddl,1,C.byref(sd),None), 'ConvertSD')
    try: checked(SetFileSecurity(str(path),0x80000004|0x10,sd), 'SetFileSecurity')
    finally: LocalFree(sd)
    event('scratch_acl',path=str(path),sddl=sddl)

class Server(http.server.ThreadingHTTPServer): daemon_threads=True
def server(label, calls, connections, host='127.0.0.1'):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append({'service':label,'path':self.path})
            body=b'SYNTHETIC-LOOPBACK-REPLY'
            self.send_response(200); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self,*args): pass
    class CountingServer(Server):
        address_family=socket.AF_INET6 if ':' in host else socket.AF_INET
        def get_request(self):
            result=super().get_request(); connections.append(label); return result
    s=CountingServer((host,0),Handler)
    threading.Thread(target=s.serve_forever,daemon=True).start(); return s

def main():
    profile='Dandelion.Session9.Canary.'+uuid.uuid4().hex
    sid=ptr(); made=False; job=None; pi=PROCESS_INFORMATION(); attrs=None
    servers=[]; stop=threading.Event(); broker=None; calls=[]; connections=[]
    try:
        for name in ('probe.py','Canary.cs'): (RUN/name).write_bytes((HERE/name).read_bytes())
        event('start',profile=profile,source=str(Path(__file__).resolve()),python=sys.version,windows=list(sys.getwindowsversion()),source_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('probe.py','Canary.cs')})
        hr=CreateProfile(profile,profile,'Task-owned synthetic isolation canary',None,0,C.byref(sid))
        event('create_profile',hresult=hr)
        if hr<0: raise RuntimeError('CreateAppContainerProfile failed: '+hex(hr&0xffffffff))
        made=True; package=sid_text(sid); owner=user_sid()
        event('identity',package_sid=package,user_sid=owner,capabilities=[])
        runtime=RUN/'runtime'; mailbox=RUN/'mailbox'; protected=RUN/'protected'
        for p in (runtime,mailbox,protected): p.mkdir()
        (runtime/'read-canary.txt').write_text('SYNTHETIC-READ')
        (protected/'protected-canary.txt').write_text('SYNTHETIC-PROTECTED')
        exe=runtime/'Canary.exe'
        csc=Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        compile_command=[str(csc),'/nologo','/target:winexe','/platform:x64','/out:'+str(exe),str(HERE/'Canary.cs')]
        compile=subprocess.run(compile_command,capture_output=True,text=True,timeout=20)
        event('compile',command=compile_command,returncode=compile.returncode,stdout=compile.stdout,stderr=compile.stderr,exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest() if exe.exists() else None)
        if compile.returncode: raise RuntimeError('Compilation failed')
        base='D:P(A;OICI;FA;;;'+owner+')(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
        acl(runtime,base+'(A;OICI;FRFX;;;'+package+')S:(ML;OICI;NW;;;LW)')
        acl(mailbox,base+'(A;OICI;0x1301bf;;;'+package+')S:(ML;OICI;NW;;;LW)')
        acl(protected,base+'S:(ML;OICI;NW;;;LW)')
        # Explicit files get exact grants too; SetFileSecurity inheritance is not
        # assumed to have propagated to files created before parent ACL change.
        for p in runtime.iterdir(): acl(p,base+'(A;;FRFX;;;'+package+')S:(ML;;NW;;;LW)')
        acl(protected/'protected-canary.txt',base+'S:(ML;;NW;;;LW)')
        allowed=server('approved-synthetic',calls,connections); denied=server('other-synthetic',calls,connections); v6=server('ipv6-synthetic',calls,connections,'::1'); servers=[allowed,denied,v6]
        for host,service in (('127.0.0.1',allowed),('127.0.0.1',denied),('::1',v6)):
            conn=http.client.HTTPConnection(host,service.server_port,timeout=1)
            try:
                conn.request('GET','/positive-control'); r=conn.getresponse()
                event('loopback_positive_control',host=host,port=service.server_port,status=r.status,body=r.read().decode())
            finally: conn.close()
        def serve_mailbox():
            for i in (1,2):
                request=mailbox/f'request{i}.json'
                deadline=time.monotonic()+15
                while not request.exists() and not stop.wait(.02) and time.monotonic()<deadline: pass
                if stop.is_set() or not request.exists(): return
                try:
                    if request.stat().st_size>1024: raise ValueError('oversized')
                    value=json.loads(request.read_text())
                    if value=={'op':'synthetic_ping','request_id':'fixed-1'}:
                        conn=http.client.HTTPConnection('127.0.0.1',allowed.server_port,timeout=1)
                        try:
                            conn.request('GET','/synthetic-ping'); r=conn.getresponse(); body=r.read(128).decode()
                            response={'ok':r.status==200,'body':body}
                        finally: conn.close()
                    else: response={'ok':False,'error':'operation_not_allowlisted'}
                    event('broker',request=value,response=response)
                    out=mailbox/f'response{i}.json'; temp=out.with_suffix('.tmp')
                    temp.write_text(json.dumps(response)); temp.replace(out)
                except Exception as e: event('broker_error',error=repr(e)); return
        broker=threading.Thread(target=serve_mailbox,daemon=True); broker.start()
        n=C.c_size_t(); InitAttr(None,1,0,C.byref(n)); attrs=C.create_string_buffer(n.value)
        checked(InitAttr(attrs,1,0,C.byref(n)), 'InitAttr')
        caps=CAPS(sid,None,0,0)
        checked(UpdateAttr(attrs,0,0x20009,C.byref(caps),C.sizeof(caps),None,None),'UpdateAttr')
        si=STARTUPINFOEX(); si.si.cb=C.sizeof(si); si.attrs=C.cast(attrs,ptr)
        cmd=C.create_unicode_buffer(subprocess.list2cmdline([str(exe),str(mailbox),str(runtime),str(protected),str(allowed.server_port),str(denied.server_port),str(v6.server_port)]))
        environment={'SystemRoot':os.environ['SystemRoot'],'WINDIR':os.environ['SystemRoot'],'SystemDrive':Path(os.environ['SystemRoot']).drive,'USERPROFILE':str(mailbox),'APPDATA':str(mailbox),'LOCALAPPDATA':str(mailbox),'TEMP':str(mailbox),'TMP':str(mailbox),'PATH':str(Path(os.environ['SystemRoot'])/'System32')}
        event('environment',values=environment)
        env=C.create_unicode_buffer('\0'.join(f'{key}={val}' for key,val in sorted(environment.items(),key=lambda item:item[0].upper()))+'\0\0')
        job=CreateJob(None,None); checked(job,'CreateJob'); limits=EXT_LIMIT(); limits.basic.flags=0x2000|0x8; limits.basic.active=1
        checked(SetJob(job,9,C.byref(limits),C.sizeof(limits)),'SetJob')
        flags=0x80000|0x400|0x4|0x08000000
        checked(CreateProcess(str(exe),cmd,None,None,False,flags,env,str(mailbox),C.byref(si),C.byref(pi)),'CreateProcess')
        event('created_suspended',pid=pi.pid,flags=flags)
        if not AssignJob(job,pi.process):
            error=C.get_last_error(); TerminateProcess(pi.process,97); raise C.WinError(error)
        if Resume(pi.thread)==0xffffffff: raise C.WinError(C.get_last_error())
        result=Wait(pi.process,15000)
        if result!=0: TerminateJob(job,98); Wait(pi.process,2000)
        code=W.DWORD(); checked(ExitCode(pi.process,C.byref(code)),'ExitCode')
        event('process_end',wait_result=result,exit_code=code.value)
        stop.set(); broker.join(2)
        child=(mailbox/'child.tsv').read_text() if (mailbox/'child.tsv').exists() else ''
        event('observations',child_tsv=child,server_calls=calls,server_connections=connections,protected_unchanged=(protected/'protected-canary.txt').read_text()=='SYNTHETIC-PROTECTED',readonly_write_exists=(runtime/'forbidden-write.txt').exists(),protected_write_exists=(protected/'forbidden-write.txt').exists())
        (RUN/'child-observations.tsv').write_text(child,encoding='utf-8')
        rows=dict(line.split('\t',1) for line in child.splitlines())
        checks={'process_completed':result==0 and code.value==0,'is_appcontainer':rows.get('TokenIsAppContainer')=='1','allowed_read':rows.get('allowed_read')=='READ:SYNTHETIC-READ','allowed_write':rows.get('allowed_write')=='WRITE_OK','outbound_access_denied':rows.get('outbound_documentation_ip_denied')=='SocketException:10013:AccessDenied','loopback_bounded_no_accept':connections==['approved-synthetic','other-synthetic','ipv6-synthetic','approved-synthetic'],'broker_allow':rows.get('broker_response_1')=='READ:{"ok": true, "body": "SYNTHETIC-LOOPBACK-REPLY"}','broker_reject':rows.get('broker_response_2')=='READ:{"ok": false, "error": "operation_not_allowlisted"}'}
        for name in ('readonly_write_denied','protected_read_denied','protected_write_denied'): checks[name]=rows.get(name,'').startswith('UnauthorizedAccessException:5:')
        event('bounded_checks',checks=checks,all_passed=all(checks.values()),qualification='synthetic_canary_only_loopback_timeout_is_not_errno_denial')
        if not all(checks.values()): return 2
    except Exception as e: event('error',error=repr(e),traceback=traceback.format_exc()); return 1
    finally:
        stop.set()
        if job: CloseHandle(job)
        if pi.thread: CloseHandle(pi.thread)
        if pi.process: CloseHandle(pi.process)
        if attrs: DeleteAttr(attrs)
        for s in servers: s.shutdown(); s.server_close()
        if made: event('delete_profile',hresult=DeleteProfile(profile))
        if sid: FreeSid(sid)
    return 0
if __name__=='__main__': sys.exit(main())
