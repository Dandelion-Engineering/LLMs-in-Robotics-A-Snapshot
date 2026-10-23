"""Direct, bounded ETW control with an explicit six-event allowlist; host scope requires approval."""
import ctypes as C
import json
from pathlib import Path
import uuid

ULONG=C.c_ulong
U64=C.c_ulonglong
IDS=(1038,1039,1040,1043,1044,1468)
PROVIDER='2f07e2ee-15db-40f1-90ef-9d7ba282188a'
HERE=Path(__file__).resolve().parent


class GUID(C.Structure):
    _fields_=[('data',C.c_ubyte*16)]
    @classmethod
    def make(cls,value):
        return cls.from_buffer_copy(uuid.UUID(str(value)).bytes_le)
    def text(self):
        return str(uuid.UUID(bytes_le=bytes(self.data)))


class EVENT_DESCRIPTOR(C.Structure):
    _fields_=[('Id',C.c_ushort),('Version',C.c_ubyte),('Channel',C.c_ubyte),
              ('Level',C.c_ubyte),('Opcode',C.c_ubyte),('Task',C.c_ushort),('Keyword',U64)]


class FILTER_DESCRIPTOR(C.Structure):
    _fields_=[('Ptr',U64),('Size',ULONG),('Type',ULONG)]


class PREDICATE(C.Structure):
    _fields_=[('FieldName',C.c_wchar_p),('CompareOp',C.c_ushort),('Value',C.c_wchar_p)]


class EVENT_IDS(C.Structure):
    _fields_=[('FilterIn',C.c_ubyte),('Reserved',C.c_ubyte),('Count',C.c_ushort),('Events',C.c_ushort*len(IDS))]


class ENABLE_PARAMS(C.Structure):
    _fields_=[('Version',ULONG),('EnableProperty',ULONG),('ControlFlags',ULONG),('SourceId',GUID),
              ('EnableFilterDesc',C.POINTER(FILTER_DESCRIPTOR)),('FilterDescCount',ULONG)]


class WNODE(C.Structure):
    _fields_=[('BufferSize',ULONG),('ProviderId',ULONG),('HistoricalContext',U64),('TimeStamp',U64),
              ('Guid',GUID),('ClientContext',ULONG),('Flags',ULONG)]


class PROPERTIES(C.Structure):
    _fields_=[('Wnode',WNODE)]+[(n,ULONG) for n in ('BufferSize','MinimumBuffers','MaximumBuffers','MaximumFileSize',
                'LogFileMode','FlushTimer','EnableFlags')]+[('AgeLimit',C.c_long)]+[(n,ULONG) for n in
                ('NumberOfBuffers','FreeBuffers','EventsLost','BuffersWritten','LogBuffersLost','RealTimeBuffersLost')]+[
                ('LoggerThreadId',C.c_void_p),('LogFileNameOffset',ULONG),('LoggerNameOffset',ULONG)]


class PROPERTY_BUFFER(C.Structure):
    _fields_=[('p',PROPERTIES),('logger',C.c_wchar*128),('filename',C.c_wchar*1024)]


def properties(name,path,guid):
    if len(name)>=128 or len(str(path))>=1024:
        raise ValueError('Session name/path too long')
    result=PROPERTY_BUFFER()
    result.p.Wnode.BufferSize=C.sizeof(result)
    result.p.Wnode.Guid=GUID.make(guid)
    result.p.Wnode.ClientContext=1  # QPC clock, same basis as perf_counter.
    result.p.Wnode.Flags=0x20000  # WNODE_FLAG_TRACED_GUID
    result.p.BufferSize=64
    result.p.MinimumBuffers=4
    result.p.MaximumBuffers=8
    result.p.MaximumFileSize=16
    result.p.LogFileMode=0x400001  # Sequential, stop on hybrid shutdown.
    result.p.FlushTimer=1
    result.p.EnableFlags=0  # No system/kernel process collection.
    result.p.LoggerNameOffset=PROPERTY_BUFFER.logger.offset
    result.p.LogFileNameOffset=PROPERTY_BUFFER.filename.offset
    result.logger=name
    result.filename=str(path)
    return result


def snapshot(buffer):
    return {n:int(getattr(buffer.p,n)) for n in ('MaximumFileSize','LogFileMode','EnableFlags','EventsLost',
            'BuffersWritten','LogBuffersLost','RealTimeBuffersLost','BufferSize','NumberOfBuffers')} | {
            'guid':buffer.p.Wnode.Guid.text(),'name':buffer.logger,'path':buffer.filename}


def check(status,operation):
    if status:
        raise OSError(int(status),operation+' failed: '+C.FormatError(status))


class EventFilters:
    def __init__(self,pids):
        if not pids or len(pids)>2 or len(set(pids))!=len(pids) or any(type(p) is not int or p<=0 for p in pids):
            raise ValueError('One or two distinct positive integer control PIDs required')
        # PIDs label the controls. They do not limit this proposed host-scope trace.
        self.control_pids=list(pids)
        schema=json.loads((HERE/'schema.json').read_text(encoding='utf-8-sig'))
        if schema['guid'].lower()!=PROVIDER or {e['id'] for e in schema['events']}!=set(IDS):
            raise ValueError('Unexpected provider/event set')
        self.provider=GUID.make(PROVIDER)
        self.event_ids=EVENT_IDS(1,0,len(IDS),(C.c_ushort*len(IDS))(*IDS))
        self.descriptors=(FILTER_DESCRIPTOR*1)(FILTER_DESCRIPTOR(C.addressof(self.event_ids),C.sizeof(self.event_ids),0x80000200))
        self.params=ENABLE_PARAMS(2,0x10,0,GUID(),self.descriptors,1)
    def close(self):
        pass


class NativeAPI:
    def __init__(self):
        dll=C.WinDLL('advapi32.dll')
        self.start=dll.StartTraceW
        self.start.argtypes=[C.POINTER(U64),C.c_wchar_p,C.POINTER(PROPERTIES)];self.start.restype=ULONG
        self.control=dll.ControlTraceW
        self.control.argtypes=[U64,C.c_wchar_p,C.POINTER(PROPERTIES),ULONG];self.control.restype=ULONG
        self.enable=dll.EnableTraceEx2
        self.enable.argtypes=[U64,C.POINTER(GUID),ULONG,C.c_ubyte,U64,U64,ULONG,C.POINTER(ENABLE_PARAMS)];self.enable.restype=ULONG


class Session:
    def __init__(self,name,path,guid,filters,api=None):
        self.name,self.path,self.guid=name,Path(path).resolve(),str(guid)
        self.filters=filters
        self.api=NativeAPI() if api is None else api
        self.handle=U64()
        self.started=self.enabled=self.stopped=False
        self.records=[]

    def record(self,op,status,buffer=None):
        row={'operation':op,'status':int(status)}
        if buffer is not None:
            row['properties']=snapshot(buffer)
        self.records.append(row)
        return status

    def start(self):
        probe=properties(self.name,self.path,self.guid)
        status=self.record('preflight_query',self.api.control(0,self.name,C.byref(probe.p),0),probe)
        if status!=4201:  # ERROR_WMI_INSTANCE_NOT_FOUND only; access denied fails.
            raise RuntimeError('Named session is already present or its state is unknown: '+str(status))
        if self.path.exists():
            raise FileExistsError('Fresh ETL required')
        prop=properties(self.name,self.path,self.guid)
        status=self.record('start',self.api.start(C.byref(self.handle),self.name,C.byref(prop.p)),prop)
        check(status,'StartTraceW')
        self.started=True
        status=self.record('enable_filtered_provider',self.api.enable(self.handle,C.byref(self.filters.provider),1,5,
                            0x1000000000,0,1000,C.byref(self.filters.params)))
        check(status,'EnableTraceEx2')
        self.enabled=True
        query=self.query_owned()
        if query.p.EnableFlags!=0 or query.p.MaximumFileSize!=16 or query.p.LogFileMode!=0x400001:
            raise RuntimeError('ETW declared bounds changed; owned cleanup still required')

    def query_owned(self):
        query=properties(self.name,self.path,self.guid)
        # Do not let values prefilled for StartTrace masquerade as query results.
        query.p.Wnode.Guid=GUID()
        query.p.MaximumFileSize=query.p.LogFileMode=query.p.EnableFlags=0
        query.logger=query.filename=''
        status=self.record('owned_query',self.api.control(self.handle,None,C.byref(query.p),0),query)
        check(status,'ControlTraceW query')
        if (query.p.Wnode.Guid.text()!=self.guid or Path(query.filename).resolve()!=self.path
                or query.logger!=self.name):
            raise RuntimeError('ETW identity changed; mutation refused')
        return query

    def stop(self):
        if not self.started or self.stopped:
            return
        query=self.query_owned()
        # Stopping this retained handle disables only its provider configuration.
        status=self.record('owned_stop',self.api.control(self.handle,None,C.byref(query.p),1),query)
        check(status,'ControlTraceW stop')
        self.stopped=True
        absent=properties(self.name,self.path,self.guid)
        status=self.record('post_stop_query',self.api.control(0,self.name,C.byref(absent.p),0),absent)
        if status!=4201:
            raise RuntimeError('Owned session not confirmed absent after stop')


assert C.sizeof(ULONG)==4 and C.sizeof(C.c_void_p)==8
assert C.sizeof(WNODE)==48 and C.sizeof(PROPERTIES)==120 and C.sizeof(EVENT_DESCRIPTOR)==16
