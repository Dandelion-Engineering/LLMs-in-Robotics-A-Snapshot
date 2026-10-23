"""Bounded synthetic adversarial checks; no native/model process is launched."""
import ast
import base64
import copy
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import canary_readback_proof as proof
from canary_exit_proof import CHECK_KEYS, SCOPE
from retained_reads import canonical, sha

TARGET='notes/resume-boundary-observation.json'
SIDECAR='notes/resume-boundary-execution.json'


def recipe(target=TARGET,sidecar=SIDECAR):
    return (f'python3 /canary.py > {target}\ncanary_exit=$?\npython3 -B - "$canary_exit" <<\'PY\'\n'
            f"import json,sys\nfrom pathlib import Path\np=Path({target!r})\nr=json.loads(p.read_text())\n"
            f"Path({sidecar!r}).write_text(json.dumps({{'exit_code':int(sys.argv[1]),'output_file':str(p)}},indent=2)+'\\n')\n"
            "print(json.dumps(r,indent=2))\nPY")


def argv(script):return ['/usr/bin/bash','-lc',script]
def document():return {'qualified':True,'checks':dict.fromkeys(sorted(CHECK_KEYS),True),'details':{},'scope':SCOPE}
def file_record(raw):return {'bytes':len(raw),'sha256':sha(raw),'retained_sha256':sha(raw),'base64':base64.b64encode(raw).decode()}


class Capture:
    def __init__(self):self.rows=[];self.delivered=set();self.events=[];self.clock=1.
    def add(self,kind,message=None,**extra):
        row={'schema':'campaign002-executor-capture-1','connection_id':'1','sequence':len(self.rows)+1,
             'previous_sha256':self.rows[-1]['record_sha256'] if self.rows else None,
             'wall_unix_s':self.clock,'kind':kind,**extra};self.clock+=.01
        if message is not None:
            row.update(message=message,original_message_sha256=sha(canonical(message)),
                       retained_message_sha256=sha(canonical(message)),blobs=[])
            if message.get('method')=='process/output':
                b=base64.b64decode(message['params']['chunk'])
                row['blobs']=[{'path':['params','chunk'],'raw_bytes':len(b),'retained_bytes':len(b),
                               'raw_sha256':sha(b),'retained_sha256':sha(b)}]
        row['record_sha256']=sha(canonical(row));self.rows.append(row);return row
    def response(self,message):
        row=self.add('response',message);self.delivered.add(row['sequence'])
        self.add('delivered',response_sequence=row['sequence']);return row
    def process(self,script,code=0,stdout=b'{}',stderr=b'',identity='exec-one',probe=False):
        pid='canary' if probe else identity
        params={'arg0':None,'argv':['/usr/bin/python3','-I','-B','/canary.py'] if probe else argv(script),
                'cwd':'file:///workspace','env':{'HOME':'/workspace','PATH':'/usr/bin:/bin'} if probe else {'LANG':'C.UTF-8'},
                'processId':pid,'sandbox':None,'tty':False}
        if not probe:params.update(pipeStdin=False,metadata={'toolCallId':identity,'threadId':'thread'},
            envPolicy={'inherit':'none','includeOnly':[],'ignoreDefaultExcludes':False,'set':{}})
        request=self.add('request',{'id':len(self.rows)+1,'method':'process/start','params':params})
        self.response({'id':request['message']['id'],'result':{'processId':pid}})
        seq=1
        for stream,data in [('stdout',stdout),('stderr',stderr)]:
            if data:self.response({'method':'process/output','params':{'processId':pid,'seq':seq,'stream':stream,'chunk':base64.b64encode(data).decode()}});seq+=1
        self.response({'method':'process/exited','params':{'processId':pid,'seq':seq,'exitCode':code}});seq+=1
        self.response({'method':'process/closed','params':{'processId':pid,'seq':seq}})
        if not probe:
            item={'id':identity,'type':'commandExecution','command':shlex.join(argv(script)),
                  'status':'completed' if code==0 else 'failed','exitCode':code,'aggregatedOutput':stdout.decode()}
            for method in ['item/started','item/completed']:
                self.events.append({'method':method,'emittedAtMs':int((self.clock+.01)*1000),
                                    'params':{'threadId':'thread','turnId':'turn','item':item.copy()}})
            self.clock+=.1
        return request


class RecipeTests(unittest.TestCase):
    def test_exact_candidate(self):
        self.assertEqual(proof.readback_recipe(argv(recipe()))['output'],TARGET)
    def test_candidate_attacks(self):
        original=recipe()
        attacks=[original+'\necho done',original.replace('canary_exit=$?','canary_exit=0'),
                 original.replace('r=json.loads(p.read_text())','r={"qualified":True}'),
                 original.replace('import json,sys','import json,sys,os'),
                 original.replace('print(json.dumps(r,indent=2))','r["qualified"]=True\nprint(json.dumps(r,indent=2))'),
                 original.replace('python3 /canary.py','false #python3 /canary.py'),
                 recipe(sidecar=TARGET),recipe(target='notes/../canary.json'),
                 recipe(sidecar=TARGET+'/child'),recipe(target='notes/canary-write.txt')]
        for attack in attacks:
            with self.subTest(attack=attack[:80]):
                try:value=proof.readback_recipe(argv(attack))
                except ValueError:continue
                self.assertIsNone(value)
    def test_three_exact_readonly_asts(self):
        for prefix,body in proof.READ_ONLY_BODIES:
            value=proof.preceding_recipe(argv(prefix+"python3 -B - <<'PY'\n"+body+'\nPY'),[TARGET,SIDECAR])
            self.assertEqual(value['kind'],'reviewed_readonly_json_projection')
    def test_encoding_cookie_cannot_hide_python_writer(self):
        injection='# coding: utf-7\n# +AAo-import os; os.system("writer &")\n'
        harmless_body=proof.READ_ONLY_BODIES[0][1]
        poisoned=injection+harmless_body
        self.assertEqual(ast.dump(ast.parse(poisoned)),ast.dump(ast.parse(harmless_body)))
        self.assertNotEqual(ast.dump(ast.parse(poisoned)),ast.dump(ast.parse(poisoned.encode().decode('utf-7'))))
        for prefix,body in proof.READ_ONLY_BODIES:
            with self.assertRaises(ValueError):
                proof.preceding_recipe(argv(prefix+"python3 -B - <<'PY'\n"+injection+body+'\nPY'),[TARGET,SIDECAR])
        candidate=recipe().replace('import json,sys',injection+'import json,sys')
        with self.assertRaises(ValueError):proof.readback_recipe(argv(candidate))
    def test_readonly_ast_extension_rejected(self):
        for prefix,body in proof.READ_ONLY_BODIES:
            for extra in ['\nopen("notes/x","w").write("x")','\nimport subprocess','\nprint(eval("1"))']:
                with self.assertRaises(ValueError):proof.preceding_recipe(argv(prefix+"python3 -B - <<'PY'\n"+body+extra+'\nPY'),[TARGET,SIDECAR])
    def test_unknown_writers_and_backgrounds(self):
        for script in ['cat Tasks.md &','sleep 1 &','python3 writer.py','python3 -c "print(1)"',
                       'echo harmless','cat Tasks.md > notes/x','find notes -exec touch notes/x ;',
                       'sed -n "1e touch notes/x" robot.py','cat $(touch notes/x)','cat Tasks.md; true']:
            with self.subTest(script=script),self.assertRaises(ValueError):proof.preceding_recipe(argv(script),[TARGET,SIDECAR])
    def test_fixed_get_redirect_excludes_target_or_alias(self):
        for path in [TARGET,SIDECAR,TARGET+'/child','notes/../x']:
            with self.assertRaises(ValueError):proof.preceding_recipe(argv(f'python3 -B robot.py query id > {path}\ncat {path}'),[TARGET,SIDECAR])
    def test_fixed_get_and_cat_allowed(self):
        for kind in ['query id','history --after 3214 --limit 42']:
            self.assertEqual(proof.preceding_recipe(argv(f'python3 -B robot.py {kind} > notes/other.json\ncat notes/other.json'),[TARGET,SIDECAR])['writes'],['notes/other.json'])
    def test_wrapper_is_closed(self):
        command=json.dumps({'cmd':'cat Tasks.md','workdir':'/workspace'})
        single=f'text(await tools.exec_command({command}));'
        self.assertEqual(len(proof.wrapper_commands(single)),1)
        parallel=f'const results = await Promise.allSettled([tools.exec_command({command})]); for (let i=0;i<results.length;i++) text({{i,...results[i]}});'
        self.assertEqual(len(proof.wrapper_commands(parallel)),1)
        for bad in [single+'fetch("x")',single.replace('exec_command','other_tool'),parallel.replace('i=0','i=1')]:
            with self.assertRaises(ValueError):proof.wrapper_commands(bad)


class ProcessTests(unittest.TestCase):
    def test_nonzero127_is_accounted(self):
        c=Capture();c.add('open');r=c.process('pwd && rg --files',code=127,stderr=b'rg: command not found\n')
        value=proof.process_record(c.rows,c.delivered,r,c.events)
        self.assertEqual(value['exit_code'],127);self.assertTrue(value['stderr'])
    def test_incomplete_or_unmatched_process_rejected(self):
        for attack in ['noexit','noclose','nodelivery','noapp','duplicate','redacted','wrongexit','shadowenv','outputgap']:
            with self.subTest(attack=attack):
                c=Capture();c.add('open');r=c.process(recipe(),stdout=json.dumps(document()).encode())
                if attack=='noexit':c.rows[:]=[x for x in c.rows if x.get('message',{}).get('method')!='process/exited']
                if attack=='noclose':c.rows[:]=[x for x in c.rows if x.get('message',{}).get('method')!='process/closed']
                if attack=='nodelivery':c.delivered.clear()
                if attack=='noapp':c.events.clear()
                if attack=='duplicate':c.events.append(copy.deepcopy(c.events[-1]))
                if attack=='redacted':r['original_message_sha256']='0'*64
                if attack=='wrongexit':c.events[-1]['params']['item']['exitCode']=False
                if attack=='shadowenv':r['message']['params']['env']['PYTHONPATH']='notes'
                if attack=='outputgap':next(x for x in c.rows if x.get('message',{}).get('method')=='process/output')['message']['params']['seq']=44
                with self.assertRaises(ValueError):proof.process_record(c.rows,c.delivered,r,c.events)
    def test_real_prefix_shaped_exclusivity(self):
        c=Capture();c.add('open');requests=[]
        requests.append(c.process('',probe=True,stdout=json.dumps(document()).encode()))
        scripts=['ls -la /workspace',"pwd && rg --files -g 'RobotAgentPrompt.md' -g 'AGENTS.md' -g 'SKILL.md' -g '!node_modules' -g '!vendor' /workspace",
                 'find /workspace -name AGENTS.md -o -name SKILL.md','cat AGENTS.md RobotAgentPrompt.md',
                 'cat Tasks.md Robot.md Tools.md','cat live/activation.json live/state.json Continuity.md','cat Tools.md',
                 "cat live/activation.json && find notes programs live -maxdepth 2 -type f -printf '%p\\n'",
                 "python3 -B robot.py query smoke-open-001 > notes/resume-open-terminal.json\ncat notes/resume-open-terminal.json",
                 "python3 -B robot.py history --after 3214 --limit 42 > notes/resume-history-interruption.json\ncat notes/resume-history-interruption.json",
                 "cat notes/smoke-observation.json\nsed -n '1,320p' robot.py"]
        scripts += [prefix+"python3 -B - <<'PY'\n"+body+'\nPY' for prefix,body in proof.READ_ONLY_BODIES]
        self.assertEqual(len(scripts),14)
        for i,script in enumerate(scripts):requests.append(c.process(script,127 if script.startswith('pwd &&') else 0,identity='exec-'+str(i)))
        requests.append(c.process(recipe(),stdout=json.dumps(document()).encode(),identity='selected'))
        processes=[proof.process_record(c.rows,c.delivered,r,c.events) for r in requests]
        for p in processes:p['capture']='executor-1-capture.jsonl'
        value=proof.prefix_exclusive(processes,processes[-1]);self.assertEqual(value['processes_including_candidate'],16)
        self.assertEqual(value['nonzero_exit_count'],1)
        for change in ['overlap','writer','bad127']:
            bad=copy.deepcopy(processes)
            if change=='overlap':bad[1]['execution']['evidence_complete_upper_wall_unix_s']=bad[-1]['execution']['request_wall_unix_s']
            if change=='writer':bad[1]['argv']=argv('sleep 1 &')
            if change=='bad127':bad[1]['exit_code']=127
            with self.assertRaises(ValueError):proof.prefix_exclusive(bad,bad[-1])


class RestoreAndDocumentTests(unittest.TestCase):
    def test_complete_source_contract_and_changed_source_negatives(self):
        from canary_exit_proof import REVIEWED_SOURCES
        from empty_startup_reads import BOUNDARY_HASHES
        integration=Path(__file__).resolve().parents[2]
        suffixes=set(proof.SOURCE_HASHES)
        suffixes.update('readiness-session-10/'+s for s in REVIEWED_SOURCES)
        suffixes.update('readiness-session-10/boundary/'+s for s in BOUNDARY_HASHES)
        suffixes.add('campaign-002/io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md')
        suffixes.update('campaign-002/assessment/'+n for n in ('canary_readback_proof.py','canary_exit_proof.py',
            'empty_startup_reads.py','completion_chronology.py','retained_reads.py','transport_integrity.py',
            'prepared_result_segments.py','raw_tool_result_reads.py'))
        payloads={s:(integration/s).read_bytes() for s in suffixes}
        with tempfile.TemporaryDirectory() as folder:
            def archive(label,alter=None):
                p=Path(folder)/(label+'.zip')
                with zipfile.ZipFile(p,'w') as z:
                    for suffix,data in payloads.items():z.writestr('prefix/'+suffix,data+(b'\n# altered' if suffix==alter else b''))
                return p
            hashes={'robot.py':proof.SOURCE_HASHES['runtime-template/robot.py']}
            self.assertTrue(proof.reviewed_sources(archive('valid'),hashes,[]))
            for index,suffix in enumerate(['campaign-002/harness/physical.py','campaign-002/harness/runtime.py',
                    'runtime-template/robot.py','readiness-session-10/boundary/runtime_layout.py',
                    'campaign-002/io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md']):
                with self.subTest(source=suffix),self.assertRaises(ValueError):proof.reviewed_sources(archive(str(index),suffix),hashes,[])
            with self.assertRaises(ValueError):proof.reviewed_sources(archive('wrong-workspace'),{'robot.py':'0'*64},[])
    def test_snapshot_retained_bytes_and_aliases(self):
        value={'files':{'notes/a':file_record(b'a')},'total_bytes':1,'scope':'actual file bytes; endpoint omitted'}
        self.assertEqual(proof.snapshot_files(value),{'notes/a':b'a'})
        for mutate in [lambda x:x['files']['notes/a'].update(sha256='0'*64),
                       lambda x:x['files'].update({'notes/a/child':file_record(b'x')}),
                       lambda x:x.update(total_bytes=True),lambda x:x['files'].update({'notes/../x':file_record(b'x')})]:
            bad=copy.deepcopy(value);mutate(bad)
            with self.assertRaises(ValueError):proof.snapshot_files(bad)
    def test_duplicate_and_changed_checks(self):
        with self.assertRaises(ValueError):proof.json_document('{"qualified":false,"qualified":true}')
        for mutate in [lambda x:x.update(qualified=False),lambda x:x['checks'].update(workspace_read=1),lambda x:x['checks'].pop('workspace_read')]:
            value=document();mutate(value)
            with self.assertRaises(ValueError):proof.check_document(value)
    def test_wrong_source_abstains(self):
        with tempfile.TemporaryDirectory() as folder:
            r=Path(folder);(r/'runtime-input-hashes.json').write_text('{}');z=r/'source.zip'
            with zipfile.ZipFile(z,'w') as archive:archive.writestr('unexpected.py','pass')
            result=proof.canary_readback_evidence(r,z)
            self.assertFalse(result['verified']);self.assertEqual(result['evidence'],[]);self.assertTrue(result['errors'])
    def test_missing_restore_never_becomes_a_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'resume';root.mkdir()
            with self.assertRaises(OSError):proof.restoration_proof(root,{},TARGET,SIDECAR,[])

    def restore_fixture(self,folder):
        parent=Path(folder);root=parent/'resume';old=parent/'interrupt';root.mkdir();old.mkdir()
        def write(p,x):p.write_text(json.dumps(x),encoding='utf-8')
        first={'kind':'interrupt','invocation_id':'old',**dict.fromkeys(('injected_interruption','durable_retention_verified',
              'old_token_denied_after_retirement','all_namespaces_retired','cleanup_clean'),True)}
        second={'kind':'resume','invocation_id':'new'}
        write(old/'stage-result.json',first);write(root/'stage-result.json',second)
        write(parent/'sequence-result.json',{'mode':'smoke','orchestrator_completed':True,'host_exit_code':0,'stages':[first,second]})
        write(old/'cleanup.json',{'clean':True,'errors':[]})
        for path,suffix in [(old,'a'*32),(root,'b'*32)]:
            run='/var/tmp/robot-codex-session10/'+suffix
            write(path/'runtime-location.json',{'run':run,'workspace':run+'/workspace'})
        snapshot={'files':{'notes/README.md':file_record(b'old'),'.continuity/Continuity.md':file_record(b'note')},
                  'total_bytes':7,'scope':'actual file bytes; endpoint omitted'}
        for name in ['runtime-before-close.json','runtime-after-close.json']:write(old/name,snapshot)
        (old/'executor-1-capture.jsonl').write_text('retirement name inventory only')
        end={'retired':True,'namespace_evidence_available':True,'outer_same_process':False,'namespace_members':[],
             'namespace_ids':[42]}
        for name in ['executor-1-retirement.json','codehost-owner-retirement-v3.json']:
            write(old/name,{'qualified':True,'normal_wait_timed_out':False,'windows_wrapper_killed_after_linux_retired':False,
                            'windows_exit_code':0,'observations':[end],'identity_path':'/var/tmp/robot-codex-session10/'+'a'*32+'/'+name})
        return root

    def test_source_derived_restore_joins_exact_prior_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.restore_fixture(folder);r=proof.restoration_proof(root,{'notes/README.md':'0'*64},TARGET,SIDECAR,[])
            self.assertTrue(r['target_initially_absent']);self.assertEqual(r['restored_files']['notes/prior-local-continuity.md']['source'],'.continuity/Continuity.md')
            self.assertIn('source-derived',r['linkage'])

    def test_restore_and_retirement_mutations_abstain(self):
        for attack in ['missing_retirement','foreign_identity','not_retired','changed_snapshot','target_present',
                       'reuse_run','wrong_stage','wrong_dispatch','alias_restore','redacted_restore']:
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as folder:
                root=self.restore_fixture(folder);old=root.parent/'interrupt'
                def change(p,fn):
                    v=json.loads(p.read_text());fn(v);p.write_text(json.dumps(v))
                if attack=='missing_retirement':(old/'executor-1-retirement.json').unlink()
                if attack=='foreign_identity':change(old/'executor-1-retirement.json',lambda v:v.update(identity_path='/elsewhere/x'))
                if attack=='not_retired':change(old/'executor-1-retirement.json',lambda v:v['observations'][0].update(namespace_members=[12]))
                if attack=='changed_snapshot':change(old/'runtime-after-close.json',lambda v:v.update(total_bytes=8))
                if attack in ('target_present','alias_restore','redacted_restore'):
                    for name in ['runtime-before-close.json','runtime-after-close.json']:
                        if attack=='target_present':change(old/name,lambda v:(v['files'].update({TARGET:file_record(b'old')}),v.update(total_bytes=10)))
                        if attack=='alias_restore':change(old/name,lambda v:(v['files'].update({'notes/prior-local-continuity.md':file_record(b'old')}),v.update(total_bytes=10)))
                        if attack=='redacted_restore':change(old/name,lambda v:v['files']['notes/README.md'].update(sha256='0'*64))
                if attack=='reuse_run':(root/'runtime-location.json').write_bytes((old/'runtime-location.json').read_bytes())
                if attack=='wrong_stage':change(root/'stage-result.json',lambda v:v.update(invocation_id='other'))
                if attack=='wrong_dispatch':change(root.parent/'sequence-result.json',lambda v:v.update(mode='pilot'))
                with self.assertRaises((ValueError,OSError)):proof.restoration_proof(root,{},TARGET,SIDECAR,[])


class CensusTests(unittest.TestCase):
    def write_capture(self,root,c):
        c.add('closed',failures=[])
        (root/'executor-1-capture.jsonl').write_bytes(b''.join(canonical(x)+b'\n' for x in c.rows))
        (root/'executor-1-requests.jsonl').write_bytes(b''.join(canonical(x['message'])+b'\n' for x in c.rows if x['kind']=='request'))
    def test_all_rpc_starts_and_nonzero_included(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);c=Capture();c.add('open');c.process('ls -la /workspace',code=127)
            self.write_capture(root,c);processes,rpcs,connections=proof.complete_census(root,c.events,100,[])
            self.assertEqual(len(processes),1);self.assertEqual(processes[0]['exit_code'],127)
    def test_unknown_native_writer_and_orphan_output_rejected(self):
        for attack in ['write','unknown','orphan','unmatched_start','redacted','mirror_missing']:
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);c=Capture();c.add('open');c.process('ls -la /workspace')
                if attack in ('write','unknown'):
                    req=c.add('request',{'id':999,'method':'fs/writeFile' if attack=='write' else 'process/writeStdin',
                        'params':{'path':'file:///workspace/'+TARGET,'dataBase64':'eA==','followSymlinks':False,'sandbox':None}})
                    c.response({'id':999,'result':{}})
                if attack=='orphan':c.response({'method':'process/closed','params':{'processId':'hidden','seq':1}})
                if attack=='unmatched_start':c.process('ls -la /workspace',identity='hidden');c.events=c.events[:-2]
                if attack=='redacted':c.rows[1]['original_message_sha256']='0'*64
                self.write_capture(root,c)
                if attack=='mirror_missing':(root/'executor-1-requests.jsonl').write_text('')
                with self.assertRaises(ValueError):proof.complete_census(root,c.events,100,[])

    def test_actual_wrapper_envelope_and_bijection(self):
        c=Capture();c.add('open');r=c.process(recipe(),stdout=json.dumps(document()).encode())
        p=proof.process_record(c.rows,c.delivered,r,c.events);p['capture']='executor-1-capture.jsonl'
        item={'type':'custom_tool_call','name':'exec','call_id':'outer','input':'text(await tools.exec_command('+json.dumps({'cmd':recipe(),'workdir':'/workspace'})+'));'}
        call={'method':'rawResponseItem/completed','params':{'threadId':'thread','turnId':'turn','item':item}}
        output={'method':'rawResponseItem/completed','params':{'threadId':'thread','turnId':'turn','item':
            {'type':'custom_tool_call_output','call_id':'outer','output':[{'type':'input_text','text':'Script completed\nWall time 0.2 seconds\nOutput:\n'}]}}}
        events=[call,*c.events,output];p['completion_index']=2
        self.assertEqual(len(proof.app_prefix_census(events,p,[p])),1)
        for attack in ['hidden','orphan','duplicate','missing','other_tool','extra_js']:
            bad=copy.deepcopy(events)
            if attack=='hidden':bad[1]['params']['item']['id']='hidden'
            if attack=='orphan':bad[2]['params']['item']['id']='hidden'
            if attack=='duplicate':bad.append(copy.deepcopy(bad[-1]))
            if attack=='missing':bad.pop()
            if attack=='other_tool':bad[0]['params']['item']['name']='other'
            if attack=='extra_js':bad[0]['params']['item']['input']+=' fetch("x");'
            with self.subTest(attack=attack),self.assertRaises(ValueError):proof.app_prefix_census(bad,p,[p])

    def public_fixture(self,folder):
        root=RestoreAndDocumentTests().restore_fixture(folder)
        (root/'runtime-input-hashes.json').write_text('{}')
        raw=json.dumps(document(),indent=2).encode();note=json.dumps(document()).encode()
        snapshots={'files':{TARGET:file_record(note),SIDECAR:file_record(json.dumps({'exit_code':0,'output_file':TARGET}).encode())}}
        for name in ['runtime-before-close.json','runtime-after-close.json']:(root/name).write_text(json.dumps(snapshots))
        c=Capture();c.add('open');c.process('',probe=True,stdout=json.dumps(document()).encode())
        c.process(recipe(),stdout=raw);self.write_capture(root,c)
        call={'method':'rawResponseItem/completed','params':{'threadId':'thread','turnId':'turn','item':
              {'type':'custom_tool_call','name':'exec','call_id':'outer','input':'text(await tools.exec_command('+json.dumps({'cmd':recipe(),'workdir':'/workspace'})+'));'}}}
        output={'method':'rawResponseItem/completed','params':{'threadId':'thread','turnId':'turn','item':
                {'type':'custom_tool_call_output','call_id':'outer','output':[{'type':'input_text','text':'Script completed\nWall time 0.2 seconds\nOutput:\n'}]}}}
        (root/'client').mkdir();(root/'client/events.jsonl').write_bytes(b''.join(canonical(x)+b'\n' for x in [call,*c.events,output]))
        return root

    def test_public_helper_semantic_evidence_and_failclosed_mutations(self):
        # Source and protected fixture contracts have independent tests above;
        # here real census/restore/AST/JSON code is exercised through public API.
        for attack in [None,'note_changed','sidecar_only','sidecar_wrong','wrapper_failed','stdout_false','hidden_writer']:
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as folder:
                root=self.public_fixture(folder)
                if attack in ('note_changed','sidecar_only','sidecar_wrong'):
                    for name in ['runtime-before-close.json','runtime-after-close.json']:
                        p=root/name;v=json.loads(p.read_text())
                        if attack=='note_changed':v['files'][TARGET]=file_record(b'{}')
                        if attack=='sidecar_only':del v['files'][TARGET]
                        if attack=='sidecar_wrong':v['files'][SIDECAR]=file_record(json.dumps({'exit_code':1,'output_file':TARGET}).encode())
                        p.write_text(json.dumps(v))
                if attack=='wrapper_failed':
                    p=root/'client/events.jsonl';e=[json.loads(x) for x in p.read_text().splitlines()];e[-2]['params']['item']['exitCode']=1
                    p.write_bytes(b''.join(canonical(x)+b'\n' for x in e))
                if attack=='stdout_false':
                    p=root/'client/events.jsonl';e=[json.loads(x) for x in p.read_text().splitlines()];e[-2]['params']['item']['aggregatedOutput']='{"qualified":false}'
                    p.write_bytes(b''.join(canonical(x)+b'\n' for x in e))
                if attack=='hidden_writer':
                    p=root/'client/events.jsonl';e=[json.loads(x) for x in p.read_text().splitlines()];e[0]['params']['item']['input']+=' tools.exec_command({cmd:"writer &"});'
                    p.write_bytes(b''.join(canonical(x)+b'\n' for x in e))
                with patch.object(proof,'reviewed_sources',return_value=[]),patch.object(proof,'fixture_proof',return_value={}):
                    result=proof.canary_readback_evidence(root,Path(folder)/'unused.zip')
                if attack is None:
                    self.assertTrue(result['verified'],result['errors']);item=result['evidence'][0]
                    self.assertTrue(item['semantic_json_equal']);self.assertFalse(item['byte_equal'])
                    self.assertFalse(item['protected_child_exit_independently_observed'])
                else:self.assertFalse(result['verified'],result)


if __name__=='__main__':unittest.main()
