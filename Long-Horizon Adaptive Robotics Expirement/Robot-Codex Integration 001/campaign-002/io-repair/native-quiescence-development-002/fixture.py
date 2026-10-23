from pathlib import Path
import copy,json,hashlib,sys
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from test_client_quiescence import QuiescenceTests,V4
root=Path(sys.argv[2]);root.mkdir(exist_ok=False)
t=QuiescenceTests();client,oldroot=t.client(state='none')
client.events.close();client.events=(root/'events.jsonl').open('x',encoding='utf-8')
args=client.args;args.evidence=root;args.host_cwd=root/'host';args.host_cwd.mkdir();args.codex_home=root/'home';args.codex_home.mkdir()
args.timeout=90;args.exec_server_url='ws://127.0.0.1:1234/synthetic';args.code_mode_host_url='http://127.0.0.1:2345';args.remote_cwd='file:///workspace';args.run_bootstrap=True
args.native_process_ready=lambda process,binary:{'schema':'synthetic-owner','pid':123}
client.args.abort_event.clear();client.deadline=__import__('time').monotonic()+5
config={'features':{n:False for n in V4.DISABLED},'model_provider':'openai','web_search':'disabled','project_doc_max_bytes':0}
config['features']['code_mode_host']=True
control=client.process.respond
def respond(request):
 method=request['method'];params=request['params']
 if method in ('turn/interrupt','thread/unsubscribe'):return control(request)
 result={}
 if method=='config/read':result={'config':config}
 if method=='account/read':result={'account':{'type':'chatgpt'}}
 if method=='environment/status':result={'status':'unknown' if params['environmentId']=='local' else 'ready'}
 if method=='environment/info':result={'shell':{'path':'/usr/bin/bash'},'cwd':'file:///workspace'}
 if method=='thread/start':result={'model':V4.LAUNCH.MODEL,'modelProvider':'openai','reasoningEffort':V4.LAUNCH.EFFORT,'instructionSources':[],'thread':{'id':'thread-fixed'}}
 if method=='mcpServerStatus/list':result={'data':[]}
 if method=='turn/start':result={'turn':{'id':'turn-fixed'}}
 client.messages.put(('stdout',(json.dumps({'id':request['id'],'result':result})+'\n').encode()))
client.process.respond=respond
original_wait=client.wait_turn
def interrupted(turn):
 client.args.abort_event.set()
 return original_wait(turn)
client.wait_turn=interrupted
native=root/'synthetic-native.exe';native.write_bytes(b'Not an executable; synthetic identity only.')
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
fake=SimpleNamespace(MODEL=V4.LAUNCH.MODEL,EFFORT=V4.LAUNCH.EFFORT,CODEX=native,
 utc=lambda:'synthetic-time',sha256=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(),
 config_args=lambda config:[],clean_environment=lambda path:{},write_json=write)
with patch.object(V4,'LAUNCH',fake),patch.object(V4,'Client',return_value=client):result=V4.run(args)
assert result['native_quiescence']['qualified'] is True,result
assert result['success'] is False and result['model_started'] is True,result
print(json.dumps({'synthetic_only':True,'quiescence_qualified':True,'original_invocation_failure_preserved':True,'controls':[v['method'] for v in client.process.controls]}))
t.doCleanups()
