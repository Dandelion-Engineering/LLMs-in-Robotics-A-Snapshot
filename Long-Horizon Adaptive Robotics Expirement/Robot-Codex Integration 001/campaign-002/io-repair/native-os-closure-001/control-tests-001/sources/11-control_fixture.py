"""Synthetic control client for simulated observer tests; never runs a model."""
import argparse
import json
from pathlib import Path
import time
import trace_control as t


def wait(root,phase,value,timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        item=t.receive(root,phase,value)
        if item:return item
        if phase!='finished' and t.receive(root,'finished',value):return None
        time.sleep(.005)
    raise TimeoutError('Fixture control phase timed out:'+phase)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--mode',required=True);args=parser.parse_args()
    value=t.config(args.control)
    if not wait(args.control,'helper-ready',value):return 0
    if args.mode=='no-start':
        wait(args.control,'finished',value);return 0
    if args.mode=='stop-before-start':
        t.emit(args.control,'stop',{'identity':t.own_identity()},value)
        wait(args.control,'finished',value);return 0
    if args.mode=='tamper-start':
        wrong=dict(value);wrong['key']='00'*32
        t.emit(args.control,'start',{'identity':t.own_identity()},wrong)
        wait(args.control,'finished',value);return 0
    t.emit(args.control,'start',{'identity':t.own_identity()},value)
    if not wait(args.control,'started',value):return 0
    if args.mode=='worker-exit':return 0
    if args.mode=='automatic-deadline':
        wait(args.control,'finished',value);return 0
    wrong=dict(value)
    if args.mode=='tamper-stop':wrong['key']='00'*32
    t.emit(args.control,'stop',{'identity':t.own_identity()},wrong)
    wait(args.control,'finished',value)
    return 0


if __name__=='__main__':raise SystemExit(main())
