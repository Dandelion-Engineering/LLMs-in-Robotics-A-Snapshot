"""Separate readback of runtime CANCEL proof and paired structural facts."""
import copy
import hashlib
import re
import importlib.util
from common import REPO

path=REPO/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/cleanup_transport.py'
spec=importlib.util.spec_from_file_location('apartment_cleanup_readback',path)
cleanup_transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(cleanup_transport)

def require(ok,message):
    if not ok:raise ValueError('Apartment H2 readback: '+message)

def records(h):
    rows=h['runtime_cancel_records'];resets=set();terminals=set();seen=set();previous=0
    require(isinstance(rows,list) and len(rows)<=64,'runtime record bound')
    for r in rows:
        sid=r['stream_id'];c=r['cancel'];local=r['local']
        require(r['schema']=='apartment-h2-runtime-cancel-1' and type(sid) is int and 0<sid<=h['last_stream_id']
                and sid%2==1 and sid not in seen and sid not in h['active_stream_ids'],'record identity');seen.add(sid)
        raw=b'\x00\x00\x04\x03\x00'+sid.to_bytes(4,'big')+b'\x00\x00\x00\x08'
        require(all(c[k]==v for k,v in dict(direction='upload',type=3,flags=0,payload_length=4,error_code=8).items())
                and c['sha256']==hashlib.sha256(raw).hexdigest() and c['end_byte']-c['start_byte']==13
                and c['frame']>previous and c['frame']<=h['frames']['upload'] and c['end_byte']<=h['bytes']['upload'],'cancel bytes/position')
        previous=c['frame'];opened=r['opened_upload'];complete=r['opening_headers_complete']
        require(0<opened['frame']<=complete['frame']<c['frame'] and 24<=opened['start_byte']<opened['end_byte']
                <=complete['end_byte']<=c['start_byte'],'opening proof')
        require(type(local['opposite_observed_frames']) is int and 0<=local['opposite_observed_frames']<=h['frames']['download'],'opposite cursor')
        for d in ('upload','download'):
            t=r['wire'][d]
            require(type(t['frames']) is int and 0<=t['frames']<=h['frames'][d] and type(t['bytes']) is int
                    and 9*t['frames']<=t['bytes']<=h['bytes'][d] and re.fullmatch('[0-9a-f]{64}',t['sha256']) is not None,'wire bounds')
            if t['frames']==0:require(t['bytes']==0 and t['sha256']==hashlib.sha256(b'').hexdigest(),'empty trace')
            end,headers=r[d+'_end_stream'],r[d+'_headers_complete']
            require(end is not None or headers is None,'header completion without end')
            if end is not None:
                require(0<end['frame']<=h['frames'][d] and 0<end['end_byte']<=h['bytes'][d],'end position')
                if d=='upload':require(end['frame']<c['frame'] and end['end_byte']<=c['start_byte'],'upload after cancel')
            if headers is not None:require(end['frame']<=headers['frame']<=h['frames'][d] and end['end_byte']<=headers['end_byte']<=h['bytes'][d],'end headers position')
        require(r['wire']['upload']['frames']>=2 and r['wire']['upload']['bytes']>=22,'missing opening/cancel trace')
        ri,ti=local['reset_record_index'],local['terminal_control_index']
        if local['classification']=='active':
            require(type(ri) is int and 0<=ri<len(h['reset_records']) and ri not in resets and ti is None
                    and h['reset_records'][ri]==dict(direction='upload',stream_id=sid,error_code=8),'raw reset index');resets.add(ri)
        else:
            require(local['classification']=='normal_closed' and type(ti) is int and 0<=ti<len(h['terminal_control_records'])
                    and ti not in terminals and ri is None,'terminal index');terminals.add(ti)
            old=h['terminal_control_records'][ti]
            require(old==dict(direction='upload',stream_id=sid,error_code=8,frame=c['frame'],end_byte=c['end_byte'],
                normal_close=dict(opened_upload={k:opened[k] for k in ('frame','end_byte')},upload_closed=r['upload_headers_complete'],download_closed=r['download_headers_complete']),
                opposite_observed_frames=local['opposite_observed_frames']) and all(r[d+'_headers_complete'] is not None for d in ('upload','download')),'normal closure')
    return resets,terminals

def paired(a,b):
    # Original cleanup proof validation is independent of the runtime adapter.
    facts=[]
    for h in (a,b):
        require(h['error'] is None and h['open_streams']==0 and not h['active_stream_ids']
                and all(h[n] for n in ('preface_complete','settings_complete','frames_complete','headers_complete')),'incomplete endpoint')
        ri,ti=records(h);cr,ct=cleanup_transport.records(h)
        require(not ri&cr and not ti&ct and ri|cr==set(range(len(h['reset_records'])))
                and h['reset_streams']==len(h['reset_records']),'unexplained/reset overlap')
        value=copy.deepcopy(h);value.pop('retiring',None)
        value['reset_streams']-=len(ri|cr);value['closed_streams']-=len(ti|ct)
        require(value['closed_streams']>=0,'negative close count')
        value['reset_records']=[]
        value['terminal_control_records']=[{k:v for k,v in row.items() if k!='opposite_observed_frames'} for i,row in enumerate(h['terminal_control_records']) if i not in ti|ct]
        for field in ('runtime_cancel_records','cleanup_cancel_records'):
            value[field]=[{k:v for k,v in row.items() if k!='local'} for row in h[field]]
        facts.append(value)
    require(facts[0]==facts[1],'endpoint structural bytes/proofs differ')
    return dict(passed=True,runtime_cancellations=len(a['runtime_cancel_records']),cleanup_cancellations=len(a['cleanup_cancel_records']))
