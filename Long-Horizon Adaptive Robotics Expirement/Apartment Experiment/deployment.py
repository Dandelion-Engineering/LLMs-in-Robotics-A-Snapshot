"""Instantiate the two supplied conditions without learned spatial/task knowledge."""
import argparse
from pathlib import Path
import shutil
from common import HERE, REPO, save, inventory, sha

ROBOT_DETAILS = '''# Apartment robot: embodiment and interfaces

You operate a simulated wheeled mobile base with one Cartesian arm, pitch wrist and parallel gripper. The common apparatus uses MuJoCo rigid-body/contact physics. The wheels are represented by a planar servo base (wheel slip and uneven terrain are outside this experiment). The arm has vertical, forward and lateral linear joints. No ground-truth apartment localization or object identifiers are available.

## Sensing

Use `python3 /robot_client.py status` for battery, current assignment, measured joint encoders, gripper width/effort, contact/lift feedback, noisy IMU and dead-reckoned odometry. Odometry is relative to the initial robot frame, may drift, and is not a surveyed map. Use observations to reconcile it.

`python3 /robot_client.py observe '{"camera":"head_rgbd"}'` returns an observation sequence, a coarse metric depth grid, 72 planar lidar ranges and current status. `wrist_rgb` selects the wrist camera. Use the `robot_image` tool with the returned observation sequence to actually inspect the corresponding RGB pixels. A successful observation command does not itself mean you have viewed the image. RGB, depth, range, encoders and IMU include noise. Images provide ordinary visual semantics; the interface supplies no room labels or object poses.

`python3 /robot_client.py point '{"observation_sequence":1,"u":240,"v":200}'` projects a selected image pixel through noisy depth into an estimated point in the robot base frame. Pixel origin is upper left. The point is a visible surface, not necessarily an object's center. Camera motion and object motion can make old observations stale; points older than 30 simulated seconds are rejected. The body calibration is known but environmental truth is not.

## Primitive control vocabulary

Invoke `python3 /robot_client.py command '{"kind":"...","parameters":{...}}'`. Each invocation creates a request ID. One physical action is admitted at a time. Poll status until it ends; a request receipt is not proof of the intended physical effect. Inspect the world after motion.

- `base`: `forward` in meters (absolute limit 1.5 per segment), or `turn` in radians (absolute limit pi). Positive forward is the current body x axis; positive turn is counterclockwise. Use one straight or rotating segment. Speed limits are .22 m/s and .6 rad/s. Retract arm reach to at most .48 m before driving. Avoid obstacles using RGB-D/lidar. Bounded segments do not plan a route for you.
- `head`: absolute `pan` (minus pi to pi) and `tilt` (minus 1.2 to 1.2) radians. Zero pan looks forward; positive tilt looks downward.
- `arm`: `x`, `y`, `z` meters in the base frame, optional `pitch` radians and `duration` seconds. x .20–1.03, y -.45–.45, z .02–1.35, pitch -1.4–1.4. z is measured above the floor plane of the base. It is a controlled Cartesian motion; collision/contact may prevent reaching a target. The arm does not plan around obstacles.
- `gripper`: total desired `width` in meters, 0–.15, optional `duration`. Gripping requires actual contacts and a successful lift. Requested closure is not proof of acquisition. Contact effort, measured opening and lift feedback help assess it.
- `trajectory`: `points`, an ordered list of 1–64 ordinary arm waypoints. Each has x,y,z,duration; optional pitch and width. Segment duration .05–30 s. Gripper and arm interpolation run together, allowing you to choose your own motion and release timing. No task-specific trajectory is supplied.
- `wait`: duration .05–60 s. Physics and time-dependent battery continue during thinking, commands and waits.
- `dock`: succeeds only when the stationary base is physically on a charging pad and the low-battery warning has occurred. Drive there normally. The command does not navigate or teleport. On acceptance, physical control closes for this invocation and filesystem closeout begins.
- `reset_object`: during the throwing assignment only, after releasing the exercise object. The external practice mechanism returns the object to its fixed starting pedestal. This is an explicit task reset, not a general world-edit interface.

All commands reject malformed/out-of-range input. No operator, scheduler, filesystem-export, hidden evaluation or arbitrary network interface is available through the robot client. Programs may invoke the same client from Python using `import sys; sys.path.insert(0,"/"); import robot_client` and `robot_client.call(action, parameters)`. The client is a transport to primitives; low-level controller implementations remain outside this filesystem.

The supplied reusable grasp-positioning capability is indexed in `Playbooks/Index.md`; its responsibility ends before closure. No learned closure values, drawer procedures or throwing routine are supplied.
'''

PROJECT_DETAILS = '''# Apartment deployment

Operate the apartment robot through current observations and its persistent filesystem. Assignments are externally selected and not known in advance. Read the current assignment from the robot status interface. Do not assume which assignment comes next.

Tasks include putting four distinct toys into the bedroom toy chest, putting a cup from one of three kitchen countertop mats into the requested drawer A or B, and a living-room practice period for learning to throw an object into a bin. The two drawers carry visible A/B markings. You must discover their operation from perception and interaction. The four toys and the cup recur, but their dimensions are not provided. Normal task completion is accepted only from physical state, including actual pickup and containment. Touching an object or declaring success does not complete the task.

For throwing, ordinary arm/gripper controls let you select candidate motions and releases. After landing, feedback gives inside-bin status and signed landing displacement relative to the bin. It describes the result; it does not prescribe improvements. Reset is available for another attempt. This is a bounded practice assignment; work usefully until its battery warning even if a throw has already succeeded.

## Time, charging and session boundaries

Battery depends on elapsed simulation/session time only, not distance, effort or actions. It continues while you think. The household working window is fixed after engineering calibration. Throwing has a longer fixed working window. Neither window is shortened as you improve. Current battery and work time remaining are available in status.

At the low-battery warning, wrap up nonessential physical work and proceed promptly to a charging station. There are charging stations in the bedroom, kitchen and living room. Identify them from their visible green pad, yellow mark and charging backstop, then navigate and dock normally. The warning reserves enough simulated time for a prompt return from every normal permitted location, including conservative decision overhead; it is a reliable wrap-up signal. Do not spend that reserve continuing the assignment.

Successful docking triggers your normal end-of-invocation routine in RobotAgentPrompt.md. Complete the session report and continuity/memory/playbook/program maintenance, then end normally. The next fresh session will start physically at that charger, recharged, with this persistent filesystem. Unfinished normal tasks resume. After a normal task succeeds, preserve the result and use remaining work time for useful observation or artifact maintenance until the warning; the next assignment is issued at the next fresh session. The throwing assignment advances after its ordinary warning, docking, filesystem closeout and clean session end regardless of throwing success.

Do not terminate early merely because a task is finished or a future invocation might continue it. Do not alter the protected runtime contract or prior session reports. Your ordinary writable files, Maps when present, learned playbooks/programs and new session reports are available for grounded memory. There is no external communication, Internet access, host filesystem access, or authority to change the simulator/evaluator.

An observer may watch or close a separate viewer. This has no effect on your sensors, task or session responsibilities. Operator controls are outside your interface.
'''

POSITION_PLAYBOOK = '''# Position an open gripper from perception

Scope: generic grasp positioning for a reachable object; no closure or acquisition decision.

Inspect the RGB-D observation and estimate an appropriate grasp point in the base frame. Pixel-to-point is available in the primitive client, but returns a surface; reason about visible geometry before choosing a center and height. Ensure a collision-free approach and place the base within reach.

Run `python3 Programs/Default/position_grasp.py --x X --y Y --z Z`. This requests an open .15 m aperture and a Cartesian approach at the provided perception-derived coordinates. It stops before closure. Poll status and inspect alignment. You decide closure using live measured width, effort, contact and lifting feedback. It contains no object identities, dimensions, drawer procedure or throw parameters.

Implementation: Programs/Default/position_grasp.py invokes the protected position_grasp control. Evidence and limits: engineering qualification covers aperture remaining open and geometric positioning; noisy depth, occlusion and collisions can still prevent a valid grasp. It does not certify task success.
'''

POSITION_PROGRAM = '''import argparse,sys
sys.path.insert(0,"/")
from robot_client import call
p=argparse.ArgumentParser()
for key in ("x","y","z"):p.add_argument("--"+key,type=float,required=True)
a=p.parse_args()
print(call("command",{"kind":"position_grasp","parameters":vars(a)}))
'''

def instantiate(condition, output, repo=REPO):
    if condition not in ('baseline','maps'):raise ValueError('Unknown condition')
    output=Path(output)
    source=Path(repo)/('Robot Agent Filesystem Draft v0.2'+(' Maps Edition' if condition=='maps' else ''))
    if output.exists():raise ValueError('Refusing to overwrite a deployment')
    shutil.copytree(source,output,ignore=shutil.ignore_patterns('Setup.md'))
    for name,content in [('RobotDetails.md',ROBOT_DETAILS),('ProjectDetails.md',PROJECT_DETAILS),
                         ('SummaryOfOnlyNecessaryContext.md','# Initial continuity\n\nThis is the first robot-agent session for this deployment. There are no prior robot-agent session reports. This summary was populated before launch by the deployment operator, not by a previous robot-agent session.\n\nRead the canonical startup files, inspect current robot status and sensors, and carry out the current external assignment. Establish location and task state from current sensing. No learned world knowledge has been supplied.\n'),
                         ('Playbooks/Default/PositionGrasp.md',POSITION_PLAYBOOK),('Programs/Default/position_grasp.py',POSITION_PROGRAM)]:
        (output/name).write_text(content,encoding='utf-8',newline='\n')
    index=output/'Playbooks/Index.md'
    index.write_text('# Playbook index\n\n| Capability | Scope | Playbook | Implementation |\n|---|---|---|---|\n| Position open gripper | Perceived reachable target; stops before closure | [PositionGrasp](Default/PositionGrasp.md) | Programs/Default/position_grasp.py |\n\nNo learned capabilities have been registered.\n',encoding='utf-8')
    readme=output/'README.md';text=readme.read_text(encoding='utf-8')
    text=text.replace('│   │   └── README.md','│   │   ├── README.md\n│   │   └── PositionGrasp.md')
    text=text.replace('    │   └── README.md','    │   ├── README.md\n    │   └── position_grasp.py')
    text+='\nThe supplied PositionGrasp default playbook and position_grasp.py program implement only perception-directed open-gripper positioning. Primitive client code is mounted at /robot_client.py by the robot stack and is outside this persistent filesystem.\n'
    readme.write_text(text,encoding='utf-8',newline='\n')
    verify(condition,output,source)
    return inventory(output)

def verify(condition,output,source):
    assert not (output/'Setup.md').exists()
    assert sha(output/'RobotAgentPrompt.md')==sha(source/'RobotAgentPrompt.md')
    assert sorted(p.name for p in (output/'SessionReports').iterdir())==['SessionReportTemplate.md']
    assert all(sorted(p.name for p in (output/d).iterdir())==['README.md'] for d in ('Programs/Learned','Playbooks/Learned'))
    if condition=='maps':
        assert inventory(output/'Maps')==inventory(source/'Maps')
    else:assert not (output/'Maps').exists()
    assert sha(output/'LongTermMemory.md')==sha(source/'LongTermMemory.md')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('condition',choices=['baseline','maps']);p.add_argument('output',type=Path);a=p.parse_args()
    print(instantiate(a.condition,a.output))
