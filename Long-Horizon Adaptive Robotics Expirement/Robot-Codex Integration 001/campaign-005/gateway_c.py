"""Operator-only sequencing; robot route vocabulary stays unchanged."""
import copy
import hashlib
from scheduler import Schedule
from supervisor import GatewayError,require,canonical
from continuation import Admission,assess
from common import save

def validate_manifest(m):
    required={'run_id','seed','noise_seed','schedule_seed','encounters','initial_order','sim_cap_s','wall_cap_s','storage_cap_bytes','mode'}
    if not required<=set(m) or m['mode']!='serve' or m['encounters']<3:raise ValueError('Bounded C004 serve manifest required')
    if m['initial_order']!=Schedule(m['schedule_seed'],m['encounters']).current:raise ValueError('Initial order mismatch')
    if 'runtime_envelope_sha256' in m:
        from runtime_limits import validate_limits
        validate_limits(m)
    else:
        if not 100<=m['sim_cap_s']<=4000 or not m['sim_cap_s']<m['wall_cap_s']<=5000:raise ValueError('Time bounds')
        if not 100_000_000<=m['storage_cap_bytes']<=512*1024**2:raise ValueError('Evidence bounds')
    return m

def extend_gateway(Base):
    class Gateway(Base):
        def __init__(self,*args,manifest,**kwargs):
            super().__init__(*args,**kwargs)
            self.schedule=Schedule(manifest['schedule_seed'],manifest['encounters']);self.terminal_sessions={};self.stage_receipts={}
            self.admission=Admission()

        def operator_request(self,s,mail):
            route=mail.path.removeprefix('/operator/')
            if mail.method=='GET' and route=='continuation-state':
                return {'ok':True,'physical':s.adapter.worker.rpc('continuation_state')}
            if mail.method=='POST' and route=='authorize-continuation':
                physical=s.adapter.worker.rpc('continuation_state')
                result=assess(s.status(),s.commands,physical,mail.body)
                allowed=self.admission.authorize(result)
                result['admitted']=allowed
                save(s.journal.root/('continuation-'+str(result['session_id'])+'.json'),result)
                return {'ok':True,**result}
            if mail.method=='GET' and route=='outcome':return {'ok':True,'outcome':s.adapter.outcome(),'order':s.adapter.order}
            if mail.method=='GET' and route.startswith('terminal/'):
                rid=route.split('/',1)[1]
                return {'ok':True,'accepted':copy.deepcopy(s.accepted_handbacks.get(rid)),
                        'resumed':copy.deepcopy(s.resumptions.get(rid))}
            if mail.method=='POST' and route=='framework-terminal':
                require(s.invocation and s.invocation['state']=='retired','not_retired','Namespace retirement must precede publication')
                receipt=mail.body['receipt'];record=receipt['record'];rid=record['handback_request_id']
                require(rid in s.resumptions and record['session_id']==s.invocation['invocation_id'],'unbound_terminal','Wrong terminal identity')
                content=mail.body['content'];require(hashlib.sha256(content.encode()).hexdigest()==receipt['after_sha256'],'terminal_hash','Wrong note bytes')
                result=s.journal.framework_continuity(content);self.terminal_sessions[record['session_id']]=receipt
                s.emit('framework_terminal_appended',{'receipt':receipt,'canonical_sha256':result['sha256']})
                return {'ok':True,**result}
            if mail.method=='POST' and route=='stage-next':
                rid=mail.body.get('request_id');require(isinstance(rid,str) and len(rid)<=128,'request_identity','Bounded request ID required')
                if rid in self.stage_receipts:return self.stage_receipts[rid]
                require(mail.body.get('order_version')==s.adapter.order['version'],'stale_order','Stage request must match current order')
                require(s.owner=='conventional' and not s.active_command and not s.adapter.busy(),'busy_boundary','Job change requires idle conventional ownership')
                require(s.adapter.outcome()['success'],'incomplete_job','Independent task acceptance required')
                if s.adapter.order['kind']=='C-placement':
                    require(s.invocation and s.invocation['state']=='retired' and s.invocation['invocation_id'] in self.terminal_sessions,
                            'incomplete_terminal','Accepted handback, resumption, retirement and terminal append required')
                nxt=self.schedule.advance()
                if nxt is None:result={'ok':True,'block_complete':True}
                else:
                    result={'ok':True,'block_complete':False,**s.adapter.stage_job(nxt,reload_c=nxt['kind']=='C-placement')}
                    s.emit('job_released',{'order':nxt,'prior_order_version':mail.body['order_version']})
                self.stage_receipts[rid]=result;return result
            if route=='start-invocation':
                duplicate=mail.body.get('request_id') in s.commands
                require(self.admission.can_start(s.adapter.order['version'],mail.body.get('invocation_id'),duplicate),
                        'admission_unavailable','Protected invocation admission unavailable')
            result=super().operator_request(s,mail)
            if route=='start-invocation' and result.get('command',{}).get('status')=='completed':
                s.current_session_id=mail.body['invocation_id']
                if not result.get('duplicate'):self.admission.started_session(s.adapter.order['version'],s.current_session_id)
            return result
    return Gateway
