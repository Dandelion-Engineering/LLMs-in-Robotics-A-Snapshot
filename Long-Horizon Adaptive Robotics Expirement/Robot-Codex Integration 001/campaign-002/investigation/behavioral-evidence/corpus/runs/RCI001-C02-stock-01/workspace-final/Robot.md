# Native simulated machine-tending robot

**Binding:** `robot-codex-integration-001` over native r4 (`Runtime 004`) components. This checked-in template is inactive until configured by the host. Documentation is not permission enforcement. This binding must not connect to real hardware.

This is a development integration description, not a qualified robot/model launch. Launcher isolation, integrated runtime operation and physical recovery outcomes have separate gates; no passing result for those gates is claimed here.

## Body and geometry

The fixed-base robot is a seven-joint Franka Panda model with parallel jaws. Skills use simulated contact and original native actuators; a request does not teleport or attach an object. Nominal part half-extents are .021, .021, .018 metres. Held-payload recovery uses the declared part/insert height bound and does not establish whether a payload is held.

Positions/translations are metres in the simulation `world` frame; positive z is up. Cartesian x/y/z are named-frame coordinates, not directions such as "right." Cartesian planning uses fixed downward rotation `diag(1,-1,-1)`; arbitrary orientation is unavailable. Joints use radians, rad/s, N m; durations use simulation seconds.

| Fixed pad | World x,y (metres) |
|---|---|
| fixture | .57, 0 |
| inspection | .34, .20 |
| parking1 | .34, .04 |
| parking2 | .46, .12 |
| tray1 | .40, .33 |
| tray2 | .61, .33 |
| tray3 | .65, -.29 |
| quarantine | .20, .29 |
| insert_home_A | .18, -.25 |
| insert_home_B | .18, -.34 |

These centres describe geometry, not current occupancy or collision-free reachability. Destination heights depend on object type, fixture and skill. Read public detections and current arm limits before movement.

## Observations and their limits

`status.packet` reports tagged detections derived from rendered overhead RGB/depth, with `capture_sim_time_s`, per-detection `age_s`, estimated position/zone/family/visible mark and uncertainty. Calibration is `B01-tag-rgbd-004`; reported sensor perturbations include .0005 m depth-noise standard deviation and a 1-DN RGB-channel offset. Missing tags mean unobserved, not absent. Occluded, stale or ambiguous objects remain uncertain.

Robot telemetry includes joint positions/velocities, actuator efforts, measured jaw width and world `tcp_position_m`. Other public fields include equipment state, current order, command feedback and inspection. Telemetry/equipment reports are not camera observations. `holding_visible_id` is a visibility/proximity inference, not a private grasp certificate. Fixture occupancy and insert identity are image-derived; equipment interlocks can reject requests without disclosing private simulator state.

`observe` requests a subsequent acquisition; query its ID for terminal capture sequence. Acquisition time is separate from request, delivery and file-publication time. Freshness-sensitive host admission requires acquisition age <=.35 seconds. The state file can lag publication; the client refreshes observation sequence before first physical dispatch while retaining the activation epoch/revision.

The host can publish requested overhead PNGs at `live/observations/overhead-<sequence>.png`, recorded by `requested_image_available`. Availability is not an image observation. `robot.py` provides no image viewer: use an actually available image tool to open the PNG before claiming to have seen it. Otherwise describe only the public RGB-D detections and telemetry you read. The checked-in template contains no measured images.

## Automation and enforced limits

The conventional public-state sequencer owns the robot until supervisor-granted recovery. Native skills are transport, insert exchange, process, inspection, clear-view and held-payload recovery through the common actuator route. Physics, sensing, equipment and lease handling continue during model/tool latency; the agent is not a motor controller tick.

The native arm adapter publishes joint/control/force ranges and TCP workspace from (.05,-.55,-.005) to (.85,.55,.80) metres. Direct commands have maximum 2-second horizon, minimum .01-second interval, at most 200 waypoints, target-speed bound 1.4 rad/s and velocity-command bound .7 rad/s. Effort uses the bounded native affine-servo inverse and may be clipped. Planning consumes the command deadline. The host's relative-motion wrapper permits `world` displacement norm <=.05 m; its gripper wrapper retains current joint positions while changing jaw command.

The host/native cell check authority, revision, freshness, equipment guard and native admission/execution boundaries. Direct motion is unavailable during a guarded busy cycle. Workspace/kinematics/joint/interlock checks and public avoidance constraints do not certify whole-arm or carried-object collision freedom. No force-controlled contact skill, hardware safety certification or whole-task robustness is implied.

## Interruption and fallback

Revocation/cancel invalidates pending planner generations and records cancellation. Native task cancellation retains its last issued position target; direct-control cancellation holds measured position. It does not generically cut power or open the jaws. An independently accepted cycle can continue with equipment interlocks. Commands expire without lawful, fresh lease renewal.

The launcher's lifetime limit terminates the agent process tree; the host owns robot lease/cancellation decisions. Killing Python alone is not a physically verified safe state. Reconcile current public records and unresolved actions after restart. Successful payload retention through every failure, full shutdown and complete task recovery need their own qualification; this binding does not claim those outcomes.
