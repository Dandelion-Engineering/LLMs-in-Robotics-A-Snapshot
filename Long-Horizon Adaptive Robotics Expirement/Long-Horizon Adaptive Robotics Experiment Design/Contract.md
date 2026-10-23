# Common experimental contract

This specifies permissions and semantics, not the organization of a candidate's reasoning or memory. A future entrant may use any internal decomposition and any permitted interface level. The harness, public services and controls are shared resources. Numerical rates are calibration targets until the workcell passes the readiness gates.

## Observations and state access

Every candidate can receive the same time-stamped RGB and metric depth images (initial target 640×480, 10 Hz), camera calibration, joint positions/velocities and gripper status (100 Hz), its command feedback, public process-station I/O and versioned orders. Contact force signals are available only if implemented uniformly as declared sensors; exact simulator contact pairs are evaluator-only. Noise, latency, occlusion, camera placement and packet-loss parameters are fixed per paired case.

The **controlled-perception first stage** also provides a frozen convenience service for visible tagged items: image-derived tag ID/pose, covariance, visibility and acquisition time. It may use AprilTag-style fiducials and depth, but must derive its output from the robot-visible images; no segmentation-ID buffer, hidden pose, object inventory, process history or off-camera object detection. Tagged objects intentionally simplify recognition. This service is not implemented or verified yet. If it proves infeasible, an explicitly labeled visible-only simulator-derived detection track may be used for debugging; it cannot silently replace the scored sensor contract. A later raw-image/perception-challenge track is separate, not pooled with the controlled stage. Candidates may ignore the convenience service or implement their own perception under the same information permissions; their development and runtime costs count.

Each packet includes episode/run ID, sensor frame, sequence number, simulator tick, acquisition and delivery wall/simulation times, calibration version and quality flags. Missing packets and stale observations remain explicit. Candidates can request fresh observations within shared bandwidth limits; this does not stop physics. They can access historical packets only if they retained them within their allowed storage or if a common public service explicitly supplies them. The evaluator's log is never a free history API.

Orders, order amendments and human answers are durable public input events available to every condition, including memory ablations. This is essential task input, not automatic reconstruction of private progress. The currently effective order and public device status can always be queried. Access does not reveal what the arm completed during a missing acknowledgement.

## Actuation without forcing one interface level

The protected actuator boundary enforces shared joint/effort/velocity limits, workspace restrictions, guard interlocks and one active command authority per resource. All candidates may use:

| Interface | Public shared support | Comparison treatment |
|---|---|---|
| Joint commands | Bounded desired positions/velocities or efforts at up to 100 Hz; common 500 Hz actuator/safety layer | Same hardware limits; caller owns command quality |
| Trajectory execution | Timestamped joint waypoints with interpolation, expiry and cancellation | Frozen executor equally available; its runtime counts |
| Cartesian targets | Optional shared IK/collision-aware path service over public geometry and sensed obstacles | Same planner/settings offered to all; no hidden-state collision oracle |
| Task motions | Optional grasp/place/inspect wrappers composed from the above | Same library available, neither mandatory nor a privileged action space |

The common physical arm model stays fixed. For the effort interface, later arena implementation must separate Menagerie's original position-servo configuration from the underlying rigid body and use an equivalent documented actuator limit/servo layer. Validate that these adapters do not change arm dynamics or grant extra control range. No winner may be explained merely by a better undocumented gripper, controller or privileged planner. Record the actual adapter/library versions used, and use a matched-executor diagnostic if needed to separate planning gains from execution gains. Full-system differences remain legitimate results; they are not automatically evidence about the LLM itself.

Candidates may change their own estimators, planners, executable behaviors, control parameters within permitted bounds, and continuity implementation. They may use supplied robotics libraries without rewriting them. They may not change bodies, sensors, machine semantics, safety bounds, initial world, disturbances, clocks, evaluation rules or protected logs during a scored run.

## Requests, interruption and ambiguity

Commands carry unique request ID, runtime incarnation ID, target resource, order version if relevant, start/deadline bounds and parent decision/event IDs. Distinguish **requested → accepted → dispatched → executing → terminal feedback → physically verified outcome**. Rejected/expired/cancelled commands are not completed actions. Terminal transport feedback is not verified physical success.

Duplicate IDs are idempotent at the dispatcher: retry returns the original acknowledgement and never re-executes. The dispatcher retains a bounded public receipt window of 60 seconds, identical across conditions, and current resource status. This transport safeguard is not a long-term task ledger. New IDs cannot be used to bypass recipe eligibility or resource ownership.

Cancel and supersede take effect only after an acknowledged control-boundary transition. Replacement commands atomically revoke the old resource lease; queued commands from an old incarnation are rejected after restart. Preemption uses a bounded deceleration or guarded hold under common limits, not a teleport or instantaneous velocity reset. A gripped object remains subject to the same physical model. The station finishes a previously accepted process safely or reports its explicit fault semantics; an arm restart does not undo machining-proxy time.

While reasoning is pending, an already accepted bounded trajectory can continue. It must carry an expiry of at most two seconds before reauthorization, with the same option for every entrant. On stale/missing command input the shared low-level layer enters a defined hold/brake state; it neither completes the task nor decides its next subtask. Fixed scripts and local controllers may renew commands while a model call is pending. The actuator boundary constrains physical permission, not where the LLM sits.

## Filesystem continuity hypothesis

All main future candidates have a persistent, candidate-writable episode filesystem, with a proposed 256 MiB consequential-context allowance excluding retained raw camera streams. The quota is an engineering cap to freeze after calibration, not a metric. File structure, serialization, retrieval, summaries, model contexts and process organization remain open. A frozen development knowledge bundle may persist across episodes; scored episodes cannot update that bundle or leak evaluation feedback into future episodes.

Durable records must enable a candidate to distinguish intent, observations/inferences, action dispatch/execution, unresolved outcomes and verified completion; preserve order corrections and reusable procedures as useful. These are **behavioral requirements**, not prescribed file names or a demanded event-sourcing architecture. Tests ask whether the returned robot continues correctly, not whether it has written all of these words.

The harness can clear model contexts, terminate candidate processes, disconnect a call, suppress an acknowledgement, and restart from the candidate's frozen entry point plus whatever the condition permits on disk. Process death clears volatile state and pending model output. Candidate files may contain partial writes; atomicity/recovery choices belong to the later implementation. The evaluator captures crash boundaries and snapshots externally. All candidates have equal opportunities to use file flush/rename primitives; no harness service reconstructs their private memory.

After restart, the system must reconcile surviving records with current observations and public device state. Durable but stale beliefs are not authoritative. The experiment covers a context change, a process crash, and an absence during which the world changes; these are different interventions. An unresolved placement should not be silently called done, repeated indiscriminately or abandoned forever.

## Time moves while the system thinks

One protected supervisor owns physics and machine time. A separate candidate process communicates through bounded IPC. Initial targets: 2 ms physics steps, 100 Hz command admission, 10 Hz camera streams, monotonic wall clock plus simulation tick on every event. Image acquisition and inference timestamps are independent; faster action generation is not fresher feedback.

**Actual-host timing track:** one second of simulation represents one wall-clock second. Inference, filesystem access, planning and observation handling consume actual time while the world advances. Log real-time factor and per-interval lag. Readiness target: cumulative lag below 100 ms and less than 1% of one-second windows outside real-time factor 0.95–1.05, excluding declared launch initialization. Freeze achievable tolerances before scoring. If the shared host prevents them, label the run infrastructure-invalid, preserve evidence and rerun in its scheduled slot. Do not pause the world or selectively excuse only one candidate's slow inference. Candidate-induced starvation within its resource quota is a candidate resource failure; evaluator/host contention outside the quota is infrastructure failure.

**Controlled-delay diagnostic:** inject declared response-availability delays of 0, 0.25, 1, 3 and 10 simulated seconds into a bounded diagnostic subset. With live inference the release time is no earlier than both actual readiness and the injected minimum; extra delay is logged. Recorded-output replay can impose exact delays only while inputs/actions remain identical; diverged policy rollouts require new inference and cannot claim exact counterfactual outputs. Delayed physics stays active. A paused-world run is an explicitly labeled diagnostic of free thinking time, never the primary responsiveness result.

No remote model/API is assumed or authorized at this stage. Later model selection must fit verified commercial terms and zero new spending; any external access or cost needs Randy's authorization under Project Details. Simulation CPU work should leave GPU headroom, but full-cell plus inference throughput remains unmeasured.

## Evaluator and generated-code boundary

The evaluator privately reads exact object IDs/poses, contact/containment, recipe and cycle histories, hidden inspection outcomes, disturbance schedule and scoring rules. A sensor gateway publishes only allowed observations. Candidates cannot call simulator internals or read evaluator files. Protected manifests are hashed before and after the run. Blocked forbidden read/write/network/process attempts count as candidate contract failures and remain in failure denominators. An actual isolation breach, exposed oracle or evaluator corruption is an infrastructure-invalid paired block, separately reported with the responsible violation retained. Holding out files by convention or using Windows read-only flags under the same unrestricted user is **not** a secure sandbox.

If a later candidate generates or modifies code, run that code only inside a validated isolated environment with bounded CPU/RAM/storage/processes, no network by default, no host filesystem mounts except allowed input/writable candidate areas, and only the same actuator IPC. The evaluator and secrets remain outside it. Validate attempted forbidden read/write/network/process access before scored runs. The isolation mechanism is a later harness implementation choice; native Windows Home support is unresolved. Until an effective boundary exists, unrestricted generated-code trials are development-only and cannot be represented as protected scored comparisons.

Common minimum run envelope proposed for calibration: one candidate at a time, at most 8 GiB candidate host RAM plus 4 GiB harness budget, at most four CPU cores for candidate runtime, and at most 12 GiB GPU memory when a model is later selected. Reserve the rest for OS/display/shared work; queue scheduling determines actual access. Cap violations and timeouts count, with causes logged. Revise these defaults openly during shared calibration, then freeze them equally before comparisons.
