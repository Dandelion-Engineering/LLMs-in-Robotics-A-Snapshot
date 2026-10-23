"""Prevent old rendered C-pad pixels from completing a newly loaded C job."""
from contextlib import nullcontext
from types import SimpleNamespace
from apparatus import conventional_decision

def check():
    calls=[]
    adapter=SimpleNamespace(order={'version':8},now=135.8,order_capture_boundary=135.656)
    s=SimpleNamespace(adapter=adapter,commands={},active_command=None,
        packet={'order':{'version':8},'capture_sim_time_s':135.656},
        conventional_step=lambda:calls.append('decision'))
    capture=SimpleNamespace(phase=lambda *a:nullcontext())
    for t in (135.555,135.655,135.656):
        s.packet['capture_sim_time_s']=t
        assert conventional_decision(s,0,capture)==0 and not calls
    s.packet['capture_sim_time_s']=135.698
    assert conventional_decision(s,0,capture)==136.0 and calls==['decision']
    s.packet['order']['version']=7
    assert conventional_decision(s,0,capture)==0 and calls==['decision']
    return dict(passed=True,model_calls=0,checks=5,
        scope='Pre-boundary, equal-tick and wrong-order frames cannot trigger conventional decisions; a fresh later capture can.')

if __name__=='__main__':print(check())
