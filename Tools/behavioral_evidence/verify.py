"""Independent raw-evidence audit. Does not import builder, recovery or replay code."""
from __future__ import annotations
import argparse
import ast
import base64
from bisect import bisect_right
from collections import Counter
import copy
import difflib
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

REPO=Path(__file__).resolve().parents[2]
C=REPO/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002'
EXPERIMENT=C.parents[1]
SCHEMA='robot-codex-behavioral-evidence-1'


def digest(raw): return hashlib.sha256(raw).hexdigest()
def read(p): return json.loads(p.read_text('utf-8'))
def lines(p): return {i:json.loads(s) for i,s in enumerate(p.read_text('utf-8').splitlines(),1) if s.strip()}


def schema_matches(value,node,root):
    """Evaluate every validation keyword used by this dependency-free finite schema."""
    if '$ref' in node: return schema_matches(value,root['$defs'][node['$ref'].split('/')[-1]],root)
    if 'allOf' in node and not all(schema_matches(value,n,root) for n in node['allOf']): return False
    if 'oneOf' in node and sum(schema_matches(value,n,root) for n in node['oneOf'])!=1: return False
    if 'const' in node and value!=node['const']: return False
    if 'enum' in node and value not in node['enum']: return False
    if 'type' in node:
        kind='null' if value is None else ('boolean' if type(value) is bool else ('integer' if type(value) is int else ('number' if type(value) is float else ('string' if type(value) is str else ('array' if type(value) is list else 'object')))))
        allowed=node['type'] if type(node['type']) is list else [node['type']]
        if kind not in allowed and not(kind=='integer' and 'number' in allowed): return False
    if type(value) in (int,float):
        if 'minimum' in node and value<node['minimum']: return False
        if 'maximum' in node and value>node['maximum']: return False
    if isinstance(value,str) and 'pattern' in node and re.search(node['pattern'],value) is None: return False
    if isinstance(value,list):
        if 'minItems' in node and len(value)<node['minItems']: return False
        if 'maxItems' in node and len(value)>node['maxItems']: return False
        if 'items' in node and not all(schema_matches(v,node['items'],root) for v in value): return False
    if isinstance(value,dict):
        if not set(node.get('required',[]))<=value.keys(): return False
        props=node.get('properties',{})
        if node.get('additionalProperties') is False and not value.keys()<=props.keys(): return False
        if not all(schema_matches(v,props[k],root) for k,v in value.items() if k in props): return False
    return True


def finite_python(source,known):
    """A separate AST content check, not a Python interpreter; no historical code executes."""
    vars={};writes=[]
    def val(n):
        if isinstance(n,ast.Constant) and type(n.value) in (str,int): return n.value
        if isinstance(n,ast.Name): return vars[n.id]
        if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add): return val(n.left)+val(n.right)
        if isinstance(n,ast.Subscript) and isinstance(n.slice,ast.Slice) and n.slice.step is None:
            return val(n.value)[val(n.slice.lower) if n.slice.lower else None:val(n.slice.upper) if n.slice.upper else None]
        if isinstance(n,ast.Call) and not n.keywords:
            args=[val(a) for a in n.args]
            if isinstance(n.func,ast.Name) and n.func.id=='Path' and len(args)==1: return {'path':args[0]}
            if isinstance(n.func,ast.Attribute):
                obj=val(n.func.value);name=n.func.attr
                if isinstance(obj,dict) and name=='read_text' and not args: return known[obj['path']].decode()
                if type(obj) is str and name=='replace' and len(args)==2: return obj.replace(*args)
                if type(obj) is str and name=='index' and len(args)==1: return obj.index(args[0])
        raise ValueError('Independent AST audit rejected unsupported syntax')
    for n in ast.parse(source).body:
        if isinstance(n,ast.ImportFrom) and n.module=='pathlib' and [(a.name,a.asname) for a in n.names]==[('Path',None)]: continue
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name): vars[n.targets[0].id]=val(n.value)
        elif isinstance(n,ast.Assert):
            if not (isinstance(n.test,ast.Compare) and len(n.test.ops)==1 and isinstance(n.test.ops[0],ast.In) and val(n.test.left) in val(n.test.comparators[0])): raise ValueError('Unsupported/failed retained assertion')
        elif isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='write_text':
            path=val(n.value.func.value)['path'];raw=val(n.value.args[0]).encode();known[path]=raw;writes.append((path,raw,'literal_python_string_edit'))
        else: raise ValueError('Independent AST audit rejected unsupported statement')
    return writes


def independently_parse_mutations(command,known):
    expected=[];heredoc=re.compile(r"cat\s+(>{1,2})\s+(\S+)\s+<<'([^']+)'\n([\s\S]*?)\n\3(?=\n|$)")
    def plain(text):
        for segment in text.splitlines():
            if segment.startswith(('cp ','mv ')):
                tokens=shlex.split(segment.split(' && ')[0])
                if len(tokens)==3 and tokens[1] in known:
                    known[tokens[2]]=known[tokens[1]];expected.append((tokens[2],known[tokens[2]],'literal_'+tokens[0]))
                    if tokens[0]=='mv': del known[tokens[1]]
            elif segment.startswith('sed -i '):
                _,_,script,path=shlex.split(segment);text=known[path].decode()
                if script.startswith('/^') and script.endswith('/d'):
                    pat=script[1:-2];text=''.join(s for s in text.splitlines(keepends=True) if not re.search(pat,s))
                else:
                    for match in re.finditer(r's/([^/]+)/([^/]*)/',script):
                        pat,rep=match.groups();text='\n'.join(re.sub(pat,rep,s,count=1) for s in text.split('\n'))
                known[path]=text.encode();expected.append((path,known[path],'literal_sed_string_edit'))
            elif segment.startswith('python3 -c ') and 'write_text' in segment:
                argv=shlex.split(segment.split(' && ')[0]);expected.extend(finite_python(argv[2],known))
    pos=0
    for m in heredoc.finditer(command):
        plain(command[pos:m.start()]);path=m[2];raw=(m[4]+'\n').encode()
        if m[1]=='>>':
            if path not in known: pos=m.end();continue
            raw=known[path]+raw
        known[path]=raw;expected.append((path,raw,'literal_heredoc_append' if m[1]=='>>' else 'literal_heredoc_write'));pos=m.end()
    plain(command[pos:]);return expected


def audit(output):
    assertions=0;totals=Counter();negative=[]
    def check(ok,label):
        nonlocal assertions
        if not ok: raise ValueError(label)
        assertions+=1
    schema=read(output/'schema.json')
    supported={'$schema','$id','title','$defs','$ref','oneOf','allOf','type','required','properties','const','pattern','minimum','maximum','enum','additionalProperties','minItems','maxItems','items'}
    def schema_keywords(node,in_props=False):
        if isinstance(node,dict):
            if not in_props: check(set(node)<=supported,'Unsupported JSON Schema keyword')
            for key,v in node.items():
                if key in ('$defs','properties'):
                    for value in v.values(): schema_keywords(value)
                elif isinstance(v,(dict,list)): schema_keywords(v)
        elif isinstance(node,list):
            for n in node: schema_keywords(n)
    schema_keywords(schema)
    index=read(output/'index.json');check(schema_matches(index,schema,schema),'Index schema')
    plan=read(C/'execution-plan.json')
    check(digest((C/'execution-plan.json').read_bytes())=='c62c43e60ce6b1be5f0fd0d8383b7c68d8779cf6baf0c1aa744bcaa235176bb5','Original sealed plan identity')
    valid=[];dispositions=[]
    for a in plan['attempts']:
        d=read(C/'execution'/a['run_id']/'disposition.json')
        dispositions.append({'run_id':a['run_id'],'ordinal':a['ordinal'],'validity':d.get('validity'),'task_outcome':d.get('task_outcome'),'execution_status':d.get('execution_status')})
        if d.get('validity')=='valid' and d.get('task_outcome')=='success': valid.append((a,d))
    def selection(rows): return len(rows)==10 and {m['run_id'] for m in rows}=={a['run_id'] for a,_ in valid}
    check(selection(index['runs']),'All and only ten valid successes required')
    check(index['campaign_dispositions']==dispositions,'All twenty original dispositions retained')
    check(Counter(m['challenge_family'] for m in index['runs'])=={'misplaced-stock':5,'blocked-insert-home':5},'Five runs per family')
    check(not selection(index['runs'][:-1]),'Missing-run counterexample must fail');negative.append('missing valid run rejected')
    guard=read(output/'guards.json')
    for g in guard['inputs']:
        raw=Path(g['path']).read_bytes();check(len(raw)==g['bytes'] and digest(raw)==g['sha256'],'Original input changed: '+Path(g['path']).name)
    snapshot_path=EXPERIMENT/'Architecture Map/releases/RCI001-C02-dev-114/snapshot.json'
    snapshot=read(snapshot_path)
    check(digest(snapshot_path.read_bytes())=='7fe9c49414ecc988c6781b2a417fd4e489d505c476e2940be5213be3367cf91a','Original revision snapshot')
    check(len(snapshot['sources'])==974,'974 frozen sources required')
    for path,g in snapshot['sources'].items():
        raw=(REPO/path).read_bytes();check(digest(raw)==g['sha256'] and len(raw)==g['bytes'],'Frozen source changed')
    for g in read(output/'build.json')['outputs']:
        raw=(output/g['path']).read_bytes();check(digest(raw)==g['sha256'] and len(raw)==g['bytes'],'Derived output differs from builder manifest: '+g['path'])
    officials={r['id']:r for r in read(output/'original-official-statuses.json')}
    results=[];widths=[]
    for attempt,disposition in valid:
        run=attempt['run_id'];directory=output/'runs'/run;host=Path(attempt['host_evidence']);orch=Path(attempt['evidence'])
        slot=C/'execution'/run;assessment=read(slot/'assessment.json');manifest=read(Path(attempt['manifest']['path']))
        check(digest((slot/'assessment.json').read_bytes())==disposition['assessment_sha256'],'Disposition/assessment binding')
        check(assessment['run_id']==manifest['run_id']==run,'Assessment/manifest run binding')
        receipt=read(slot/'storage/queue-receipt.json');job=receipt.get('job',receipt);jid=job['id']
        current=json.loads(subprocess.run([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',jid],capture_output=True,encoding='utf-8',check=True).stdout)
        check(current['id']==jid and current['state']=='succeeded' and type(current['exit_status']) is int and current['exit_status']==0,'Authentic original queue success/int0')
        for key in ('id','argv','cwd','started_at','ended_at','state','exit_status'): check(job[key]==current[key]==officials[jid][key],'Queue receipt binding')
        check(assessment['queue_job_id']==jid,'Assessment/job identity')
        check(digest(Path(attempt['manifest']['path']).read_bytes())==attempt['manifest']['sha256']==assessment['bindings']['manifest_sha256'],'Manifest hash binding')
        check(digest((slot/'storage/queue-receipt.json').read_bytes())==assessment['bindings']['queue_receipt_sha256'],'Assessment/receipt binding')
        meta=read(directory/'metadata.json');workspace=read(directory/'workspace.json')
        check(meta==next(m for m in index['runs'] if m['run_id']==run),'Index metadata join')
        check(meta['run_id']==run and meta['queue_job_id']==jid and meta['ordinal']==attempt['ordinal'],'Export original identity')
        check(meta['challenge_family']==attempt['family']==assessment['family']==manifest['family'],'Family binding')
        check(meta['seed']==manifest['seed']==assessment['seed'] and meta['noise_seed']==manifest['noise_seed']==assessment['noise_seed'],'Original seed metadata')
        check(meta['agent_written_workspace_programs_used']==bool(assessment.get('program_records')),'Program-use receipt scope')
        check(meta['handbacks']==[{'request_id':h['request_id'],'status':h['status'],'error_code':(h.get('error') or {}).get('code')} for h in assessment['recovery_and_task_outcome']['handback_requests']],'Handback metadata')
        check(meta['handback_accepted']==assessment['recovery_and_task_outcome']['protected_handback_accepted'],'Accepted handback')
        source_rows=list(lines(directory/'sources.jsonl').values());sources={s['source_id']:s for s in source_rows};originals={}
        for s in source_rows:
            p=REPO/s['repository_path'];raw=p.read_bytes();check(digest(raw)==s['sha256'] and len(raw)==s['bytes'],'Per-run source fingerprint')
            if s['original_root'] in ('protected_host','orchestrator'): check(run in p.parts,'Source belongs to original run')
            originals[s['source_id']]=raw
        def ref_valid(ref):
            check(ref['source_id'] in sources,'Broken provenance source ID')
            raw=originals[ref['source_id']]
            if ref['line'] is not None:
                ls=raw.decode('utf-8').splitlines();check(1<=ref['line']<=len(ls),'Provenance physical line bounds');value=json.loads(ls[ref['line']-1])
            elif ref['json_pointer']: value=json.loads(raw)
            else: return
            for component in ref['json_pointer'].split('/')[1:]:
                component=component.replace('~1','/').replace('~0','~')
                value=value[int(component)] if isinstance(value,list) else value[component]
        history=lines(host/'public-history.jsonl');broker=lines(orch/'pilot/broker-events.jsonl');client=lines(orch/'pilot/client/events.jsonl')
        anchors=list(lines(directory/'anchors.jsonl').values());walls=[x['wall_unix_s'] for x in history.values()]
        check([(a['event_id'],a['wall_unix_s'],a['sim_time_s']) for a in anchors]==[(a['event_id'],a['wall_unix_s'],a['sim_time_s']) for a in history.values()],'Full original clock anchors')
        for a,b in zip(anchors,anchors[1:]): check(b['wall_unix_s']>a['wall_unix_s'] and b['sim_time_s']>=a['sim_time_s'],'Clock segment ordering')
        def clock_ok(clock,wall,exact=None):
            if clock['wall_unix_s']!=wall or clock['recorded_sim_time_s']!=exact or clock['exact_mutation_time_s'] is not None: return False
            if exact is not None: return clock['relation']=='recorded_simulation' and clock['sim_lower_s']==clock['sim_upper_s']==exact
            if wall is None: return clock['relation']=='untimed' and clock['sim_lower_s'] is None and clock['sim_upper_s'] is None
            i=bisect_right(walls,wall)
            if i==0: return clock['relation']=='before_recording' and clock['sim_lower_s'] is None and clock['sim_upper_s'] is None
            a=anchors[i-1]
            if wall==a['wall_unix_s']: return clock['relation']=='exact_anchor' and clock['sim_lower_s']==clock['sim_upper_s']==a['sim_time_s'] and clock['left_anchor_event_id']==clock['right_anchor_event_id']==a['event_id']
            if i==len(anchors): return clock['relation']=='after_stop' and clock['sim_lower_s'] is None and clock['sim_upper_s'] is None and clock['left_anchor_event_id']==a['event_id']
            b=anchors[i];widths.append(b['sim_time_s']-a['sim_time_s'])
            return clock['relation']=='wall_bracket' and clock['sim_lower_s']==a['sim_time_s'] and clock['sim_upper_s']==b['sim_time_s'] and clock['left_anchor_event_id']==a['event_id'] and clock['right_anchor_event_id']==b['event_id']
        events=list(lines(directory/'events.jsonl').values());obs=list(lines(directory/'observations.jsonl').values());by_id={e['id']:e for e in events+obs}
        check(len(by_id)==len(events)+len(obs),'Stable unique event IDs')
        check(events==sorted(events,key=lambda e:(e['clock']['wall_unix_s'] is None,e['clock']['wall_unix_s'] or 0,e['provenance'][0]['source_id'],e['provenance'][0]['line'] or 0,e['id'])),'Chronological source-receipt order')
        expected=set()
        for line,x in history.items():
            eid=run+':world:'+str(x['event_id']);expected.add(eid);e=by_id[eid]
            payload={'owner':x.get('owner'),'authority_epoch':x.get('authority_epoch'),'record':x.get('payload',{})}
            if x['type']=='observation': payload['availability_scope']='Background public sensor sample; agent receipt/read is not inferred'
            check(e['kind']==x['type'] and e['payload']==payload,'Original public world receipt content')
            check(clock_ok(e['clock'],x['wall_unix_s'],x['sim_time_s']),'World clock mapping')
            check(e['provenance'][0]['line']==line,'World source-line join')
        check(len(obs)==sum(x['type']=='observation' for x in history.values()),'Every public observation accounted for')
        for line,x in broker.items():
            eid=run+':broker:'+str(line);expected.add(eid);e=by_id[eid]
            check(e['payload']=={k:x.get(k) for k in ('origin','trace_id','method','path','status','request','response','received_wall_unix_s')},'Exact gateway request/response')
            check(clock_ok(e['clock'],x.get('wall_unix_s')),'Gateway complete-receipt clock')
        safe_fields={'userMessage':{'type','id','content'},'agentMessage':{'type','id','phase','text'},'commandExecution':{'type','id','command','commandActions','cwd','processId','source','status','aggregatedOutput','exitCode','durationMs'},'sleep':{'type','id','durationMs'}}
        public_ids={x['params']['item']['id'] for x in client.values() if x.get('method') in ('item/started','item/completed') and x.get('params',{}).get('item',{}).get('type')=='agentMessage' and x['params']['item'].get('phase') in ('commentary','final_answer','final')}
        public_tools={}
        for line,x in client.items():
            p=x.get('params') or {};item=p.get('item') or {};typ=item.get('type');method=x.get('method');payload=None
            if method=='item/agentMessage/delta' and p.get('itemId') in public_ids: payload={'item_id':p.get('itemId'),'delta':p.get('delta')}
            elif method in ('item/started','item/completed') and typ in safe_fields and (typ!='agentMessage' or item['id'] in public_ids):
                payload={k:v for k,v in item.items() if k in safe_fields[typ]}
                if typ=='commandExecution' and method=='item/completed': public_tools[item['id']]=item
            if payload is None:
                check(run+':client:'+str(line) not in by_id,'Private/nonbehavioral item excluded');continue
            eid=run+':client:'+str(line);expected.add(eid);e=by_id[eid]
            check(e['payload']==payload,'Complete allowlisted public client item')
            check(clock_ok(e['clock'],x.get('emittedAtMs',0)/1000 or None),'Application emitted receipt clock')
        process_rows={};process_info={};fs_request={}
        for path in sorted((orch/'pilot').glob('executor-*-capture.jsonl')):
            n=int(re.search(r'executor-(\d+)',path.name).group(1));capture=lines(path);requests={}
            for line,x in capture.items():
                m=x.get('message') or {};method=m.get('method');p=m.get('params') or {};wall=x.get('wall_unix_s');eid=run+':executor:'+str(n)+':'+str(line)
                if x['kind']=='request' and 'id' in m: requests[m['id']]=(line,m)
                if x['kind']=='request' and method=='process/start':
                    expected.add(eid);e=by_id[eid]
                    check(e['payload']=={k:p.get(k) for k in ('argv','cwd','processId','tty')},'Exact process request with environment excluded')
                    pid=p['processId'];tid=p.get('metadata',{}).get('toolCallId')
                    process_info[(n,pid)]={'request':x,'line':line,'command':p['argv'][-1] if p['argv'][:2]==['/usr/bin/bash','-lc'] else None,'exit':None,'output':[]}
                    if n==2:
                        check(tid in public_tools and public_tools[tid]['processId']==pid,'Application tool/executor process/run join')
                        check(e['ids']['tool_id']==tid,'Stable original tool ID')
                elif x['kind']=='response' and method in ('process/output','process/exited','process/closed'):
                    expected.add(eid);e=by_id[eid];pid=p['processId'];info=process_info[(n,pid)]
                    if method=='process/output':
                        raw=base64.b64decode(p['chunk'],validate=True)
                        check(e['payload']['base64']==p['chunk'] and e['payload']['bytes']==len(raw) and e['payload']['sha256']==digest(raw) and e['payload']['text']==raw.decode('utf-8',errors='replace'),'Complete executor output bytes')
                        for blob in x.get('blobs',[]):
                            if blob['path']==['params','chunk']: check(blob['raw_bytes']==blob['retained_bytes']==len(raw) and blob['raw_sha256']==blob['retained_sha256']==digest(raw),'Output retained completeness')
                        info['output'].append((p['stream'],raw))
                    else:
                        check(e['payload']==p,'Exact process completion')
                        if method=='process/exited': info['exit']=(line,x)
                elif x['kind']=='request' and method in ('fs/readFile','fs/writeFile'):
                    expected.add(eid);e=by_id[eid]
                    check(e['payload']['path']==p.get('path'),'Filesystem RPC requested path')
                    if method=='fs/writeFile': check(e['payload']['requested_content_sha256']==digest(base64.b64decode(p['dataBase64'])),'Filesystem literal requested bytes')
                elif x['kind']=='response' and method is None and m.get('id') in requests:
                    qline,q=requests[m['id']];rm=q.get('method')
                    if rm not in ('process/start','fs/readFile','fs/writeFile'): continue
                    expected.add(eid)
                else: continue
                check(clock_ok(by_id[eid]['clock'],wall),'Trusted executor receipt clock')
            process_rows[n]=capture
        check(len([i for (n,_),i in process_info.items() if n==2])==len(public_tools),'All model process tools match original captures')
        actual_original={k for k in by_id if ':write:' not in k and not k.endswith(':outcome:assessment')}
        check(actual_original==expected,'Exact complete public record inventory; no missing/private extra events')
        check(len(events)==meta['counts']['events'] and len(obs)==meta['counts']['background_observations'],'Published event counts')
        final=read(orch/'pilot/runtime-after-close.json');before=read(orch/'pilot/runtime-before-close.json');initial=read(orch/'pilot/runtime-input-hashes.json')
        check(final==before,'Original closure exports equal')
        final_bytes={p:base64.b64decode(v['base64'],validate=True) for p,v in final['files'].items()}
        actual_files={p.relative_to(directory/'workspace-final').as_posix() for p in (directory/'workspace-final').rglob('*') if p.is_file()}
        check(actual_files==set(final_bytes),'Every final regular file, no extra file')
        manifest_files={f['path']:f for f in workspace['files'] if f['final_presence']=='retained'}
        check(set(manifest_files)==set(final_bytes),'Workspace inventory correctly bound')
        for path,raw in final_bytes.items():
            check((directory/'workspace-final'/path).read_bytes()==raw,'Exact original final file bytes')
            check(digest(raw)==final['files'][path]['sha256'] and len(raw)==final['files'][path]['bytes'],'Final snapshot hash/size')
            check(manifest_files[path]['final_content_sha256']==digest(raw),'Final tree/content join')
        check(workspace['regular_file_count']==len(final_bytes)==meta['counts']['final_regular_files'],'Final file counts')
        check(sum(map(len,final_bytes.values()))==workspace['total_retained_bytes']==final['total_bytes'],'Final file byte sum')
        content_rows=list(lines(directory/'contents.jsonl').values());contents={v['sha256']:v for v in content_rows};raw_contents={}
        for h,v in contents.items():
            raw=v['text'].encode('utf-8') if v['encoding']=='utf-8' else base64.b64decode(v['base64'],validate=True)
            check(digest(raw)==h and len(raw)==v['bytes'],'Every complete content-addressed body');raw_contents[h]=raw
        versions=list(lines(directory/'file-versions.jsonl').values());vids={v['id']:v for v in versions}
        check(len(vids)==len(versions)==meta['counts']['file_version_records'],'Version ID/count uniqueness')
        commits=[(line,x) for line,x in history.items() if x['type']=='continuity_committed']
        exported_commits=[v for v in versions if v['evidence_class']=='protected_continuity_commit']
        check(len(exported_commits)==len(commits)==meta['counts']['protected_continuity_commits'],'All protected Continuity versions')
        for line,x in commits:
            h=x['payload']['sha256'];raw=(host/'continuity-history'/(h+'.md')).read_bytes();v=next(v for v in exported_commits if v['provenance'][0]['line']==line)
            check(v['path']=='.continuity/Continuity.md' and v['content_sha256']==digest(raw)==h and raw_contents[h]==raw,'Original Continuity content/receipt identity')
            check(clock_ok(v['clock'],x['wall_unix_s'],x['sim_time_s']),'Protected commit exact clock')
        for path,h in initial.items():
            canonical='.continuity/Continuity.md' if path=='Continuity.md' else path
            vs=[v for v in versions if v['path']==canonical and v['evidence_class']=='initial_hash_inventory']
            check(len(vs)==1 and vs[0]['content_sha256']==h,'Every original initial file identity')
        for v in versions:
            if v['content_status']=='retained': check(v['content_sha256'] in contents and v['bytes']==len(raw_contents[v['content_sha256']]),'Version/body join')
            else: check(v['bytes'] is None and v['unknown_reason'] is not None,'Unknown baseline is not given invented bytes')
            if v['evidence_class']=='final_workspace_snapshot':
                check(v['clock']['wall_unix_s'] is None and v['clock']['sim_lower_s'] is None,'Final snapshot never backdated')
                check(raw_contents[v['content_sha256']]==final_bytes[v['path']],'Final version belongs to original run')
            elif v['evidence_class']=='exact_cat_read':
                info=next(i for (n,p),i in process_info.items() if p==v['process_id'] and n==2)
                stdout=b''.join(b for stream,b in info['output'] if stream=='stdout')
                check(stdout[v['output_byte_start']:v['output_byte_end']]==raw_contents[v['content_sha256']],'Exact read byte span in retained stdout')
                check(info['exit'] and clock_ok(v['clock'],info['exit'][1]['wall_unix_s']),'Exact read evidenced at exit receipt')
            elif v['evidence_class']=='gateway_file_content_read':
                ref=v['provenance'][0];original=broker[ref['line']];body=json.loads(original['request']) if isinstance(original['request'],str) else original['request']
                check(body['content'].encode()==raw_contents[v['content_sha256']],'Exact endpoint draft content, including rejected publication')
                info=next(i for (n,p),i in process_info.items() if n==2 and p==v['process_id'])
                check('continuity --file '+v['path'] in info['command'],'Endpoint content/file request join')
                check(info['request']['wall_unix_s']<=original['received_wall_unix_s']<=original['wall_unix_s']<=info['exit'][1]['wall_unix_s'],'Endpoint draft/process receipt interval')
        known={p:final_bytes[p] for p,h in initial.items() if p in final_bytes and digest(final_bytes[p])==h}
        if initial.get('Continuity.md')==digest(b''): known['Continuity.md']=b''
        known['notes/executor-canary.txt']=b'synthetic-write-only'
        literal_count=0
        for (n,pid),info in sorted(process_info.items(),key=lambda kv:kv[1]['request']['wall_unix_s']):
            if n!=2: continue
            command=info['command'];associated=[v for v in versions if v.get('process_id')==pid]
            for v in associated:
                if v['evidence_class']=='exact_cat_read':
                    path='Continuity.md' if v['path']=='.continuity/Continuity.md' else v['path'];known[path]=raw_contents[v['content_sha256']]
            expected_mutations=independently_parse_mutations(command,known)
            actual=[v for v in associated if v['evidence_class'].startswith('literal_')]
            check(len(expected_mutations)==len(actual),'Complete closed literal mutation inventory for process')
            for (path,raw,syntax),v in zip(expected_mutations,actual):
                check(v['path']==path and v['evidence_class']==syntax and raw==raw_contents[v['content_sha256']],'Independent literal byte recovery')
                check(v['write_interval']['wall_start']==info['request']['wall_unix_s'] and v['write_interval']['wall_end']==(info['exit'][1]['wall_unix_s'] if info['exit'] else None),'Write request/exit bounds')
                check(v['clock']['exact_mutation_time_s'] is None,'No invented exact write timestamp')
                if v['independent_content_identity']:
                    check(any(ref['source_id'].startswith('host:continuity-history/') or ref['source_id']=='orchestrator:pilot/runtime-after-close.json' or (ref['source_id']=='orchestrator:pilot/broker-events.jsonl' and ref['json_pointer']) for ref in v['provenance']),'Explicit independent content provenance')
            literal_count+=len(actual)
            for v in associated:
                if v['evidence_class']=='redirect_with_retained_content':
                    check(v['exact_intermediate_state_proven'] is False and v['unknown_reason'],'Redirect is not a fabricated intermediate snapshot')
                    check(re.search(r'> '+re.escape(v['path'])+r'(\s|$)',command) is not None,'Redirect target request identity')
                    known[v['path']]=raw_contents[v['content_sha256']]
        prior={}
        for v in versions:
            p=prior.get(v['path']);check(v['previous_evidenced_version_id']==(p['id'] if p else None),'Adjacent evidenced version links')
            if p and p['content_sha256'] in raw_contents and v['content_sha256'] in raw_contents:
                a=contents[p['content_sha256']]['text'];b=contents[v['content_sha256']]['text']
                if a is not None and b is not None:
                    expected_diff=''.join(difflib.unified_diff(a.splitlines(keepends=True),b.splitlines(keepends=True),fromfile=v['path']+' (previous evidenced)',tofile=v['path']+' (selected evidenced)'))
                    check(v['diff']==expected_diff,'Exact adjacent evidenced diff')
            if v['state_assertion']!='requested_content_only': prior[v['path']]=v
        def no_secret_keys(value):
            if isinstance(value,dict):
                check(not set(k.lower() for k in value)&{'token','access_token','refresh_token','authorization','api_key','password','secret','credentials'},'No credential properties in public records')
                for v in value.values(): no_secret_keys(v)
            elif isinstance(value,list):
                for v in value: no_secret_keys(v)
            elif isinstance(value,str): check(not re.search(r'Bearer\s+[A-Za-z0-9._-]{20,}|\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}',value),'No credential value pattern')
        for value in events+obs+versions+content_rows+source_rows+anchors+[meta,workspace]:
            check(schema_matches(value,schema,schema),'Consistent machine-readable schema')
            if value.get('run_id') is not None: check(value['run_id']==run,'Every derived record belongs to its run')
            for ref in value.get('provenance',[]): ref_valid(ref)
            no_secret_keys(value)
        for f in workspace['files']:
            for ref in f['provenance']: ref_valid(ref)
            for vid in f['version_ids']: check(vid in vids and (vids[vid]['path']==f['path'] or f['kind']=='documented_public_alias'),'Workspace/version join')
        for gap in read(directory/'recovery-gaps.json'):
            for ref in gap['provenance']: ref_valid(ref)
        check(by_id[run+':outcome:assessment']['payload']=={**{k:assessment[k] for k in ('validity','task_outcome','observed_task_outcome','scorable','task_evidence_valid')},'original_checks_count':len(assessment['checks']),'original_checks_passed':sum(v is True for v in assessment['checks'].values())},'Original protected outcome projection')
        if not negative or len(negative)==1:
            sample=next(e for e in events if e['clock']['relation']=='wall_bracket');bad=copy.deepcopy(sample['clock']);bad['sim_upper_s']+=1
            check(not clock_ok(bad,sample['clock']['wall_unix_s']),'Corrupted clock bracket must fail');negative.append('corrupted simulation bracket rejected')
            private_lines=[line for line,x in client.items() if x.get('params',{}).get('item',{}).get('type')=='reasoning']
            check(private_lines and all(run+':client:'+str(line) not in expected for line in private_lines),'Private reasoning negative coverage');negative.append('all retained reasoning items excluded')
            wrong=copy.deepcopy(meta);wrong['run_id']='RCI001-C02-home-05' if run!='RCI001-C02-home-05' else 'RCI001-C02-stock-05'
            check(wrong['run_id']!=assessment['run_id'],'Swapped-run identity counterexample');negative.append('swapped run binding rejected')
            empty=digest(b'');check(empty!=digest(b'unknown_not_retained'),'Empty/unknown distinct identity');negative.append('unknown content not treated as empty')
        totals.update({'events':len(events),'observations':len(obs),'final_regular_files':len(final_bytes),'file_versions':len(versions),'protected_continuity_commits':len(commits),'process_requests':len(process_info),'literal_mutations':literal_count})
        results.append({'run_id':run,'passed':True,'events':len(events),'observations':len(obs),'final_regular_files':len(final_bytes),'literal_mutations':literal_count})
        print(json.dumps(results[-1]),flush=True)
    result={'schema':'behavioral-evidence-independent-verification-1','passed':True,'assertions':assertions,
        'original_inputs_unchanged':len(guard['inputs']),'frozen_sources_unchanged':974,'runs':results,'totals':dict(totals),
        'maximum_sim_bracket_width_s':max(widths) if widths else None,'negative_checks':negative,
        'private_reasoning_included':False,'new_model_launches':0,'interpretation_performed':False,
        'scope':'Independent original receipt/content/clock/selection/schema audit; no new scoring or exact intermediate filesystem claim'}
    (output/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n','utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='runs'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try: audit(a.output.resolve())
    except Exception as e:
        (a.output/'VERIFICATION_FAILED.json').write_text(json.dumps({'passed':False,'error':str(e)})+'\n','utf-8');raise
