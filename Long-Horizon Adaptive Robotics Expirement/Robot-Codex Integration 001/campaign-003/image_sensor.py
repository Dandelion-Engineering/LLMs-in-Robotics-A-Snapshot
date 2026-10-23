"""Narrow app-server dynamic image tool; no arbitrary file/URL capability."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
from common import canonical

TOOL={'type':'function','name':'robot_image','description':'Inspect an overhead camera image from an explicit robot observation. Supply its observation sequence. Structured observations remain available.',
      'inputSchema':{'type':'object','properties':{'observation_sequence':{'type':'integer','minimum':0}},
                     'required':['observation_sequence'],'additionalProperties':False}}

class ImageSensor:
    def __init__(self,workspace,journal,run_id,session_id,authority_epoch):
        self.workspace=Path(workspace);self.journal=journal
        self.run_id,self.session_id,self.epoch=run_id,session_id,authority_epoch
        self.thread_id=self.turn_id=None;self.retired=False

    def bind(self,thread_id,turn_id):
        if self.thread_id is not None:raise ValueError('Image tool context may only bind once')
        self.thread_id,self.turn_id=thread_id,turn_id

    def call(self,params):
        if self.retired or self.thread_id is None or (params.get('threadId'),params.get('turnId'))!=(self.thread_id,self.turn_id):
            raise ValueError('Retired or mismatched image invocation')
        if params.get('tool')!='robot_image' or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}',params.get('callId','')):
            raise ValueError('Wrong image tool or call identity')
        args=params.get('arguments')
        if isinstance(args,str):args=json.loads(args)
        if not isinstance(args,dict) or set(args)!={'observation_sequence'} or type(args['observation_sequence']) is not int or args['observation_sequence']<0:
            raise ValueError('Exact observation sequence required')
        sequence=args['observation_sequence']
        matches=[e for e in self.journal.events if e['type']=='requested_image_available' and e['payload']['observation_sequence']==sequence]
        if len(matches)!=1:raise ValueError('No unique published observation image')
        event=matches[0];meta=event['payload']
        if event['authority_epoch']!=self.epoch:raise ValueError('Image belongs to another authority epoch')
        path=self.workspace/('live/observations/overhead-'+str(sequence)+'.png')
        if path.is_symlink() or path.resolve().parent!=(self.workspace/'live/observations').resolve():raise ValueError('Image path alias')
        raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if len(raw)>1048576 or not raw.startswith(b'\x89PNG\r\n\x1a\n') or sha!=meta['sha256'] or len(raw)!=meta['bytes']:
            raise ValueError('Image identity or size mismatch')
        receipt={'schema':'campaign003-image-view-1','run_id':self.run_id,'session_id':self.session_id,
                 'authority_epoch':self.epoch,'thread_id':self.thread_id,'turn_id':self.turn_id,'call_id':params['callId'],
                 'publication_event_id':event['event_id'],'view_wall_unix_ns':time.time_ns(),
                 'view_windows_perf_ns':time.perf_counter_ns(),**meta}
        with (self.journal.root/('image-views-'+self.session_id+'.jsonl')).open('ab') as stream:
            stream.write(canonical(receipt)+b'\n');stream.flush();os.fsync(stream.fileno())
        return {'success':True,'contentItems':[{'type':'inputText','text':json.dumps(receipt,sort_keys=True)},
                 {'type':'inputImage','imageUrl':'data:image/png;base64,'+base64.b64encode(raw).decode()}]}

def observable(value):
    """Exclude private reasoning before serialization, including completed items."""
    if not isinstance(value,dict):return value
    if value.get('type','').lower() in ('reasoning','reasoningsummary'):return None
    method=value.get('method','')
    if 'reasoning' in method.lower():return None
    item=value.get('params',{}).get('item',{})
    if isinstance(item,dict) and item.get('type','').lower() in ('reasoning','reasoningsummary'):return None
    if value.get('kind')=='notification':
        allowed={'item/started','item/completed','item/agentMessage/delta','item/commandExecution/outputDelta',
                 'item/fileChange/outputDelta','turn/started','turn/completed','thread/started',
                 'thread/tokenUsage/updated','error'}
        if method not in allowed:return {'kind':'omitted_notification','method':method}
    result={}
    for k,v in value.items():
        if any(s in k.lower() for s in ('reasoning','encryptedcontent','encrypted_content')):continue
        if isinstance(v,dict):v=observable(v)
        elif isinstance(v,list):v=[y for x in v if (y:=observable(x)) is not None]
        result[k]=v
    return result
