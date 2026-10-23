"""Derived ten-run behavioral corpus. Read original evidence; never run experiment code."""
from __future__ import annotations
import argparse
import base64
from bisect import bisect_right
from collections import Counter
import difflib
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

from recover import mutations, leading_reads, workspace_path

REPO=Path(__file__).resolve().parents[2]
EXPERIMENT=REPO/'Long-Horizon Adaptive Robotics Expirement'
C=EXPERIMENT/'Robot-Codex Integration 001/campaign-002'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
PLAN_SHA='c62c43e60ce6b1be5f0fd0d8383b7c68d8779cf6baf0c1aa744bcaa235176bb5'
SCHEMA='robot-codex-behavioral-evidence-1'
PRIVATE_KEYS={'token','access_token','refresh_token','authorization','api_key','apikey','password','secret','credential','credentials'}
CLIENT_FIELDS={
 'userMessage':{'type','id','content'},
 'agentMessage':{'type','id','phase','text'},
 'commandExecution':{'type','id','command','commandActions','cwd','processId','source','status','aggregatedOutput','exitCode','durationMs'},
 'sleep':{'type','id','durationMs'},
}


def sha(raw): return hashlib.sha256(raw).hexdigest()


def pointer_key(key): return key.replace('~','~0').replace('/','~1')


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf-8')


def jsonl(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def check_public(value):
    """Fail closed on credential-bearing record properties; no secret values printed."""
    if isinstance(value,dict):
        for k,v in value.items():
            if k.lower() in PRIVATE_KEYS:
                raise ValueError('Credential property encountered in proposed public record')
            check_public(v)
    elif isinstance(value,list):
        for v in value: check_public(v)
    elif isinstance(value,str):
        if re.search(r'Bearer\s+[A-Za-z0-9._-]{20,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}',value):
            raise ValueError('Credential pattern encountered in proposed public record')


class Inputs:
    def __init__(self): self.rows={}
    def raw(self,path,role,expected=None,size=None):
        p=Path(path).resolve(); raw=p.read_bytes(); h=sha(raw)
        if (expected is not None and h!=expected) or (size is not None and len(raw)!=size):
            raise ValueError('Original input identity mismatch: '+p.name)
        self.rows[str(p)]={'path':str(p),'sha256':h,'bytes':len(raw),'role':role}
        return raw
    def read(self,path,role,expected=None): return json.loads(self.raw(path,role,expected))


class Run:
    def __init__(self,attempt,assessment,output,inputs):
        self.a,self.assessment,self.output,self.inputs=attempt,assessment,output,inputs
        self.run=attempt['run_id']; self.host=Path(attempt['host_evidence']); self.orch=Path(attempt['evidence'])
        self.inv={(r['root'],r['path']):r for r in assessment['evidence_inventory']}
        self.sources={}; self.events=[]; self.versions=[]; self.contents={}; self.gaps=[]
        self.processes=[]; self.anchors=[]; self.walls=[]; self.files={}
    def raw(self,root,path):
        r=self.inv[(root,path)]
        p=({'protected_host':self.host,'orchestrator':self.orch}[root])/path
        raw=self.inputs.raw(p,'admitted original evidence',r['sha256'],r['bytes'])
        sid=('host:' if root=='protected_host' else 'orchestrator:')+path
        self.sources[sid]={'schema_version':SCHEMA,'run_id':self.run,'source_id':sid,
            'original_root':root,'original_path':path,'repository_path':p.relative_to(REPO).as_posix(),
            'sha256':r['sha256'],'bytes':r['bytes'],
            'contains_excluded_private_items':path=='pilot/client/events.jsonl',
            'scope':'Original identity reference only; original raw envelopes are not in the upload'}
        return raw,sid
    def read(self,root,path):
        raw,sid=self.raw(root,path); return json.loads(raw),sid
    def rows(self,root,path):
        raw,sid=self.raw(root,path)
        return [(i,json.loads(s)) for i,s in enumerate(raw.decode('utf-8').splitlines(),1) if s.strip()],sid
    def ref(self,sid,line=None,pointer=''):
        return {'source_id':sid,'line':line,'json_pointer':pointer}
    def content(self,raw,refs):
        h=sha(raw)
        try: text=raw.decode('utf-8'); encoding='utf-8'
        except UnicodeDecodeError: text=None; encoding='base64'
        if text is not None: check_public(text)
        r=self.contents.setdefault(h,{'schema_version':SCHEMA,'run_id':self.run,'sha256':h,'bytes':len(raw),
            'encoding':encoding,'text':text,'base64':None if text is not None else base64.b64encode(raw).decode(), 'provenance':[]})
        for ref in refs:
            if ref not in r['provenance']: r['provenance'].append(ref)
        return h
    def clock(self,wall=None,exact=None,fields=None):
        relation='untimed'; lo=hi=None; left=right=None
        if exact is not None:
            relation='recorded_simulation';lo=hi=exact
        elif type(wall) in (int,float) and math.isfinite(wall):
            i=bisect_right(self.walls,wall)
            if i==0: relation='before_recording'
            elif wall==self.walls[i-1]:
                relation='exact_anchor';lo=hi=self.anchors[i-1]['sim_time_s'];left=right=self.anchors[i-1]['event_id']
            elif i==len(self.walls): relation='after_stop';left=self.anchors[-1]['event_id']
            else:
                relation='wall_bracket';lo=self.anchors[i-1]['sim_time_s'];hi=self.anchors[i]['sim_time_s']
                left=self.anchors[i-1]['event_id'];right=self.anchors[i]['event_id']
        return {'wall_unix_s':wall,'recorded_sim_time_s':exact,'relation':relation,
            'sim_lower_s':lo,'sim_upper_s':hi,'left_anchor_event_id':left,'right_anchor_event_id':right,
            'original_timestamp_fields':fields or {},'exact_mutation_time_s':None,
            'unknown_reason':'No provable simulation mapping' if lo is None else None}
    def event(self,ident,category,kind,actor,wall,payload,refs,exact=None,ids=None,phase=None,fields=None):
        check_public(payload)
        e={'schema_version':SCHEMA,'run_id':self.run,'id':self.run+':'+ident,'category':category,
            'kind':kind,'phase':phase,'actor':actor,'clock':self.clock(wall,exact,fields),
            'ids':ids or {},'provenance':refs,'payload':payload}
        self.events.append(e);return e['id']
    def version(self,path,raw,clock,evidence,refs,state='content_evidenced',extra=None,digest=None):
        path=workspace_path(path)
        if path=='Continuity.md': path='.continuity/Continuity.md'
        h=self.content(raw,refs) if raw is not None else digest
        r={'schema_version':SCHEMA,'run_id':self.run,'id':self.run+':file-version:'+str(len(self.versions)+1),
            'path':path,'content_sha256':h,'bytes':len(raw) if raw is not None else None,
            'content_status':'retained' if raw is not None else 'unknown_not_retained',
            'evidence_class':evidence,'state_assertion':state,'clock':clock,'provenance':refs,
            'previous_evidenced_version_id':None,'diff':None,
            'unknown_reason':'Only a content hash retained; exact bytes unavailable' if raw is None else None}
        if extra: r.update(extra)
        self.versions.append(r);return r


def world_category(kind,p):
    if kind=='observation': return 'observation'
    if kind=='episode_started': return 'task_request'
    if kind=='episode_stopped': return 'task_outcome'
    if kind=='continuity_committed': return 'file_change'
    if kind=='control_owner_changed': return 'controller_transition'
    if 'invocation_' in kind: return 'authority'
    if kind=='conventional_assistance_requested': return 'task_request'
    if (p.get('envelope') or {}).get('action',{}).get('operation')=='handback' or p.get('kind')=='handback': return 'handback'
    if kind in ('command_requested','observation_requested'): return 'action_request'
    return 'action_receipt'


def export_run(attempt,assessment,output,inputs):
    r=Run(attempt,assessment,output,inputs); directory=output/'runs'/r.run
    history,hs=r.rows('protected_host','public-history.jsonl')
    r.anchors=[{'schema_version':SCHEMA,'run_id':r.run,'event_id':x['event_id'],'wall_unix_s':x['wall_unix_s'],
        'sim_time_s':x['sim_time_s'],'provenance':[r.ref(hs,line)]} for line,x in history]
    r.walls=[a['wall_unix_s'] for a in r.anchors]
    if len(r.anchors)<2 or any(b['wall_unix_s']<=a['wall_unix_s'] or b['sim_time_s']<a['sim_time_s'] for a,b in zip(r.anchors,r.anchors[1:])):
        raise ValueError('Unsupported clock reset/regression')
    background=[]
    for line,x in history:
        p=x.get('payload',{});k=x['type']
        e=r.event('world:'+str(x['event_id']),world_category(k,p),k,p.get('actor','protected_supervisor'),
            x['wall_unix_s'],{'owner':x.get('owner'),'authority_epoch':x.get('authority_epoch'),'record':p},
            [r.ref(hs,line)],exact=x['sim_time_s'],ids={'event_id':x['event_id'],'request_id':p.get('request_id')})
        if k=='observation':
            background.append(r.events.pop())
            background[-1]['payload']['availability_scope']='Background public sensor sample; agent receipt/read is not inferred'
    broker,bs=r.rows('orchestrator','pilot/broker-events.jsonl')
    for line,x in broker:
        category='robot_request' if x.get('origin')!='protected_host' else 'public_mirror'
        r.event('broker:'+str(line),category,'gateway_exchange',x.get('origin'),x.get('wall_unix_s'),
            {k:x.get(k) for k in ('origin','trace_id','method','path','status','request','response','received_wall_unix_s')},[r.ref(bs,line)],
            ids={'request_id':x.get('request_id'),'trace_id':x.get('trace_id')},
            fields={'received_wall_unix_s':x.get('received_wall_unix_s'),'wall_unix_s':x.get('wall_unix_s')})
    client,cs=r.rows('orchestrator','pilot/client/events.jsonl')
    public_messages={x['params']['item']['id'] for _,x in client if x.get('method') in ('item/started','item/completed')
        and (x.get('params') or {}).get('item',{}).get('type')=='agentMessage'
        and x['params']['item'].get('phase') in ('commentary','final_answer','final')}
    excluded=Counter();client_counts=Counter()
    for line,x in client:
        method=x.get('method');p=x.get('params') or {};item=p.get('item') or {};typ=item.get('type')
        wall=x.get('emittedAtMs',0)/1000 or None
        fields={k:v for k,v in {'emittedAtMs':x.get('emittedAtMs'),'startedAtMs':p.get('startedAtMs'),'completedAtMs':p.get('completedAtMs')}.items() if v is not None}
        if method=='item/agentMessage/delta' and p.get('itemId') in public_messages:
            r.event('client:'+str(line),'message','agent_message_delta','agent',wall,
                {'item_id':p.get('itemId'),'delta':p.get('delta')},[r.ref(cs,line)],ids={'item_id':p.get('itemId')},fields=fields)
            client_counts['message_delta']+=1
        elif method in ('item/started','item/completed') and typ in CLIENT_FIELDS and (typ!='agentMessage' or item['id'] in public_messages):
            phase=method.split('/')[1]
            category=('tool_call' if phase=='started' else 'tool_result') if typ in ('commandExecution','sleep') else ('task_request' if typ=='userMessage' else 'message')
            safe={k:v for k,v in item.items() if k in CLIENT_FIELDS[typ]}
            r.event('client:'+str(line),category,typ,'user' if typ=='userMessage' else 'agent',wall,safe,[r.ref(cs,line)],
                ids={'item_id':item.get('id'),'process_id':item.get('processId'),'thread_id':p.get('threadId'),'turn_id':p.get('turnId')},phase=phase,fields=fields)
            client_counts[typ+'_'+phase]+=1
        else: excluded['private_or_nonbehavioral_client_record']+=1
    captures=[];protocol={};fs_writes=[]
    for capture_path in sorted((r.orch/'pilot').glob('executor-*-capture.jsonl')):
        rel='pilot/'+capture_path.name
        rows,sid=r.rows('orchestrator',rel);number=int(re.search(r'executor-(\d+)',rel).group(1))
        requests={};procs={}
        for line,x in rows:
            m=x.get('message') or {};method=m.get('method');p=m.get('params') or {};wall=x.get('wall_unix_s')
            ref=r.ref(sid,line);actor='agent_executor' if number==2 else 'bootstrap_probe'
            if x['kind']=='request' and 'id' in m: requests[m['id']]=(line,m)
            if x['kind']=='request' and method=='process/start':
                pid=p['processId'];tid=p.get('metadata',{}).get('toolCallId')
                rec={'process_id':pid,'tool_id':tid,'capture_number':number,'source_id':sid,'line':line,
                     'wall':wall,'command':p['argv'][-1] if p['argv'][:2]==['/usr/bin/bash','-lc'] else None,
                     'argv':p['argv'],'cwd':p.get('cwd'),'outputs':[],'exit':None,'actor':actor}
                procs[pid]=rec;r.processes.append(rec)
                r.event('executor:'+str(number)+':'+str(line),'tool_call','process_start',actor,wall,
                    {k:p.get(k) for k in ('argv','cwd','processId','tty')},[ref],ids={'process_id':pid,'tool_id':tid,'protocol_id':m.get('id')})
            elif x['kind']=='response' and method in ('process/output','process/exited','process/closed'):
                pid=p['processId'];rec=procs.get(pid)
                ids={'process_id':pid,'tool_id':rec['tool_id'] if rec else None}
                if method=='process/output':
                    raw=base64.b64decode(p['chunk'],validate=True)
                    blobs=[b for b in x.get('blobs',[]) if b['path']==['params','chunk']]
                    if len(blobs)!=1 or any(b['raw_bytes']!=len(raw) or b['retained_bytes']!=len(raw) or b['raw_sha256']!=sha(raw) or b['retained_sha256']!=sha(raw) for b in blobs):
                        raise ValueError('Executor output is truncated or unauthenticated')
                    payload={'process_id':pid,'stream':p['stream'],'sequence':p['seq'],'text':raw.decode('utf-8',errors='replace'),
                        'bytes':len(raw),'sha256':sha(raw),'base64':base64.b64encode(raw).decode(),
                        'receipt_scope':'Complete retained executor chunk; application/model output projection is separately recorded'}
                    if rec: rec['outputs'].append({'stream':p['stream'],'raw':raw,'line':line,'wall':wall})
                    category='tool_output'
                else:
                    payload=p;category='tool_result'
                    if method=='process/exited' and rec: rec['exit']={'code':p.get('exitCode'),'wall':wall,'line':line}
                r.event('executor:'+str(number)+':'+str(line),category,method,actor,wall,payload,[ref],ids=ids)
            elif x['kind']=='request' and method in ('fs/readFile','fs/writeFile'):
                payload={'path':p.get('path'),'follow_symlinks':p.get('followSymlinks')}
                if method=='fs/writeFile':
                    raw=base64.b64decode(p['dataBase64'],validate=True)
                    payload['requested_content_sha256']=r.content(raw,[ref])
                r.event('executor:'+str(number)+':'+str(line),'tool_call',method,actor,wall,payload,[ref],ids={'protocol_id':m.get('id')})
            elif x['kind']=='response' and method is None and m.get('id') in requests:
                request_line,request=requests[m['id']];rm=request.get('method')
                if rm not in ('process/start','fs/readFile','fs/writeFile'): continue
                payload={k:v for k,v in m.items() if k in ('id','error','result')}
                if rm=='fs/readFile' and 'dataBase64' in (m.get('result') or {}):
                    raw=base64.b64decode(m['result']['dataBase64'],validate=True)
                    payload={'id':m['id'],'content_sha256':r.content(raw,[ref]),'bytes':len(raw),'path':request['params']['path']}
                    try: path=workspace_path(request['params']['path'])
                    except ValueError: path=None
                    if path:
                        r.version(path,raw,r.clock(wall),'executor_file_read',[r.ref(sid,request_line),ref])
                if rm=='fs/writeFile' and 'result' in m and 'error' not in m:
                    raw=base64.b64decode(request['params']['dataBase64'],validate=True)
                    path=workspace_path(request['params']['path'])
                    fs_writes.append((path,raw,r.clock(wall),[r.ref(sid,request_line),ref]))
                r.event('executor:'+str(number)+':'+str(line),'tool_result',rm+'_response',actor,wall,payload,[ref,r.ref(sid,request_line)],ids={'protocol_id':m.get('id')})
        captures.append((number,rows,sid))
    final,final_sid=r.read('orchestrator','pilot/runtime-after-close.json')
    before,before_sid=r.read('orchestrator','pilot/runtime-before-close.json')
    initial,initial_sid=r.read('orchestrator','pilot/runtime-input-hashes.json')
    if before!=final: raise ValueError('Distinct closure snapshots require an explicit separate export')
    raw_final={}
    for path,value in final['files'].items():
        if re.search(r'(^|/)(?:endpoint|credentials?)(?:[./]|$)',path,re.I): raise ValueError('Final export contains credential file')
        raw=base64.b64decode(value['base64'],validate=True)
        if sha(raw)!=value['sha256'] or len(raw)!=value['bytes']: raise ValueError('Final workspace content identity mismatch')
        raw_final[path]=raw
        target=directory/'workspace-final'/workspace_path(path);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    if sum(map(len,raw_final.values()))!=final['total_bytes']: raise ValueError('Final workspace byte sum')
    for path,h in initial.items():
        raw=raw_final.get(path)
        if h==sha(b''): raw=b''
        if raw is not None and sha(raw)!=h: raw=None
        r.version(path,raw,r.clock(), 'initial_hash_inventory',[r.ref(initial_sid,pointer='/'+pointer_key(path))],
            state='initial_content_identity_only',digest=h)
    for path,raw,clock,refs in fs_writes: r.version(path,raw,clock,'executor_file_write',refs)
    commits=[];candidates={};corroboration={}
    for line,x in history:
        if x['type']=='continuity_committed':
            h=x['payload']['sha256'];rel='continuity-history/'+h+'.md'
            raw,sid=r.raw('protected_host',rel)
            if sha(raw)!=h or len(raw)!=x['payload']['bytes']: raise ValueError('Continuity content mismatch')
            candidates[h]=raw;commits.append((line,x,raw,sid))
            corroboration.setdefault(h,[]).extend([r.ref(hs,line),r.ref(sid)])
            r.version('Continuity.md',raw,r.clock(x['wall_unix_s'],x['sim_time_s']),'protected_continuity_commit',
                [r.ref(hs,line),r.ref(sid)],extra={'observed_via':'Continuity.md','previous_protected_sha256':x['payload']['previous_sha256']})
    # Endpoint requests independently witness the exact draft text read by robot.py, including rejected publication.
    for line,x in broker:
        if x.get('path')=='/continuity':
            request=json.loads(x['request']) if isinstance(x.get('request'),str) and x['request'] else x.get('request')
            if not isinstance(request,dict): continue
            for key,value in request.items():
                if isinstance(value,str) and (key in ('text','content','markdown')):
                    candidates[sha(value.encode())]=value.encode()
                    body_ref=r.ref(bs,line,pointer='/request' if isinstance(x['request'],str) else '/request/'+key)
                    corroboration.setdefault(sha(value.encode()),[]).append(body_ref)
                    matching=[rec for rec in r.processes if rec['command'] and 'continuity --file ' in rec['command']
                        and rec['wall']<=x.get('received_wall_unix_s',x['wall_unix_s'])
                        and rec['exit'] and x['wall_unix_s']<=rec['exit']['wall']]
                    if len(matching)==1:
                        rec=matching[0];name=re.search(r'continuity --file (\S+)',rec['command']).group(1)
                        r.version(name,value.encode(),r.clock(x['wall_unix_s']),'gateway_file_content_read',
                            [body_ref,r.ref(rec['source_id'],rec['line'])],extra={'process_id':rec['process_id'],
                                'read_interval':{'wall_start':rec['wall'],'gateway_received_wall':x.get('received_wall_unix_s'),'gateway_reply_wall':x['wall_unix_s']},
                                'scope':'Exact draft content read by robot.py before this gateway request; includes rejected publication'})
    candidates.update({sha(raw):raw for raw in raw_final.values()})
    for path,raw in raw_final.items():
        corroboration.setdefault(sha(raw),[]).append(r.ref(final_sid,pointer='/files/'+pointer_key(path)))
    known={p:raw_final[p] for p,h in initial.items() if p in raw_final and sha(raw_final[p])==h}
    if initial.get('Continuity.md')==sha(b''): known['Continuity.md']=b''
    for path,raw,_,_ in fs_writes: known[path]=raw
    for rec in sorted(r.processes,key=lambda x:x['wall']):
        cmd=rec['command']
        if not cmd: continue
        refs=[r.ref(rec['source_id'],rec['line'])]
        exit=rec['exit'];clock=r.clock(exit['wall'] if exit else None)
        if exit: refs.append(r.ref(rec['source_id'],exit['line']))
        stdout=b''.join(x['raw'] for x in rec['outputs'] if x['stream']=='stdout')
        # Exact cat output can authenticate dynamic files, concatenation boundaries are checked explicitly.
        read_paths=leading_reads(cmd);offset=0
        for index,path in enumerate(read_paths):
            canonical='.continuity/Continuity.md' if path=='Continuity.md' else path
            choices=[raw for raw in candidates.values() if raw and stdout[offset:].startswith(raw)]
            expected=raw_final.get(canonical)
            raw=None
            if expected is not None and expected and stdout[offset:].startswith(expected): raw=expected
            elif path.endswith('.json'):
                text=stdout[offset:].decode('utf-8',errors='strict')
                try:
                    _,end=json.JSONDecoder().raw_decode(text);raw=text[:end].encode()
                    if stdout[offset+len(raw):].startswith(b'\n'): raw+=b'\n'
                except json.JSONDecodeError: pass
            elif choices:
                # Choose a known content for this path, never a prefix from an unrelated file.
                identities={v['content_sha256'] for v in r.versions if v['path']==canonical}
                matches=[b for b in choices if sha(b) in identities]
                if matches: raw=max(matches,key=len)
            elif len(read_paths)==1 and cmd.strip().startswith('cat ') and '&&' not in cmd and '\n' not in cmd:
                raw=stdout
            elif known.get(path)==b'' and index==len(read_paths)-1 and offset==len(stdout): raw=b''
            if raw is None:
                r.gaps.append({'path':canonical,'process_id':rec['process_id'],'reason':'Read output lacks provable file boundary','provenance':refs});break
            r.version(path,raw,clock,'exact_cat_read',refs,extra={'process_id':rec['process_id'],'output_byte_start':offset,'output_byte_end':offset+len(raw)})
            known[path]=raw;offset+=len(raw)
        writes,operations,gaps=mutations(cmd,known)
        for gap in gaps: r.gaps.append({**gap,'process_id':rec['process_id'],'provenance':refs})
        for path,raw,syntax in writes:
            h=sha(raw);independent=h in candidates
            if not independent:
                # Keep request bytes explicitly, without promoting them to a witnessed filesystem state.
                state='requested_content_only'
            else: state='corroborated_content_and_write_request'
            v=r.version(path,raw,clock,syntax,refs+corroboration.get(h,[]),state=state,extra={'process_id':rec['process_id'],'tool_id':rec['tool_id'],
                'write_interval':{'wall_start':rec['wall'],'wall_end':exit['wall'] if exit else None,
                    'sim_start_lower':r.clock(rec['wall'])['sim_lower_s'],'sim_end_upper':clock['sim_upper_s']},
                'process_exit_code':exit['code'] if exit else None,'independent_content_identity':independent})
            r.event('write:'+v['id'].rsplit(':',1)[-1],'file_change',syntax,'agent',exit['wall'] if exit else None,
                {'path':v['path'],'file_version_id':v['id'],'content_sha256':h,'state_assertion':state,'write_interval':v['write_interval']},refs,
                ids={'process_id':rec['process_id'],'tool_id':rec['tool_id']})
        # Preserve output redirects whose bytes survive independently in final snapshots.
        for m in re.finditer(r'python3 -B robot\.py ([^\n]*?) > (notes/[^\s;&]+)',cmd):
            path=workspace_path(m.group(2));retained_path=path;raw=raw_final.get(path)
            # A redirect to an absent path is recoverable from a later exact cat or literal rename.
            if raw is None:
                for later in r.processes:
                    if later['wall']>rec['wall'] and later['command'] and re.search(r'\bmv '+re.escape(path)+r' (\S+)',later['command']):
                        target=re.search(r'\bmv '+re.escape(path)+r' (\S+)',later['command']).group(1)
                        raw=raw_final.get(target);retained_path=target
            if raw is None:
                r.gaps.append({'path':path,'process_id':rec['process_id'],'reason':'Redirected bytes not retained or independently recoverable','provenance':refs});continue
            # Exact surviving bytes are a final-state fact; interval association does not backdate a full snapshot.
            known[path]=raw
            r.version(path,raw,clock,'redirect_with_retained_content',refs+[r.ref(final_sid,pointer='/files/'+pointer_key(retained_path))],
                state='retained_content_correlated_to_write_request',extra={'process_id':rec['process_id'],
                    'write_interval':{'wall_start':rec['wall'],'wall_end':exit['wall'] if exit else None},
                    'exact_intermediate_state_proven':False,'unknown_reason':'No mutation journal; retained bytes correlated with a unique redirect, not an exact intermediate snapshot'})
    final_ids={}
    for path,raw in raw_final.items():
        final_ids[path]=r.version(path,raw,r.clock(),'final_workspace_snapshot',
            [r.ref(final_sid,pointer='/files/'+pointer_key(path)),r.ref(before_sid,pointer='/files/'+pointer_key(path))],state='exact_retained_final_export')['id']
    # Sort versions by evidenced completion, not by invented mutation times. Untimed baseline precedes timed content, final is last.
    def order(v):
        if v['evidence_class']=='initial_hash_inventory': return (-1,0,v['id'])
        if v['evidence_class']=='final_workspace_snapshot': return (2,0,v['id'])
        return (0 if v['clock']['wall_unix_s'] is not None else 1,v['clock']['wall_unix_s'] or 0,v['id'])
    r.versions.sort(key=order);prior={}
    for v in r.versions:
        path=v['path'];p=prior.get(path)
        if p:
            v['previous_evidenced_version_id']=p['id']
            a=r.contents.get(p['content_sha256']);b=r.contents.get(v['content_sha256'])
            if a and b and a['text'] is not None and b['text'] is not None:
                v['diff']=''.join(difflib.unified_diff(a['text'].splitlines(keepends=True),b['text'].splitlines(keepends=True),
                    fromfile=path+' (previous evidenced)',tofile=path+' (selected evidenced)'))
        if v['state_assertion']!='requested_content_only': prior[path]=v
    all_paths=set(raw_final)|{v['path'] for v in r.versions}
    files=[]
    for path in sorted(all_paths):
        vs=[v for v in r.versions if v['path']==path]
        files.append({'path':path,'kind':'retained_regular_file' if path in raw_final else 'evidenced_path_absent_from_final_export',
            'final_presence':'retained' if path in raw_final else 'not_in_retained_final_export',
            'final_content_sha256':sha(raw_final[path]) if path in raw_final else None,
            'final_bytes':len(raw_final[path]) if path in raw_final else None,'final_version_id':final_ids.get(path),
            'version_ids':[v['id'] for v in vs], 'provenance':[r.ref(final_sid,pointer='/files/'+pointer_key(path))] if path in raw_final else vs[0]['provenance']})
    files.append({'path':'Continuity.md','kind':'documented_public_alias','target':'.continuity/Continuity.md',
        'final_presence':'documented_alias','final_content_sha256':sha(raw_final['.continuity/Continuity.md']),
        'final_bytes':len(raw_final['.continuity/Continuity.md']),'final_version_id':final_ids['.continuity/Continuity.md'],
        'version_ids':[v['id'] for v in r.versions if v['path']=='.continuity/Continuity.md'],
        'link_metadata':'unknown_not_retained','provenance':[r.ref(final_sid,pointer='/files/.continuity~1Continuity.md')]})
    workspace={'schema_version':SCHEMA,'run_id':r.run,'root':'/workspace','scope':final['scope'],
        'regular_file_count':len(raw_final),'total_retained_bytes':final['total_bytes'],'files':files,
        'directories':sorted({str(p.parent) for path in raw_final for p in [Path(path)] if str(p.parent)!='.'}),
        'directory_metadata':'unknown_not_retained; directory names derived from retained regular-file paths',
        'exact_intermediate_tree':'unknown_not_retained; no complete mutation journal',
        'final_snapshot_timestamp':'unknown_not_retained','omitted_scope':['endpoint credentials','non-exported Linux roots','unretained directory/symlink metadata'],
        'provenance':[r.ref(final_sid),r.ref(before_sid)]}
    assessment_path=C/'execution'/r.run/'assessment.json';asid='campaign:assessment.json'
    raw=inputs.raw(assessment_path,'original admitted assessment')
    r.sources[asid]={'schema_version':SCHEMA,'run_id':r.run,'source_id':asid,'original_root':'campaign',
        'original_path':'execution/'+r.run+'/assessment.json','repository_path':assessment_path.relative_to(REPO).as_posix(),
        'sha256':sha(raw),'bytes':len(raw),'contains_excluded_private_items':False,'scope':'Outcome/metadata projection only'}
    for filename,original in [('disposition.json',C/'execution'/r.run/'disposition.json'),('manifest.json',Path(attempt['manifest']['path'])),
            ('queue-receipt.json',C/'execution'/r.run/'storage/queue-receipt.json')]:
        value=inputs.raw(original,'original identity/provenance')
        r.sources['campaign:'+filename]={'schema_version':SCHEMA,'run_id':r.run,'source_id':'campaign:'+filename,
            'original_root':'campaign','original_path':original.relative_to(C).as_posix(),'repository_path':original.relative_to(REPO).as_posix(),
            'sha256':sha(value),'bytes':len(value),'contains_excluded_private_items':False,'scope':'Original identity reference; no unrelated assessor internals exported'}
    outcome={k:assessment[k] for k in ('validity','task_outcome','observed_task_outcome','scorable','task_evidence_valid')}
    outcome['original_checks_count']=len(assessment['checks']);outcome['original_checks_passed']=sum(v is True for v in assessment['checks'].values())
    r.event('outcome:assessment','task_outcome','original_admitted_outcome','independent_assessor',None,outcome,[r.ref(asid)])
    r.events.sort(key=lambda e:(e['clock']['wall_unix_s'] is None,e['clock']['wall_unix_s'] or 0,e['provenance'][0]['source_id'],e['provenance'][0]['line'] or 0,e['id']))
    handbacks=assessment['recovery_and_task_outcome']['handback_requests']
    starts=[x for _,x in history if x['type']=='episode_started'];stops=[x for _,x in history if x['type']=='episode_stopped']
    if len(starts)!=1 or len(stops)!=1: raise ValueError('Unique episode boundary required')
    meta={'schema_version':SCHEMA,'run_id':r.run,'ordinal':attempt['ordinal'],'challenge_family':attempt['family'],
        'seed':assessment['seed'],'noise_seed':assessment['noise_seed'],'queue_job_id':assessment['queue_job_id'],
        'disposition':'valid_success','validity':assessment['validity'],'final_task_outcome':assessment['task_outcome'],
        'framework_revision':assessment['framework_revision'],'release_revision':'RCI001-C02-frozen-001',
        'manifest_sha256':assessment['bindings']['manifest_sha256'],'assessment_sha256':sha(raw),
        'handbacks':[{'request_id':h['request_id'],'status':h['status'],'error_code':(h.get('error') or {}).get('code')} for h in handbacks],
        'handback_rejected':any(h['status']=='rejected' for h in handbacks),
        'handback_accepted':assessment['recovery_and_task_outcome']['protected_handback_accepted'],
        'agent_written_workspace_programs_used':bool(assessment.get('program_records')),
        'program_evidence_scope':'Original program-run receipts; inline Python command use is separately counted',
        'inline_python_process_count':sum(bool(x['command'] and 'python3 -c ' in x['command']) for x in r.processes),
        'start_sim_time_s':starts[0]['sim_time_s'],'stop_sim_time_s':stops[0]['sim_time_s'],
        'start_wall_unix_s':starts[0]['wall_unix_s'],'stop_wall_unix_s':stops[0]['wall_unix_s'],
        'counts':{'events':len(r.events),'background_observations':len(background),'clock_anchors':len(r.anchors),
            'process_requests':len(r.processes),'agent_process_requests':sum(x['capture_number']==2 for x in r.processes),
            'final_regular_files':len(raw_final),'file_version_records':len(r.versions),'protected_continuity_commits':len(commits),
            'unique_file_contents':len(r.contents),'public_client':dict(client_counts),'excluded_client':dict(excluded)},
        'limitations':['No complete mutation journal: exact intermediate trees, unnoticed mutations and exact write instants are unknown.',
            'Untimed final closure export is not assigned an invented simulation timestamp.',
            'Background observations prove availability, not agent receipt; actual outputs/gateway exchanges are distinct.',
            'Public notes/messages contain agent claims; protected task outcome is an independent record.',
            'Concurrent events retain source sequence; cross-source ties do not prove causality.',
            'Only five successes from each of two known challenge families; this is a selected-success corpus, not a campaign performance denominator.'],
        'provenance':[r.ref(asid),r.ref('campaign:manifest.json'),r.ref('campaign:disposition.json'),r.ref('campaign:queue-receipt.json')]}
    jsonl(directory/'events.jsonl',r.events);jsonl(directory/'observations.jsonl',background)
    jsonl(directory/'anchors.jsonl',r.anchors);jsonl(directory/'file-versions.jsonl',r.versions)
    jsonl(directory/'contents.jsonl',sorted(r.contents.values(),key=lambda x:x['sha256']))
    jsonl(directory/'sources.jsonl',sorted(r.sources.values(),key=lambda x:x['source_id']))
    dump(directory/'workspace.json',workspace);dump(directory/'metadata.json',meta);dump(directory/'recovery-gaps.json',r.gaps)
    summary=f"# {r.run}\n\nFamily: {attempt['family']}. Seed {assessment['seed']}, noise seed {assessment['noise_seed']}. Original disposition: valid success.\n\n"
    summary+='Read [metadata](metadata.json), [events](events.jsonl), [file versions](file-versions.jsonl), [complete file contents](contents.jsonl), and [final tree](workspace.json). Original bytes are under `workspace-final/`; `Continuity.md` aliases `.continuity/Continuity.md`. [Background observations](observations.jsonl) and [clock anchors](anchors.jsonl) are separate from actual agent receipts. [Source identities](sources.jsonl) resolve every provenance reference.\n\n'
    summary+=f"{len(r.events)} event records, {len(background)} background observations, {len(raw_final)} retained final regular files, {len(r.versions)} evidenced/requested version records, {len(commits)} protected continuity commits.\n\n"
    summary+='No exact intermediate filesystem reconstruction is claimed. `requested_content_only` is a literal request, not a witnessed file state. Redirected contents correlate surviving bytes with observed requests; exact mutation boundaries remain unknown. [Recovery gaps](recovery-gaps.json) preserve unsupported reads/writes.\n'
    (directory/'README.md').write_text(summary,'utf-8')
    return meta


def build(output):
    if output.exists(): raise ValueError('Fresh output directory required')
    output.mkdir(parents=True);inputs=Inputs()
    # Archive the exact tools before parsing; failed builds retain their source as well as their error.
    tools=output/'tool-source';tools.mkdir()
    for p in Path(__file__).parent.glob('*.py'): shutil.copyfile(p,tools/p.name)
    plan=inputs.read(C/'execution-plan.json','sealed campaign plan',PLAN_SHA)
    selected=[];dispositions=[]
    for a in plan['attempts']:
        d=inputs.read(C/'execution'/a['run_id']/'disposition.json','twenty unchanged dispositions')
        dispositions.append({'run_id':a['run_id'],'ordinal':a['ordinal'],'validity':d.get('validity'),
            'task_outcome':d.get('task_outcome'),'execution_status':d.get('execution_status')})
        if d.get('validity')=='valid' and d.get('task_outcome')=='success': selected.append((a,d))
    if len(selected)!=10 or Counter(a['family'] for a,_ in selected)!=Counter({'misplaced-stock':5,'blocked-insert-home':5}):
        raise ValueError('Exact ten-success selection mismatch')
    inputs.raw(C/'execution/campaign-stop.json','closed campaign admission')
    for p in (EXPERIMENT/'Architecture Map').glob('*.jsonl'): inputs.raw(p,'canonical map immutability guard')
    snapshot_path=EXPERIMENT/'Architecture Map/releases/RCI001-C02-dev-114/snapshot.json'
    snapshot=inputs.read(snapshot_path,'frozen source snapshot','7fe9c49414ecc988c6781b2a417fd4e489d505c476e2940be5213be3367cf91a')
    inputs.raw(snapshot_path.with_name('code.zip'),'frozen source archive','74e9f48f914a8f270cd658f20a360802d0afe8457948b0b00a9af5566d672ec4')
    for path,v in snapshot['sources'].items(): inputs.raw(REPO/path,'974 frozen source guards',v['sha256'],v.get('bytes'))
    metas=[];statuses=[]
    for a,d in selected:
        slot=C/'execution'/a['run_id'];receipt=inputs.read(slot/'storage/queue-receipt.json','original bound queue receipt')
        bound=receipt.get('job',receipt);jid=bound['id']
        official=json.loads(subprocess.run([sys.executable,'-X','utf8','-B',str(QUEUE),'status',jid],check=True,capture_output=True,encoding='utf-8').stdout)
        if official['id']!=jid or official['state']!='succeeded' or type(official['exit_status']) is not int or official['exit_status']!=0: raise ValueError('Original queue success/int0 missing')
        for key in ('argv','cwd','started_at','ended_at','state','exit_status'):
            if official[key]!=bound[key]: raise ValueError('Original receipt/official queue mismatch')
        statuses.append(official)
        assessment=inputs.read(slot/'assessment.json','original admitted assessment',d['assessment_sha256'])
        if assessment['run_id']!=a['run_id'] or assessment['queue_job_id']!=jid or assessment['validity']!='valid' or assessment['task_outcome']!='success': raise ValueError('Run identity/disposition mismatch')
        bindings=assessment['bindings']
        if bindings['queue_receipt_sha256']!=sha((slot/'storage/queue-receipt.json').read_bytes()) or bindings['manifest_sha256']!=a['manifest']['sha256']: raise ValueError('Assessment manifest/receipt mismatch')
        inputs.raw(a['manifest']['path'],'immutable original attempt manifest',bindings['manifest_sha256'])
        if bindings['framework_snapshot_sha256']!='7fe9c49414ecc988c6781b2a417fd4e489d505c476e2940be5213be3367cf91a': raise ValueError('Frozen revision mismatch')
        roots={'protected_host':Path(a['host_evidence']),'orchestrator':Path(a['evidence'])}
        for v in assessment['evidence_inventory']:
            inputs.raw(roots[v['root']]/v['path'],'admitted original evidence guard',v['sha256'],v['bytes'])
        metas.append(export_run(a,assessment,output,inputs))
        print(json.dumps({'exported':a['run_id'],'counts':metas[-1]['counts']},ensure_ascii=False),flush=True)
    for path in Path(__file__).parent.glob('*.py'): inputs.raw(path,'derived implementation source')
    shutil.copyfile(Path(__file__).parent/'schema.json',output/'schema.json')
    shutil.copyfile(Path(__file__).parent/'FORMAT.md',output/'FORMAT.md')
    index={'schema_version':SCHEMA,'campaign_id':plan['campaign_id'],'selection':'All and only ten originally valid Campaign 002 successes',
        'campaign_dispositions':dispositions,'runs':metas,'interpretation_performed':False,
        'new_model_simulation_launches':0,'provenance':'Per-run sources.jsonl + line/json-pointer references; original raw private traces omitted'}
    dump(output/'index.json',index)
    table='\n'.join(f"| [{m['run_id']}](runs/{m['run_id']}/README.md) | {m['challenge_family']} | {m['seed']} | {m['counts']['final_regular_files']} | {m['counts']['protected_continuity_commits']} |" for m in metas)
    (output/'README.md').write_text('# Campaign 002 behavioral evidence corpus\n\n'
        'All ten existing valid successes: five misplaced-stock and five blocked-insert-home. This is post-campaign evidence packaging for ChatGPT analysis; no behavioral interpretation or new experiment was performed. Campaign 002 remains 10 valid successes, 1 infrastructure-invalid/unknown task outcome, and 9 not run. Selection of successes must not be confused with the full campaign denominator.\n\n'
        'Start with [the machine-readable index](index.json) and [format guide](FORMAT.md). Each run has the same events, background observations, clocks, sources, workspace and content/version representation. Complete original final file bytes are browsable per run. The ZIP contains only this derived public corpus, without original raw model envelopes.\n\n'
        '| Run | Challenge family | Seed | Final regular files | Protected Continuity commits |\n|---|---|---:|---:|---:|\n'+table+'\n\n'
        'Intermediate content is last evidenced/requested content, never an exact reconstructed filesystem. Missing mutation journals, exact write times, intermediate unknown contents, directory metadata and unretained namespaces remain explicit. Public notes and messages are the agent’s claims. Background sensors do not establish a read. Final snapshots are untimed closure exports. Hidden reasoning and credentials are excluded; public agent-authored notes remain exact.\n\n'
        'Use event IDs and source sequence for joins, and wall/simulation bounds for timing. Tool-call and executor layers refer to the same observable work but different receipts; do not double count them. `contents.jsonl` is keyed by SHA256 and supplies every retained file/version body. `workspace-final/` supplies exact original final bytes. See [independent verification](verification.json) for coverage and authenticity checks.\n','utf-8')
    dump(output/'original-official-statuses.json',statuses)
    dump(output/'guards.json',{'schema':'behavioral-evidence-input-guards-1','inputs':list(inputs.rows.values())})
    for v in inputs.rows.values():
        p=Path(v['path']);raw=p.read_bytes()
        if len(raw)!=v['bytes'] or sha(raw)!=v['sha256']: raise ValueError('Original input changed during export')
    outputs=[{'path':p.relative_to(output).as_posix(),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()]
    dump(output/'build.json',{'schema':SCHEMA,'runs':len(metas),'original_frozen_sources':len(snapshot['sources']),
        'input_guard_count':len(inputs.rows),'outputs':outputs,'total_output_bytes':sum(v['bytes'] for v in outputs)})
    print(json.dumps({'completed':True,'runs':len(metas),'bytes':sum(v['bytes'] for v in outputs)}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try: build(a.output.resolve())
    except Exception as e:
        if a.output.exists(): dump(a.output/'BUILD_FAILED.json',{'outputs_not_usable':True,'error':str(e)})
        raise
