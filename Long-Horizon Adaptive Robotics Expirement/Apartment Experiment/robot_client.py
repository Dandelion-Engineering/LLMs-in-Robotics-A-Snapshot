"""Public primitive transport only. No simulator code, spatial labels or schedule."""
import json
import socket
import sys
import uuid

def call(action,parameters=None):
    parameters={} if parameters is None else parameters
    if action=='status':method,path,body='GET','/status',''
    elif action=='observe':method,path,body='POST','/observe',json.dumps(parameters)
    elif action=='point':method,path,body='POST','/command',json.dumps({'kind':'sense_point','parameters':parameters,'request_id':uuid.uuid4().hex})
    elif action=='command':
        method,path,body='POST','/command',json.dumps({'request_id':uuid.uuid4().hex,**parameters})
    else:raise ValueError('Unknown client action')
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(8)
        sock.connect('/gateway.sock')
        sock.sendall((json.dumps({'method':method,'path':path,'body':body,'capability':'local-workspace-capability'})+'\n').encode())
        raw=sock.makefile('rb').readline(8*1024*1024)
    response=json.loads(raw);decoded=json.loads(response['body'])
    if response['status']!=200 or not decoded.get('ok'):raise RuntimeError(json.dumps(decoded))
    return decoded

if __name__=='__main__':
    print(json.dumps(call(sys.argv[1],json.loads(sys.argv[2]) if len(sys.argv)>2 else {}),ensure_ascii=False))
