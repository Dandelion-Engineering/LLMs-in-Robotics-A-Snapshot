"""Prospective error evidence adapter; no model retry, fallback or prompt change."""
import json
from common import save


def sanitized(value,tokens):
    raw=json.dumps(value,ensure_ascii=False)
    for token in tokens:
        if token:raw=raw.replace(token,'[REDACTED_EPHEMERAL_CAPABILITY]')
    return json.loads(raw)


class FailureTrace:
    def __init__(self,tokens=()):
        self.tokens=tokens;self.phase='native-initialization';self.errors=[]
        self.thread_id=None;self.turn_id=None;self.terminal=None;self.activity=False

    def observe(self,row):
        method=row.get('method');p=row.get('params',{})
        if method in ('thread/start','turn/start') and row.get('kind')=='request':self.phase=method
        if method=='turn/started':
            self.phase='active-turn';self.thread_id=p.get('threadId');self.turn_id=p.get('turn',{}).get('id')
        if row.get('kind')=='public_tool_call':self.activity=True
        if method in ('item/started','item/completed'):
            kind=p.get('item',{}).get('type')
            if kind in ('agentMessage','commandExecution','dynamicToolCall','mcpToolCall','fileChange'):self.activity=True
        if method=='error' and row.get('kind')=='notification':
            detail={k:p.get(k) for k in ('error','willRetry','threadId','turnId')}
            if len(self.errors)<8:self.errors.append(sanitized(detail,self.tokens))
        if method=='turn/completed' and row.get('kind')=='notification':
            turn=p.get('turn',{})
            self.terminal=sanitized({k:turn.get(k) for k in ('id','status','error','durationMs','startedAt','completedAt')},self.tokens)
            self.thread_id=p.get('threadId',self.thread_id);self.turn_id=turn.get('id',self.turn_id)
        if row.get('kind')=='rpc_error':
            if len(self.errors)<8:self.errors.append(sanitized({k:row.get(k) for k in ('method','code','message')},self.tokens))

    def detail(self,fallback):
        native=(self.terminal or {}).get('error')
        if native is None and self.errors:native=self.errors[-1].get('error',self.errors[-1])
        return dict(schema='apartment-native-failure-1',phase=self.phase,thread_id=self.thread_id,
            turn_id=self.turn_id,native_error=native,terminal=self.terminal,notifications=self.errors,
            retry_disposition=self.errors[-1].get('willRetry') if self.errors else None,
            recorded_assistant_or_tool_activity=self.activity,runtime_error=str(fallback),
            automatic_retry=False,model_fallback=False)


def message(detail):
    native=detail.get('native_error')
    if isinstance(native,dict):
        code=native.get('codexErrorInfo',native.get('code','unknown-native-code'))
        return str(code)+': '+str(native.get('message',detail['runtime_error']))
    return detail['runtime_error']


def install(module):
    inherited=module.Client;original_run=module.run
    class Client(inherited):
        def __init__(self,args,*a,**kw):
            self.failure_trace=FailureTrace(getattr(args,'redact_tokens',()))
            args.apartment_failure_trace=self.failure_trace
            super().__init__(args,*a,**kw)
        def log(self,value):
            # Use the inherited filtering/redaction before recording metadata.
            super().log(value)
            self.failure_trace.observe(value)
        def wait_turn(self,turn_id):
            completed=super().wait_turn(turn_id)
            if completed.get('status')!='completed':
                raise RuntimeError(message(self.failure_trace.detail('Native turn '+str(completed.get('status')))))
            return completed
    def run(args):
        result=original_run(args)
        if not result.get('success'):
            trace=getattr(args,'apartment_failure_trace',FailureTrace())
            detail=trace.detail(result.get('error','Native invocation failed'))
            result.update(structured_failure=detail,error=message(detail))
            if trace.terminal is not None:result['turn_status']=trace.terminal['status']
            save(args.evidence/'result.json',result)
        return result
    module.Client=Client;module.run=run
    return Client
