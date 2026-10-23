"""Protected continuation predicates. No model instructions or motion policy."""
import copy
import hashlib
from common import canonical

MAX_SESSIONS=3

def assess(status, commands, physical, evidence):
    invocation=status.get('invocation') or {}
    epoch=invocation.get('authority_epoch')
    pending=[c.get('request_id') for c in commands.values()
             if c.get('actor')=='robot' and c.get('kind')=='command'
             and c.get('envelope',{}).get('authority_epoch')==epoch
             and (c.get('phase')!='terminal' or c.get('status') not in ('completed','rejected'))]
    checks={
        'normal_model_completion':evidence.get('normal_completion') is True,
        'retired_native_namespaces':evidence.get('native_retirement') is True,
        'durable_independent_journal':evidence.get('journal_verified') is True,
        'no_open_filesystem_handles':evidence.get('open_handles')==0,
        'bound_session':evidence.get('session_id')==invocation.get('invocation_id'),
        'robot_authority':status.get('owner')=='robot',
        'clean_authority_retirement':invocation.get('state')=='retired',
        'no_unresolved_request':not pending and status.get('active_command') is None,
        'safe_workcell':physical.get('safe') is True,
        'same_occurrence':physical.get('order_version')==status.get('order_version'),
        'no_accepted_handback':not any(c.get('kind')=='handback' and c.get('status')=='completed'
                                     and c.get('envelope',{}).get('authority_epoch')==epoch for c in commands.values()),
        'not_stopped':status.get('stopped') is False,
    }
    return {'safe_unresolved':all(checks.values()),'checks':checks,'unresolved_request_ids':pending,
            'session_id':invocation.get('invocation_id'),'order_version':status.get('order_version'),
            'physical':copy.deepcopy(physical),'evidence':copy.deepcopy(evidence)}

class Admission:
    """Not serialized into public state, history, framework note or template."""
    def __init__(self):self.counts={};self.permits={};self.started=set()
    def can_start(self,order,sid,duplicate=False):
        if duplicate:return True
        used=self.counts.get(order,0)
        return sid not in self.started and used<MAX_SESSIONS and (used==0 or order in self.permits)
    def started_session(self,order,sid):
        if not self.can_start(order,sid):raise ValueError('Protected admission unavailable')
        self.counts[order]=self.counts.get(order,0)+1;self.started.add(sid);self.permits.pop(order,None)
    def authorize(self,assessment):
        order=assessment['order_version']
        if assessment['safe_unresolved'] and self.counts.get(order,0)<MAX_SESSIONS:
            self.permits[order]=hashlib.sha256(canonical(assessment)).hexdigest()
            return True
        return False
