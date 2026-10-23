"""Asynchronous resource observations, never quota enforcement.

Start ResourceSampler before the episode clock and close it after physics ends.
The physics thread may read latest()/summary(); it never executes a subprocess.
GPU values describe the whole device, including display/other applications.
Candidate WSL resource usage and energy are explicitly unavailable here.

Primary metric definitions:
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes
https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex
https://docs.nvidia.com/deploy/nvidia-smi/index.html
"""
from __future__ import annotations

import copy
import csv
import ctypes
from datetime import datetime,timezone
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

GIB=1024**3


def utc():return datetime.now(timezone.utc).isoformat()


def missing_process(pid,reason):
    return {'pid':pid,'cpu_total_s':None,'rss_bytes':None,'peak_rss_bytes':None,
            'private_commit_bytes':None,'creation_time_100ns':None,'missing_reason':reason}


def windows_process_sample(pid):
    """Read only the supplied process; no enumeration, signal or PID probing."""
    if pid is None:return missing_process(None,'No owned process is running')
    if os.name!='nt':return missing_process(pid,'Windows process API is unavailable on this platform')
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    kernel.GetProcessTimes.restype=wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    handle=kernel.OpenProcess(0x0400|0x0010,False,int(pid))
    if not handle:return missing_process(pid,f'OpenProcess failed: Windows error {ctypes.get_last_error()}')
    result=missing_process(pid,None);problems=[]
    def ticks(value):return (int(value.dwHighDateTime)<<32)|int(value.dwLowDateTime)
    try:
        created,exited,kernel_time,user_time=(wintypes.FILETIME() for _ in range(4))
        if kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(kernel_time),ctypes.byref(user_time)):
            result.update(cpu_total_s=(ticks(kernel_time)+ticks(user_time))/10_000_000.,creation_time_100ns=ticks(created))
        else:problems.append(f'GetProcessTimes failed: Windows error {ctypes.get_last_error()}')
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),ctypes.sizeof(counters)):
            result.update(rss_bytes=int(counters.WorkingSetSize),peak_rss_bytes=int(counters.PeakWorkingSetSize),private_commit_bytes=int(counters.PrivateUsage))
        else:problems.append(f'GetProcessMemoryInfo failed: Windows error {ctypes.get_last_error()}')
    finally:kernel.CloseHandle(handle)
    result['missing_reason']='; '.join(problems) if problems else None
    return result


def parse_gpu_csv(text):
    rows=[]
    names=('index','name','memory_total_mib','memory_used_mib','utilization_gpu_percent','temperature_c')
    for fields in csv.reader(io.StringIO(text)):
        if not fields or all(not x.strip() for x in fields):continue
        if len(fields)!=len(names):raise ValueError(f'Expected {len(names)} GPU CSV fields, received {len(fields)}')
        row={'scope':'entire physical GPU including OS and other applications','missing_reasons':{}}
        for name,value in zip(names,fields):
            value=value.strip()
            if name=='name':row[name]=value;continue
            try:
                number=float(value)
                if not math.isfinite(number):raise ValueError('nonfinite')
                row[name]=int(number) if name=='index' else number
            except ValueError:
                row[name]=None;row['missing_reasons'][name]='Driver value unavailable: '+value
        for source,target in (('memory_total_mib','memory_total_bytes'),('memory_used_mib','memory_used_bytes')):
            row[target]=None if row[source] is None else int(row[source]*1024**2)
        rows.append(row)
    return rows


def gpu_sample(timeout_s=2.):
    executable=shutil.which('nvidia-smi')
    if not executable:return {'devices':None,'missing_reason':'nvidia-smi was not found on PATH'}
    command=[executable,'--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits']
    try:
        reply=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout_s,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if reply.returncode!=0:return {'devices':None,'missing_reason':f'nvidia-smi exited {reply.returncode}: {reply.stderr[:500]}'}
        rows=parse_gpu_csv(reply.stdout)
        return {'devices':rows if rows else None,'missing_reason':None if rows else 'nvidia-smi returned no devices'}
    except Exception as exc:return {'devices':None,'missing_reason':f'{type(exc).__name__}: {exc}'}


class ResourceSampler:
    def __init__(self,path,*,model_pid=None,period_s=5.,gpu_timeout_s=2.,process_reader=windows_process_sample,gpu_reader=gpu_sample):
        if period_s<=0 or gpu_timeout_s<=0:raise ValueError('Sampling intervals must be positive')
        self.path=Path(path);self.model_pid=model_pid;self.period_s=float(period_s);self.gpu_timeout_s=float(gpu_timeout_s)
        self.process_reader=process_reader;self.gpu_reader=gpu_reader;self.harness_pid=os.getpid()
        self._stop=threading.Event();self._thread=None;self._stream=None;self._latest=None;self._previous={}
        self._sample_count=0;self._failure=None;self._maxima={};self._started=None
    def start(self):
        if self._thread is not None:raise RuntimeError('ResourceSampler cannot be restarted')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._stream=self.path.open('x',encoding='utf-8',newline='\n')
        self._started=time.perf_counter();self._thread=threading.Thread(target=self._run,name='robot-resource-sampler',daemon=True)
        self._thread.start();return self
    def _process(self,role,pid,captured):
        try:sample=self.process_reader(pid)
        except Exception as exc:sample=missing_process(pid,f'{type(exc).__name__}: {exc}')
        sample={**sample,'scope':'single owned Windows process; not descendants','cpu_core_equivalents':None,
                'cpu_interval_s':None,'cpu_rate_missing_reason':'No prior matching process sample'}
        previous=self._previous.get(role)
        identity=(sample.get('pid'),sample.get('creation_time_100ns'))
        cpu=sample.get('cpu_total_s')
        if cpu is not None and previous and previous['identity']==identity:
            interval=captured-previous['captured'];delta=cpu-previous['cpu']
            if interval>0 and delta>=0:
                sample.update(cpu_core_equivalents=delta/interval,cpu_interval_s=interval,cpu_rate_missing_reason=None)
            else:sample['cpu_rate_missing_reason']='CPU counter or observation clock did not advance consistently'
        if cpu is not None:self._previous[role]={'identity':identity,'captured':captured,'cpu':cpu}
        else:self._previous.pop(role,None)
        return sample
    def _capture(self):
        started=time.perf_counter();timestamp=utc()
        try:pid=self.model_pid() if callable(self.model_pid) else self.model_pid
        except Exception as exc:pid=None;pid_error=f'Model PID supplier failed: {exc}'
        else:pid_error=None
        harness=self._process('harness',self.harness_pid,started)
        model=self._process('model',pid,time.perf_counter())
        if pid_error:model['missing_reason']=pid_error
        try:gpu=self.gpu_reader(timeout_s=self.gpu_timeout_s)
        except Exception as exc:gpu={'devices':None,'missing_reason':f'{type(exc).__name__}: {exc}'}
        checks={'enforced':False,'harness_rss_budget_bytes':4*GIB,'model_private_commit_budget_bytes':12*GIB,'candidate_gpu_budget_bytes':12*GIB,
                'harness_observed_rss_exceeds_budget':None if harness['rss_bytes'] is None else harness['rss_bytes']>4*GIB,
                'model_observed_private_commit_exceeds_budget':None if model['private_commit_bytes'] is None else model['private_commit_bytes']>12*GIB,
                'complete_candidate_ram_bytes':None,'complete_candidate_ram_missing_reason':'Linux incarnation high-water marks are reported separately by supervisor; not simultaneous with these Windows samples',
                'candidate_gpu_usage_bytes':None,'candidate_gpu_missing_reason':'Whole-device usage cannot attribute memory to this candidate',
                'interpretation':'This sampler observes only. Windows model job and Linux candidate rlimits enforce their separately declared bounds; GPU attribution is unavailable here'}
        return {'schema_version':'robot-resource-samples-1.0','captured_at':timestamp,'capture_monotonic_s':started,
                'wall_since_sampler_start_s':started-self._started,'capture_duration_s':time.perf_counter()-started,
                'harness':harness,'model':model,'gpu':gpu,'logical_cpu_count':os.cpu_count(),
                'cpu_rate_definition':'CPU seconds / wall interval; 1.0 means one fully occupied logical CPU',
                'candidate_linux':{'cpu_s':None,'rss_bytes':None,'missing_reason':'Obtain separately timed incarnation observations from supervisor candidate_usage'},
                'energy_joules':None,'energy_missing_reason':'Energy was not measured; instantaneous utilization is not energy',
                'budget_observations':checks}
    def _run(self):
        deadline=time.perf_counter()
        try:
            while not self._stop.is_set():
                sample=self._capture()
                self._stream.write(json.dumps(sample,allow_nan=False,separators=(',',':'))+'\n');self._stream.flush()
                self._latest=sample;self._sample_count+=1
                for role in ('harness','model'):
                    value=sample[role]['rss_bytes']
                    if value is not None:self._maxima[role+'_sampled_peak_rss_bytes']=max(value,self._maxima.get(role+'_sampled_peak_rss_bytes',value))
                deadline+=self.period_s
                if deadline<time.perf_counter():deadline=time.perf_counter()+self.period_s
                self._stop.wait(max(0.,deadline-time.perf_counter()))
        except BaseException as exc:self._failure=f'{type(exc).__name__}: {exc}'
        finally:
            try:self._stream.close()
            except Exception as exc:self._failure=(self._failure or '')+'; stream close: '+str(exc)
    def latest(self):
        """Nonblocking copy of the last finished observation, or None."""
        return copy.deepcopy(self._latest)
    def summary(self):
        return {'path':str(self.path),'sample_count':self._sample_count,'period_s':self.period_s,'failure':self._failure,
                'sampler_stopped':self._thread is not None and not self._thread.is_alive(),
                'sampled_peaks':dict(self._maxima),'peaks_are_lower_bounds':True,
                'resource_caps_enforced':False,'energy_joules':None,'energy_missing_reason':'Unmeasured',
                'limitations':['GPU metrics cover all applications','Windows RSS does not include candidate Linux process','Five-second sampling may miss transient peaks']}
    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.gpu_timeout_s+3.)
            if self._thread.is_alive():
                self._failure='Sampler did not stop within bounded close timeout'
                raise TimeoutError(self._failure)
    stop=close
    def __enter__(self):return self.start()
    def __exit__(self,exc_type,exc,tb):self.close()
