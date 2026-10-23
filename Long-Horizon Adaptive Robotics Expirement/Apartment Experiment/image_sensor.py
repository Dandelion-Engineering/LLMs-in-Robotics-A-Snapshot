"""Bound explicit camera delivery; excludes private reasoning from recorded events."""
import base64
import json
TOOL={'type':'function','name':'robot_image','description':'View the robot head RGB-D or wrist RGB image from an explicit observation. Supply the exact observation_sequence returned by the public observe command.',
      'inputSchema':{'type':'object','properties':{'observation_sequence':{'type':'integer','minimum':1}},'required':['observation_sequence'],'additionalProperties':False}}

class ImageSensor:
    def __init__(self,controller):self.controller=controller;self.thread_id=None;self.turn_id=None;self.retired=False
    def bind(self,thread_id,turn_id):
        if self.thread_id:raise ValueError('Image binding already set')
        self.thread_id,self.turn_id=thread_id,turn_id
    def call(self,params):
        if self.retired or (params.get('threadId'),params.get('turnId'))!=(self.thread_id,self.turn_id) or params.get('tool')!='robot_image':raise ValueError('Image invocation mismatch')
        args=params['arguments'];args=json.loads(args) if isinstance(args,str) else args
        if set(args)!={'observation_sequence'} or type(args['observation_sequence']) is not int:raise ValueError('Exact image sequence required')
        raw=self.controller.ask('image',args['observation_sequence'])
        return dict(success=True,contentItems=[{'type':'inputText','text':'Robot sensor image, observation '+str(args['observation_sequence'])},
                    {'type':'inputImage','imageUrl':'data:image/png;base64,'+base64.b64encode(raw).decode()}])

def observable(value):
    if not isinstance(value,dict):return value
    if 'reasoning' in value.get('type','').lower() or 'reasoning' in value.get('method','').lower():return None
    item=value.get('params',{}).get('item',{})
    if isinstance(item,dict) and 'reasoning' in item.get('type','').lower():return None
    result={}
    for key,child in value.items():
        if any(x in key.lower() for x in ('reasoning','encryptedcontent','encrypted_content')):continue
        if isinstance(child,dict):child=observable(child)
        elif isinstance(child,list):child=[y for x in child if (y:=observable(x)) is not None]
        result[key]=child
    return result
