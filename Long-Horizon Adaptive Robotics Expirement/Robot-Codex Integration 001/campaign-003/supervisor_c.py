"""Add terminal evidence to the existing protected authority state machine."""
import copy
import time
import os
from common import canonical
from common import inherited_paths
inherited_paths()
from supervisor import Supervisor as OriginalSupervisor
from supervisor import require,GatewayError

class Supervisor(OriginalSupervisor):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.accepted_handbacks={};self.resumptions={};self.current_session_id=None
        self.invocation_wall_started=None

    def lifecycle(self,operation,envelope):
        previous_count=self.invocation_count
        value=super().lifecycle(operation,envelope)
        if self.invocation_count>previous_count:
            self.invocation_wall_started=time.perf_counter()
        return value

    def status(self):
        value=super().status()
        value['robot_action_budget']['limit']=getattr(self.adapter,'manifest',{}).get('robot_action_limit',20)
        return value

    def request(self,method,path,body=None):
        if method=='GET' and path.startswith('/history'):
            from urllib.parse import urlsplit,parse_qs
            query=parse_qs(urlsplit(path).query)
            after=int(query.get('after',[0])[0]);limit=min(200,max(1,int(query.get('limit',[100])[0])))
            require(after>=0,'invalid_cursor','after must be nonnegative',400)
            return {'ok':True,'events':copy.deepcopy(self.journal.events[after:after+limit]),
                    'high_water':len(self.journal.events),'gaps':[],'incomplete_tail':False}
        return super().request(method,path,body)

    def command(self, envelope, actor="robot"):
        # Same reserve/fence/normalize/durable-dispatch/feedback order as the
        # frozen parent method. Only the explicitly approved count is variable.
        record, duplicate = self.reserve(envelope, "command", actor)
        if duplicate:
            return {"ok": True, "duplicate": True, "command": copy.deepcopy(record)}
        try:
            self.fence(envelope, actor)
            action = self.normalize(envelope.get("action"))
            if actor == "robot":
                limit=getattr(self.adapter,'manifest',{}).get('robot_action_limit',20)
                require(self.robot_action_count < limit, "action_budget", f"Activation has reached its {limit} action budget", 429)
                require(self.now - self.last_robot_request >= .1, "request_rate", "Robot commands require at least 0.1 simulation seconds between requests", 429)
                self.robot_action_count += 1
                self.last_robot_request = self.now
            require(not self.active_command or action["operation"] == "cancel",
                    "resource_busy", "Another command is outstanding")
            action.update(request_id=record["request_id"], incarnation=self.epoch,
                          order_version=envelope["order_version"])
            record.update(phase="dispatched", status="pending", native_action=action,
                          dispatched_sim_time_s=self.now)
            self.emit("command_dispatched", record)
            self.journal.registry(self.commands)
            feedback = self.adapter.submit(action)
            record["admission"] = copy.deepcopy(feedback)
            if feedback["status"] != "accepted":
                record.update(phase="terminal", status="rejected", terminal_sim_time_s=self.now)
            else:
                record.update(phase="admitted", status="accepted")
                if action["operation"] != "cancel":
                    self.active_command = record["request_id"]
            self.emit("command_admission", {"request_id": record["request_id"], "feedback": feedback})
            self.journal.registry(self.commands)
            if actor == "conventional":
                self.baseline.accept_feedback(feedback)
            return {"ok": True, "command": copy.deepcopy(record)}
        except GatewayError as error:
            return {"ok": True, "command": self.failed(record, error)}
        except (ValueError, KeyError, TypeError) as error:
            return {"ok": True, "command": self.failed(record, GatewayError("native_rejected", str(error), 400))}

    def native_event(self,event):
        if event.get('type')=='operator_plant_reload':
            with (self.journal.root/'plant-events.jsonl').open('ab') as stream:
                stream.write(canonical({'run_id':self.journal.run_id,'wall_unix_ns':time.time_ns(),**event})+b'\n')
                stream.flush();os.fsync(stream.fileno())
            return
        super().native_event(event)

    def update_observation(self,packet):
        if hasattr(self.adapter,'order') and packet['order']['version']!=self.adapter.order['version']:return
        super().update_observation(packet)

    def activate(self,symptom,event_id=None):
        previous=self.owner
        super().activate(symptom,event_id)
        if previous!='robot' and self.owner=='robot' and hasattr(self.adapter,'begin_activation'):
            self.adapter.begin_activation()

    def handback(self,envelope):
        old_count=self.handoffs
        value=super().handback(envelope)
        if self.handoffs>old_count:
            receipt={**copy.deepcopy(value['command']),'run_id':self.journal.run_id,
                'session_id':self.current_session_id or (self.invocation or {}).get('invocation_id'),
                'new_authority_epoch':self.epoch,'event_id':self.journal.events[-1]['event_id'],
                'sim_time_s':self.now,'wall_unix_ns':time.time_ns()}
            self.accepted_handbacks[receipt['request_id']]=receipt
            self.emit('terminal_append_pending',{'handback_request_id':receipt['request_id'],
                'session_id':receipt['session_id'],'reason':'Await conventional resumption and namespace retirement'})
        return value

    def conventional_step(self):
        before=self.baseline_steps
        super().conventional_step()
        if self.owner=='conventional' and self.baseline_steps>before:
            for rid,accepted in self.accepted_handbacks.items():
                if rid in self.resumptions or accepted['new_authority_epoch']!=self.epoch:continue
                # A real scheduler step returned under conventional ownership.
                # Admission/terminal identities are independently retained.
                commands=[c for c in self.commands.values() if c['actor']=='conventional'
                    and c['envelope']['authority_epoch']==accepted['new_authority_epoch']
                    and c.get('requested_sim_time_s',-1)>=accepted['sim_time_s']
                    and c.get('admission',{}).get('status')=='accepted']
                if not commands:continue
                c=commands[-1]
                receipt={'run_id':self.journal.run_id,'session_id':accepted['session_id'],
                    'owner':'conventional','authority_epoch':self.epoch,'handback_request_id':rid,
                    'conventional_request_id':c['request_id'],'sim_time_s':self.now,'wall_unix_ns':time.time_ns()}
                receipt['event_id']=self.emit('conventional_resumed',receipt)
                self.resumptions[rid]=receipt
