"""No-model continuation fixtures through the real host and isolated runtime."""
import asyncio
import hashlib
import json
import unittest
from pathlib import Path
from common import canonical,save,sha
from workspace_block import linux
from continuation import Admission,assess

def fixture(runtime,out,block,manifest,op,wait,number):
    sid='continuation-session-'+str(number);root=out/sid;guest=None
    status=wait(lambda s:s['owner']=='robot' and s['observation_age_s']<.2)
    start=op('start-invocation',{'request_id':'start-'+sid,'authority_epoch':status['authority_epoch'],'invocation_id':sid})
    endpoint=start['endpoint'];status=op('status');before=op('continuation-state')['physical']
    save(out/(sid+'-before-world.json'),before)
    files=runtime.template();files.update({'live/state.json':json.dumps(status),'live/activation.json':json.dumps(status['activation']),
                                         'live/observations/latest.json':json.dumps(status['packet'])})
    try:
        guest=runtime.Runtime.__new__(runtime.Runtime);guest.__init__(root,files,endpoint,block,sid,host_workspace=out/'public')
        guest.qualify()
        async def check(url):await runtime.prior.executor_probe(url,guest)
        asyncio.run(runtime.captured_executor.bridge_executor(guest,check))
        code="""import subprocess,sys,json
w,n=sys.argv[1:];cmd=['bwrap','--unshare-all','--unshare-user','--disable-userns','--assert-userns-disabled','--die-with-parent','--new-session','--cap-drop','ALL','--clearenv','--setenv','PATH','/usr/bin:/bin','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',w,'/workspace','--bind',w+'/notes','/workspace/notes','--chdir','/workspace','--remount-ro','/','/usr/bin/python3','-I','-B','-c', 'import os,json,pathlib,sys; p=pathlib.Path("notes/continuation-fixture.txt"); n=int(sys.argv[1]); old=p.read_text() if p.exists() else None; assert old==(None if n==1 else "neutral durable bytes 1"); assert not pathlib.Path("/tmp/scratch").exists(); pathlib.Path("/tmp/scratch").write_text("fresh process only"); p.write_text("neutral durable bytes "+str(n)); print(json.dumps({"read_prior":old,"written":p.read_text(),"pid_namespace":os.readlink("/proc/self/ns/pid"),"scratch_initially_absent":True}))',n]
p=subprocess.run(cmd,capture_output=True,text=True,timeout=20);assert p.returncode==0,p.stderr+p.stdout;print(p.stdout)
"""
        probe=json.loads(linux(code,block.workspace,number));save(root/'neutral-probe.json',probe)
        rejected=None
        if number==2:
            status=wait(lambda s:s['observation_age_s']<.2)
            body={'request_id':'fixture-rejected-handback','authority_epoch':status['authority_epoch'],
                  'order_version':status['order_version'],'observation_sequence':status['observation_sequence'],'reason':'Synthetic unresolved fixture'}
            code,rejected=runtime.request(endpoint['url'],endpoint['capability'],'POST','/handback',body)
            assert code==200 and rejected['command']['status']=='rejected';save(root/'rejected-handback.json',rejected)
        assert guest.close() and not guest.abort_event.is_set();guest=None
        retire_files=list(root.glob('executor-*-retirement.json'));assert retire_files
        assert all(json.loads(p.read_text())['qualified'] for p in retire_files)
        retirement={'run_id':manifest['run_id'],'session_id':sid,'all_namespaces_retired':True,
                    'evidence_sha256':hashlib.sha256(canonical({p.name:sha(p) for p in [*retire_files,root/'cleanup.json',root/'neutral-probe.json']})).hexdigest()}
        save(root/'retirement-bound.json',retirement)
        current=op('status');op('retire-invocation',{'request_id':'retire-'+sid,'authority_epoch':current['authority_epoch'],
                     'invocation_id':sid,'reason':'Isolated runtime retired'})
        prefix=block.verify_prefix();save(root/'continuation-journal-audit.json',prefix)
        proof={'session_id':sid,'normal_completion':True,'native_retirement':True,'journal_verified':prefix['verified']['passed'],
               'open_handles':prefix['after']['linux']['open_handles'],'journal_state_sha256':prefix['verified']['final_state_sha256'],
               'journal_audit_sha256':sha(root/'continuation-journal-audit.json'),'retirement_evidence_sha256':retirement['evidence_sha256'],
               'mode':'deterministic synthetic normal invocation; no model'}
        ending=op('authorize-continuation',proof);save(root/'ending.json',ending)
        assert ending['safe_unresolved'] and ending['admitted'],ending
        assert before['order_version']==ending['physical']['order_version']
        # Physics and gravity compensation continue during retirement; an
        # unchanged world is not an artificially frozen joint configuration.
        assert ending['physical']['sim_time_s']>before['sim_time_s']
        assert all(max(abs(a-b) for a,b in zip(position,ending['physical']['positions'][name]))<.003
                   for name,position in before['positions'].items()),'Parcel state discontinuity'
        history=[json.loads(line) for line in (out/'host/public-history.jsonl').read_text().splitlines()]
        assert not any(r['type'] in ('job_released','plant_reloaded_C') for r in history)
        assert not list((out/'host').glob('terminal-*.json'))
        return {'session_id':sid,'ending':ending,'probe':probe,'before':before,'no_model':True}
    finally:
        if guest:guest.close()

class NegativeTests(unittest.TestCase):
    def values(self):
        return ({'invocation':{'invocation_id':'opaque','state':'retired','authority_epoch':3},'owner':'robot',
                 'active_command':None,'order_version':1,'stopped':False}, {}, {'safe':True,'order_version':1},
                {'session_id':'opaque','normal_completion':True,'native_retirement':True,'journal_verified':True,'open_handles':0})
    def test_every_adverse_ending_refuses_continuation(self):
        for key,value in [('normal_completion',False),('native_retirement',False),('journal_verified',False),('open_handles',1),('session_id','wrong')]:
            s,c,p,e=self.values();e[key]=value;self.assertFalse(assess(s,c,p,e)['safe_unresolved'],key)
        for change in ('unsafe','pending','unknown','authority','accepted'):
            s,c,p,e=self.values()
            if change=='unsafe':p['safe']=False
            if change in ('pending','unknown'):c['x']={'request_id':'x','actor':'robot','kind':'command','envelope':{'authority_epoch':3},'phase':'terminal' if change=='unknown' else 'admitted','status':'unknown'}
            if change=='authority':s['invocation']['state']='active'
            if change=='accepted':c['h']={'kind':'handback','status':'completed','envelope':{'authority_epoch':3}}
            self.assertFalse(assess(s,c,p,e)['safe_unresolved'],change)
    def test_three_is_a_hard_ceiling_and_new_occurrence_is_independent(self):
        admission=Admission();s,c,p,e=self.values()
        for i in range(3):
            self.assertTrue(admission.can_start(1,str(i)));admission.started_session(1,str(i))
            self.assertFalse(admission.can_start(1,'next'))
            self.assertEqual(admission.authorize(assess(s,c,p,e)),i<2)
        self.assertFalse(admission.can_start(1,'fourth'));self.assertTrue(admission.can_start(2,'new-occurrence'))

def negative_tests():
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(NegativeTests)
    result=unittest.TextTestRunner().run(suite)
    if not result.wasSuccessful():raise RuntimeError('Continuation predicate/ceiling negative controls failed')
    return {'passed':True,'tests':result.testsRun}
