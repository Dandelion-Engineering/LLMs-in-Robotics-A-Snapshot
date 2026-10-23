"""Read terminal ETL files; decode only the declared socket-closure schema.

Unknown events are counted by descriptor, never copied or payload-decoded.
Uses raw QPC timestamps, not localized message rendering.
"""
from collections import Counter
import ctypes as C
import ipaddress
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as XML
from etw_session import GUID, EVENT_DESCRIPTOR, ULONG, U64, PROVIDER, IDS, HERE, check


class EVENT_HEADER(C.Structure):
    _fields_=[(n,C.c_ushort) for n in ('Size','HeaderType','Flags','EventProperty')]+[
        ('ThreadId',ULONG),('ProcessId',ULONG),('TimeStamp',C.c_longlong),('ProviderId',GUID),
        ('EventDescriptor',EVENT_DESCRIPTOR),('ProcessorTime',U64),('ActivityId',GUID)]


class EVENT_RECORD(C.Structure):
    _fields_=[('EventHeader',EVENT_HEADER),('BufferContext',ULONG),('ExtendedDataCount',C.c_ushort),
        ('UserDataLength',C.c_ushort),('ExtendedData',C.c_void_p),('UserData',C.c_void_p),('UserContext',C.c_void_p)]


class EVENT_TRACE(C.Structure):
    _fields_=[('Header',C.c_ubyte*48),('InstanceId',ULONG),('ParentInstanceId',ULONG),('ParentGuid',GUID),
        ('MofData',C.c_void_p),('MofLength',ULONG),('ClientContext',ULONG)]


class TRACE_LOGFILE_HEADER(C.Structure):
    _fields_=[(n,ULONG) for n in ('BufferSize','Version','ProviderVersion','NumberOfProcessors')]+[
        ('EndTime',C.c_longlong)]+[(n,ULONG) for n in ('TimerResolution','MaximumFileSize','LogFileMode',
        'BuffersWritten','StartBuffers','PointerSize','EventsLost','CpuSpeedInMHz')]+[
        ('LoggerName',C.c_void_p),('LogFileName',C.c_void_p),('TimeZone',C.c_ubyte*172),
        ('BootTime',C.c_longlong),('PerfFreq',C.c_longlong),('StartTime',C.c_longlong),
        ('ReservedFlags',ULONG),('BuffersLost',ULONG)]


class EVENT_TRACE_LOGFILE(C.Structure):
    _fields_=[('LogFileName',C.c_wchar_p),('LoggerName',C.c_wchar_p),('CurrentTime',C.c_longlong),
        ('BuffersRead',ULONG),('ProcessTraceMode',ULONG),('CurrentEvent',EVENT_TRACE),
        ('LogfileHeader',TRACE_LOGFILE_HEADER),('BufferCallback',C.c_void_p),('BufferSize',ULONG),
        ('Filled',ULONG),('EventsLost',ULONG),('EventRecordCallback',C.c_void_p),
        ('IsKernelTrace',ULONG),('Context',C.c_void_p)]


def address(raw):
    family=int.from_bytes(raw[:2],'little')
    if family==2 and len(raw)==16:
        return {'family':family,'ip':str(ipaddress.IPv4Address(raw[4:8])),
                'port':int.from_bytes(raw[2:4],'big')}
    if family==23 and len(raw)==28:
        return {'family':family,'ip':str(ipaddress.IPv6Address(raw[8:24])),
                'port':int.from_bytes(raw[2:4],'big'),'scope_id':int.from_bytes(raw[24:28],'little')}
    raise ValueError('Unsupported socket address family/length')


def decode_payload(raw,template,pointer_size):
    if not 0<len(raw)<=256 or pointer_size not in (4,8):
        raise ValueError('Payload length/pointer size outside schema bounds')
    values={};offset=0
    for field in XML.fromstring(template):
        name,kind=field.attrib['name'],field.attrib['inType']
        if kind=='win:Binary':
            count=values[field.attrib['length']]
            if field.attrib.get('outType')!='win:SocketAddress' or count not in (16,28) or offset+count>len(raw):
                raise ValueError('Binary field is not a bounded socket address')
            value=address(raw[offset:offset+count])
        else:
            count={'win:UInt32':4,'win:UInt64':8,'win:Pointer':pointer_size,'win:Boolean':4}.get(kind)
            if count is None or offset+count>len(raw):
                raise ValueError('Unsupported/truncated scalar field')
            value=int.from_bytes(raw[offset:offset+count],'little')
        values[name]=value;offset+=count
    if offset!=len(raw):
        raise ValueError('Trailing bytes outside the declared schema')
    return values


def read(path):
    path=Path(path).resolve()
    if not path.is_file() or not 0<path.stat().st_size<=16*1024*1024:
        raise ValueError('Fresh terminal ETL within16MiB required')
    schema=json.loads((HERE/'schema.json').read_text(encoding='utf-8-sig'))
    templates={(e['id'],e['version']):e['template'] for e in schema['events']}
    counts=Counter();events=[];errors=[];extended=Counter()
    @C.WINFUNCTYPE(None,C.POINTER(EVENT_RECORD))
    def event_callback(pointer):
        try:
            event=pointer.contents;header=event.EventHeader;desc=header.EventDescriptor
            provider=header.ProviderId.text()
            key=f'{provider}/{desc.Id}/{desc.Version}/{desc.Opcode}'
            counts[key]+=1
            if provider!=PROVIDER or desc.Id not in IDS:
                return
            template=templates.get((desc.Id,desc.Version))
            if template is None or event.UserDataLength>256 or not event.UserData:
                raise ValueError('Undeclared version or invalid payload bounds')
            if event.ExtendedDataCount:
                extended[key]+=int(event.ExtendedDataCount)
            pointer_size=4 if header.Flags&0x20 else 8 if header.Flags&0x40 else logfile.LogfileHeader.PointerSize
            values=decode_payload(C.string_at(event.UserData,event.UserDataLength),template,pointer_size)
            events.append({'provider':provider,'id':int(desc.Id),'version':int(desc.Version),
                'opcode':int(desc.Opcode),'qpc_ticks':int(header.TimeStamp),'header_pid':int(header.ProcessId),
                'header_tid':int(header.ThreadId),'payload_bytes':int(event.UserDataLength),'fields':values})
        except BaseException as exc:
            errors.append({'type':type(exc).__name__,'message':str(exc)[:300]})
    logfile=EVENT_TRACE_LOGFILE()
    logfile.LogFileName=str(path)
    logfile.ProcessTraceMode=0x10000000|0x1000
    logfile.EventRecordCallback=C.cast(event_callback,C.c_void_p)
    dll=C.WinDLL('advapi32.dll',use_last_error=True)
    dll.OpenTraceW.argtypes=[C.POINTER(EVENT_TRACE_LOGFILE)];dll.OpenTraceW.restype=U64
    dll.ProcessTrace.argtypes=[C.POINTER(U64),ULONG,C.c_void_p,C.c_void_p];dll.ProcessTrace.restype=ULONG
    dll.CloseTrace.argtypes=[U64];dll.CloseTrace.restype=ULONG
    handle=dll.OpenTraceW(C.byref(logfile))
    if handle==(1<<64)-1:
        raise C.WinError(C.get_last_error())
    try:
        handles=(U64*1)(handle)
        status=dll.ProcessTrace(handles,1,None,None)
        check(status,'ProcessTrace')
    finally:
        check(dll.CloseTrace(handle),'CloseTrace')
    header=logfile.LogfileHeader
    stats={n:int(getattr(header,n)) for n in ('BufferSize','MaximumFileSize','LogFileMode','BuffersWritten',
        'StartBuffers','PointerSize','EventsLost','BuffersLost','PerfFreq','StartTime','EndTime','ReservedFlags')}
    if header.ReservedFlags!=1 or header.PerfFreq<=0:
        errors.append({'type':'ClockMismatch','message':'Trace clock is not verified raw QPC'})
    else:
        for event in events:
            event['perf_counter_ns']=event['qpc_ticks']*1_000_000_000//header.PerfFreq
    return {'process_trace_status':int(status),'trace_header':stats,'descriptor_counts':dict(counts),
            'allowed_events':events,'decode_errors':errors,'extended_data_counts':dict(extended),
            'unknown_payloads_decoded':False,'raw_qpc_mode':True}


assert C.sizeof(EVENT_HEADER)==80 and C.sizeof(EVENT_RECORD)==112 and C.sizeof(EVENT_TRACE)==88
assert C.sizeof(TRACE_LOGFILE_HEADER)==280 and C.sizeof(EVENT_TRACE_LOGFILE)==448
