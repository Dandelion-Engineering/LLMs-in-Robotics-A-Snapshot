"""Read-only TDH filter construction probe. Never starts an ETW session."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import uuid

HERE = Path(__file__).resolve().parent


class GUID(C.Structure):
    _fields_ = [('bytes', C.c_ubyte * 16)]


class EVENT_DESCRIPTOR(C.Structure):
    _fields_ = [('Id', C.c_ushort), ('Version', C.c_ubyte), ('Channel', C.c_ubyte),
                ('Level', C.c_ubyte), ('Opcode', C.c_ubyte), ('Task', C.c_ushort), ('Keyword', C.c_ulonglong)]


class PREDICATE(C.Structure):
    _fields_ = [('FieldName', C.c_wchar_p), ('CompareOp', C.c_ushort), ('Value', C.c_wchar_p)]


def probe():
    schema_path = HERE/'tcpip-closure-schema.json'
    schema = json.loads(schema_path.read_text(encoding='utf-8-sig'))
    provider = GUID.from_buffer_copy(uuid.UUID(schema['guid']).bytes_le)
    tdh = C.WinDLL('tdh.dll')
    create = tdh.TdhCreatePayloadFilter
    create.argtypes = [C.POINTER(GUID), C.POINTER(EVENT_DESCRIPTOR), C.c_ubyte, C.c_ulong, C.POINTER(PREDICATE), C.POINTER(C.c_void_p)]
    create.restype = C.c_ulong
    delete = tdh.TdhDeletePayloadFilter
    delete.argtypes = [C.POINTER(C.c_void_p)]
    delete.restype = C.c_ulong
    rows = []
    for event in schema['events']:
        keyword = 0
        for value in event['keywords']:
            keyword |= value & ((1 << 64)-1)
        descriptor = EVENT_DESCRIPTOR(event['id'], event['version'], 16, event['level'], event['opcode'], event['task'], keyword)
        for field, operation, value in [('ProcessId', 0, '12345'), ('LocalAddress', 30, '127.0.0.1:54321')]:
            predicate = PREDICATE(field, operation, value)
            allocated = C.c_void_p()
            status = create(C.byref(provider), C.byref(descriptor), 0, 1, C.byref(predicate), C.byref(allocated))
            row = {'id': event['id'], 'version': event['version'], 'field': field, 'operation': operation, 'value': value, 'tdh_create_status': int(status), 'filter_allocated': bool(allocated)}
            if allocated:
                row['tdh_delete_status'] = int(delete(C.byref(allocated)))
            rows.append(row)
    result = {'scope': 'TDH metadata/filter construction only; no trace, provider enablement, traffic, model, or elevation', 'schema_sha256': hashlib.sha256(schema_path.read_bytes()).hexdigest(), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rows': rows}
    with (HERE/'filter-construction-001.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    probe()
