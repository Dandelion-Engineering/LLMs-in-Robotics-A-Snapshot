# Apartment robot: embodiment and interfaces

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
