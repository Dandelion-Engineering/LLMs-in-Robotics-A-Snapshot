# Protected robot interface

**Interface:** `robot-codex-host-1.0`, native r4 simulation. `robot.py` requires Python 3 standard library only and imports no simulator/driver. This staging workspace has no endpoint or active permission; the trusted host configures an isolated operational copy.

Examples show syntax, not permission or recommended physical moves. Run from the runtime workspace with its launcher-provided Python. Use actual IDs and evidence, and select a stable new request ID before sending a command:

```text
python -B robot.py status
python -B robot.py history --after 0 --limit 50
python -B robot.py query ACTUAL_REQUEST_ID
python -B robot.py observe --request-id NEW_CAPTURE_ID
```

## Transport and command semantics

`live/endpoint.json` is host-published `{schema,url,capability}`, schema `robot-codex-host-1.0`. The client only accepts a literal loopback HTTP origin with explicit port, no credentials/path/query/fragment, and never follows redirects or uses proxy environment variables. It sends `X-Robot-Capability` to that origin. Do not copy the capability into notes/output.

Each client pins activation `authority_epoch` and `order_version` once and checks launch-pinned `ROBOT_AUTHORITY_EPOCH`/`ROBOT_ORDER_VERSION` when supplied. Before first physical dispatch/handback it reads status once for a current `observation_sequence`, refusing a different epoch/revision. It does not silently adopt authority, refresh a retry, poll completion or resubmit after timeout. An imported `Client` retains that dispatch fence; use a new explicitly considered invocation for new evidence. Files alone are not cryptographic per-process fencing: host token/epoch enforcement plus the launcher killing the previous generation remain essential.

`POST /command` carries `{request_id,authority_epoch,order_version,observation_sequence,action:{operation,...}}`. The host attaches native run/generation identity and owns deduplication, admission, leases and history. A reused ID must not create a second dispatch; conflicting reuse is rejected. Accepted, executing, terminal and physically verified are different. Query uncertain requests before another action; never replay automatically. A terminal motion receipt does not prove the intended grasp or placement.

All replies are JSON on stdout. Exit 0 means a received non-rejected service reply, not physical completion. Exit 3 means invalid input, unavailable read transport, or rejection. Exit 4 means a mutating response was lost/invalid and outcome is unknown. Original rejection details remain visible. Host errors use `{ok:false,error:{code,message}}`; HTTP200 with `{ok:true,command:{phase:"terminal",status:"rejected",...}}` also yields exit 3.

`--timeout SECONDS` precedes a subcommand, defaults to 5, and accepts .05-30. It is a socket inactivity limit on a blocking I/O operation, not a total wall-clock or physical-action deadline; a slow trickle can exceed it overall. The launcher provides activation lifetime bounds. Timing out does not cancel an action. Maximum request/reply sizes are 65,536/1,048,576 UTF-8 bytes. No redirects, retries or response-triggered commands occur.

## Observation and history

`GET /status` returns `{ok:true,owner,authority_epoch,order_version,observation_sequence,observation_age_s,packet,active_command,commands_recent,...}`. `Robot.md` describes public evidence. Check actual ownership and response; a note cannot grant control.

`GET /history?after=N&limit=M` reads public events after the integer cursor, CLI limit 1-200. Inspect returned IDs and gaps before advancing continuity. `GET /command/ID` resolves one request. History excludes evaluator truth, future disturbances and other trials; inspect focused relevant windows.

`POST /observe` sends the identity envelope without `action`; no fresh prior observation is needed. Query the returned request ID for terminal capture `observation_sequence`. Requested PNGs may appear under `live/observations/` with `requested_image_available` events. Open an image through a supported image tool before visual claims. A capture receipt or RGB-D detection list is not proof you inspected the PNG.

## Native skills

Binding `native-r4-cell-1` calls the protected native `Cell.submit` implementations. All skills use the common gateway and current host-granted ownership. IDs are public strings; durations depend on current planning/configuration unless noted. The protected source is not agent-editable in this workspace.

| CLI (append `--request-id NEW_ID`) / action signature | Preconditions and outcome evidence |
|---|---|
| `skill transport --part-id ID --destination ZONE` / `transport(part_id,destination,objective?)` | Fresh seen source, permitted destination, compatible fixture/task and equipment guard. Verify a new destination detection, open jaws and required process provenance. |
| `skill recover_held --destination PAD` / `recover_held(destination)` | Non-open measured jaws, existing closing command, fresh view and no observed destination occupant. PAD is parking1/parking2/inspection/quarantine. Retains grip in transport before release; reobserve possible payload identity/outcome. |
| `skill setup --family A` / `setup(family)` | A/B family, idle fixture with no observed part; old-insert return needs fresh observed home placement before fetching replacement. Verify newly seen installed family. |
| `skill cycle --part-id ID --recipe A` / `cycle(part_id,recipe)` | Eligible seated part/insert, current A/B recipe and equipment interlocks. Completion may mean cycle accepted; independent processing normally continues 8-10 seconds. Verify actual completed cycle and linked inspection. |
| `skill inspect --part-id ID` / `inspect(part_id)` | Part on inspection pad; normal instrument wait 2 seconds. Verify part, inspection and cycle IDs plus pass/rework/fail. |
| `skill observe --clear-view` / `observe(clear_view=true)` | Empty open jaws, fresh view and no visibly held object. Moves to improve visibility; query outcome and request another capture. Plain skill observe is a native no-op, not guaranteed fresh sensing. |
| `skill wait` / `wait()` | Immediate recorded no-op; no sleep, wake subscription or lease extension. |
| `skill cancel --target-request-id ACTIVE_ID` / `cancel(target_request_id)` | Current same-authority native robot action. Query target and cancellation IDs, then observe. Does not undo motion or stop an independent accepted machine cycle. |

Destination names are in `Robot.md`. Optional transport `objective`, available via `Client.command`, contains clearance .08-.25 m (default .16), speed_scale .3-1 (default .8), approach `vertical`, avoid_zones of public zone strings. CLI uses defaults. Checked public paths are not whole-arm collision certificates.

Failures include stale evidence/revision, absent ownership, busy resource, incompatible fixture, unseen object, unknown ID, IK/planning failure, deadline/lease expiry, device interlock or ineligible rework. A rejected action does not permit weakening a limit. Cancellation is described above. After terminal feedback, obtain fresh public evidence of the actual outcome.

## Manual controls

All commands below use the common gateway and native bounds. Examples may be rejected and are not movement recommendations:

```text
python -B robot.py manual move-relative --frame world --delta 0 0 0.01 --duration 0.5 --request-id EXAMPLE_MOVE
python -B robot.py manual cartesian-target --position 0.4 0.1 0.3 --duration 1.5 --request-id EXAMPLE_TARGET
python -B robot.py manual gripper --state open --duration 0.5 --request-id EXAMPLE_JAWS
python -B robot.py manual joint-position --values 0 0 0 0 0 0 0 --duration 2 --request-id EXAMPLE_JOINTS
python -B robot.py manual trajectory --waypoints-file notes/waypoints.json --request-id EXAMPLE_PATH
```

`move_relative(delta:[3],frame:"world",duration_s,gripper?)` permits Euclidean displacement <=.05 m. Host converts current public TCP telemetry to the bounded target. `cartesian_target(position:[3],duration_s,gripper?)` uses world metres and fixed orientation from `Robot.md`. `gripper(state:"open"|"close",duration_s=.5)` retains measured joint position while changing jaw command; opening may release a payload and requires reasoned placement evidence.

`joint-position`, `joint-velocity`, `joint-effort` map to `joint_command(mode,values:[7],duration_s,gripper?)`: units radians, rad/s or N m. Velocity/effort may be clipped by the native bounded adapter. Use actual telemetry/ranges, not the illustrative zero vector. Optional `--gripper 0` closes, `255` opens; omission retains the command.

`trajectory(waypoints:[{time_s,positions:[7]}],gripper?)` uses absolute simulation times/radians, at most 200 points, native joint bounds, intervals >=.01 seconds, target-speed checks and total two-second horizon. A stale time is rejected. Direct durations are .01-2 simulation seconds including planning. The machine guard prohibits direct motion during a busy guarded cycle. These interfaces do not promise whole-arm collision freedom, arbitrary orientation or force-controlled contact. Query feedback and acquire new evidence before subsequent motion.

## Workspace and execution

The read-only instruction/client/live paths are protected. The writable areas are notes/, programs/, and the canonical Continuity.md backing (.continuity/Continuity.md). Ordinary shell/Python execution within the isolated workspace is available; commands retain all robot-interface bounds. Files in writable areas persist; /tmp and process environment are fresh each invocation. No particular artifact or memory strategy is required.

Continuity.md is a fixed public symlink. Atomic replacements must target its resolved backing file, not the protected symlink. The optional `robot.py continuity --file PATH` route commits up to 32,768 UTF-8 bytes to that same surface. The framework may append a separately marked terminal receipt after accepted handback, confirmed conventional resumption and retirement, without reactivating you. That record preserves your preceding bytes.

## Handback

`python -B robot.py handback --request-id NEW_ID --reason "Evidence and remaining uncertainty"` requests release of authority. The host requires fresh evidence, idle resources, empty open jaws, no unresolved action, and a supported conventional next step. Rejection leaves ownership as returned; a successful reply fences off the old authority. End the invocation after handback or when the task cannot be completed within the available bounds.

## Camera image tool

Request a fresh observation using `robot.py observe`. Once its receipt completes and history includes `requested_image_available`, call the model-facing `robot_image` tool with that observation_sequence. The tool returns actual PNG pixels as image content plus run/session/epoch, capture time, publication event and content hash. A structured detection or file path alone does not mean the image was inspected. There is no arbitrary file/URL image route.
