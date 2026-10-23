"""Prospective namespace: v0.2 writable state, protected contracts, no host roots."""
from pathlib import Path
import sys

def main():
    # Trusted parent supplies source and repository; they are never guest mounts.
    i=sys.argv.index('--repo');repo=Path(sys.argv[i+1]);del sys.argv[i:i+2]
    here=Path(__file__).resolve().parent
    integration=repo/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001'
    boundary=integration/'readiness-session-10/boundary';harness=integration/'campaign-002/harness'
    sys.path.insert(0,str(boundary));sys.path.insert(0,str(harness))
    import linux_entry
    from namespace import command as original
    from codehost_entry_v3 import replace_inside
    def validate(workspace):
        w=Path(workspace)
        if w.parent.parent!=Path('/var/tmp/robot-codex-session10') or not w.parent.name.startswith('apartment-') or w.name!='workspace' or w.resolve()!=w:
            raise ValueError('Unexpected apartment workspace')
        if not (w/'RobotAgentPrompt.md').is_file():raise ValueError('Runtime prompt missing')
        return w
    def command(workspace,sock,source,executable,codehost):
        args=original(workspace,sock,boundary,executable,codehost)
        w=Path(workspace)
        for directory in ('notes','programs','.continuity'):
            at=args.index(str(w/directory))-1;del args[at:at+3]
        at=args.index(str(w))-1;args[at]='--bind'
        # Carry forward the already-qualified native codehost drain/retirement transport.
        if sys.argv[1]=='codehost':
            args=replace_inside(args,boundary/'inside.py',here/'transport_inside.py',harness/'codehost_mux_protocol.py',harness/'native_cleanup_protocol.py')
            at=args.index('--remount-ro')
            args[at:at]=['--ro-bind',str(harness/'codehost_inside_v3.py'),'/inherited_inside.py',
                         '--ro-bind',str(here/'frame_digest.py'),'/frame_digest.py',
                         '--ro-bind',str(here/'h2_runtime.py'),'/h2_runtime.py',
                         '--ro-bind',str(here/'flow_control.py'),'/flow_control.py']
        for filename in ('canary.py','codehost_canary.py'):
            at=args.index('/'+filename);args[at-1]=str(here/'guest_probe.py')
        at=args.index('--remount-ro');bindings=['--ro-bind',str(here/'robot_client.py'),'/robot_client.py']
        for name in ('RobotAgentPrompt.md','RobotDetails.md','ProjectDetails.md','Programs/Default','Playbooks/Default'):
            bindings+=['--ro-bind',str(w/name),'/workspace/'+name]
        # Earlier episodic reports are individually immutable; new reports remain writable.
        for report in sorted((w/'SessionReports').iterdir()):
            if report.is_file():bindings+=['--ro-bind',str(report),'/workspace/SessionReports/'+report.name]
        args[at:at]=bindings
        return args
    linux_entry.validate_workspace=validate;linux_entry.command=command
    linux_entry.main()

if __name__=='__main__':main()
