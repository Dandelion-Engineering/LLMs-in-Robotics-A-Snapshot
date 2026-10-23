# Protected development host API

The protected host owns the frozen workcell and conventional controller. No account credentials are loaded here. `live/endpoint.json` contains `schema`, `url` (literal `http://127.0.0.1:<port>`) and a random local `capability`. Send it in `X-Robot-Capability`. Endpoint capabilities rotate at authority changes; never archive a live token in Git or tool transcripts. This is access to one local robot service, not an OpenAI credential.

Success replies have `ok:true`. Errors have `ok:false,error:{code,message}` and a non-2xx status. A valid command request can return HTTP 200 with `command.status=rejected`; inspect command status, not HTTP status alone. Body limit is 64 KiB; a request is a JSON object. No redirects or arbitrary paths/URLs are accepted.

| Endpoint | Contract |
|---|---|
| `GET /status` | Root `owner`, `authority_epoch`, `order_version`, `observation_sequence`, `observation_age_s`, `packet`, `active_command`, recent commands and history cursor. Packet contains public image-derived detections, public devices, measured joints, jaw width and `tcp_position_m` in world coordinates. |
| `GET /continuity` | Exact current note content, UTF-8 byte count and SHA-256; at most 32 KiB. |
| `GET /observation/overhead-N.png` | Only positive decimal `N` without leading zero. Returns JSON `name,media_type,bytes,sha256,base64`, at most 750,000 raw bytes and less than 1 MiB full JSON. Reads only that retained public camera artifact. |
| `GET /history?after=N&limit=100` | Ordered public events after N; maximum 200; high-water mark and explicit gap/tail status. |
| `GET /command/<id>` | Durable request, phases, admission, terminal feedback, and separately labeled verification. |
| `POST /command` | Envelope below plus `action`; calls the same native actuator/skill boundary used by conventional automation. |
| `POST /observe` | Envelope below; no `action`. Requests a fresh overhead structured capture and bounded PNG artifact. Poll the same command ID until terminal; deadline 3 simulation seconds. |
| `POST /handback` | Envelope below plus `reason`. Validates fresh observations, ownership/task revision, idle resources/device, open unoccupied jaws, no retained conventional pending outcome, and a valid next frozen conventional action. |
| `POST /continuity` | `{content: string}`, <=32 KiB UTF-8. Retains both old and new note contents by hash in protected evidence, fsyncs and atomically replaces runtime `Continuity.md`. Returns bytes and current/previous SHA-256. A separate WSL workspace must synchronize this successful commit through its trusted bridge. |
| `POST /restart-agent` | Explicitly denied as `operator_only`; the robot capability does not grant agent lifecycle authority. |
| `POST /run-program` | Explicitly denied: no dedicated isolated program runner is qualified. |

Every control envelope contains:

```json
{"request_id":"unique-stable-id","authority_epoch":2,"order_version":1,"observation_sequence":14}
```

Authentication records the exact capability epoch at HTTP receipt. The physics-owner thread rechecks that epoch immediately before every queued operation, including continuity writes and reads. Epoch changes rotate the capability before the next queued operation; delayed old-generation requests receive `stale_authentication` and do not execute. An old token is never upgraded to current authority by waiting in the queue.

The `serve` runner enables a protected launcher bridge. Its distinct `operator-endpoint.json` is written inside the **protected evidence directory**, never the robot runtime. Send its capability in `X-Robot-Operator-Capability`. A robot capability cannot authenticate to any `/operator/` route; an operator capability cannot authenticate to robot routes. The WSL broker must never expose operator routes, endpoint contents or this token.

| Protected operator endpoint | Contract |
|---|---|
| `GET /operator/status` | Current public status, invocation and unresolved robot commands, without granting robot control. Wait for conventional activation (`owner=robot`) before start. |
| `GET /operator/command/<id>` | Durable lifecycle receipt; query after an unknown reply. |
| `GET /operator/continuity` | Current note plus hash/bytes for fresh workspace creation. |
| `POST /operator/start-invocation` | `{request_id,invocation_id,authority_epoch,reason?}`. Current epoch, robot owner, no active invocation or outstanding motion required. Each invocation identity is single-use. Increments epoch and returns `command.status=completed` plus a new robot `endpoint` with URL, capability and epoch. A historical start retry returns the historical receipt, never a successor token. |
| `POST /operator/retire-invocation` | Same body fields. Cancels motion and revokes the active invocation before namespace teardown. Pending physical effects remain unknown. Wait for retained cancellation feedback before a new start. After successful handback, retirement only records process retirement and leaves resumed conventional motion/epoch intact. |
| `POST /operator/stop` | `{request_id,authority_epoch,reason?}`. Revokes/cancels and requests orderly host termination with `terminal=operator_stop`. |

Every lifecycle operation uses durable stable request identity and rejects changed-payload reuse. Retry the identical body to obtain its original transition without cancelling twice or incrementing again. Use current status rather than a historical transition for the next new intention. Start/retire preserve action and observation budgets. New invocations receive `unresolved_commands` including cancelled commands whose physical effect was never established. Cancellation receipt is not physical success.

The launcher freezes the returned robot endpoint into one invocation's trusted broker; it must **never reload a newer runtime capability** for that invocation. Retirement first fences requests, then the launcher destroys the complete old namespace before starting new code. No robot endpoint is published while no invocation is active. Handback immediately revokes robot access; commit continuity first. `Supervisor.restart_agent` remains a legacy trusted in-process test seam and is not the serve lifecycle route.

Read the activation's epoch/task revision once per invocation. Fetch status to get a recent observation; reject rather than silently adopting a changed epoch or task. The host accepts only observation sequences it issued within 0.35 simulation seconds. A stale request is a recorded rejection. Reconstruct current state before issuing a new intention; never blindly retry with a new identity. Repeating an identical request ID/payload returns its retained record without dispatch. Changing its payload is rejected. This guarantee is limited to the current supervisor lifetime; a complete host restart requires an operator recovery procedure that is not implemented.

Skills are `transport(part_id,destination,objective?)`, `recover_held(destination)`, `setup(family)`, `cycle(part_id,recipe)`, `inspect(part_id)`, `observe(clear_view?)`, `wait`, and `cancel(target_request_id)`. `done` is merely an assertion; it does not grant completion or handback.

Manual actions are native `cartesian_target(position:[x,y,z],duration_s,gripper?)`, `joint_command(mode:position|velocity|effort,values:[7],duration_s,gripper?)`, and `trajectory(waypoints:[{time_s,positions:[7]}],gripper?)`. Native gripper fields are close `0`, open `255`, or omitted to retain. Convenience `move_relative(delta:[3],frame:"world",duration_s,gripper?)` resolves from current measured TCP and limits each delta to 0.05 m. `gripper(state:"open"|"close",duration_s?)` uses a bounded native hold at current joints; default duration 0.5 s. All native limits/interlocks remain active. Native joint-position and velocity values can be clipped; do not mistake requested values for measured motion.

One activation permits at most 20 physical command requests and 50 explicit observations. Physical command requests are at least 0.1 simulation seconds apart. Fresh agent invocation does not reset these budgets. Periodic sensing is independent and does not consume the explicit observation budget. A macro may continue independently for up to 90 simulation seconds under protected host renewal; native manual commands always retain their <=2-second horizon. Agent absence does not freeze physics. Epoch revocation cancels active motion and retains unknown physical outcomes.

The host journals/fsyncs the request and command registry before dispatch. `requested`, `dispatched`, `admitted`, `executing`, and `terminal` are separate where observable. `completed` from a motion service does not assert successful grasp or placement. Public effect verification requires a later sensor acquisition. Private independent evaluator results stay outside the runtime workspace.

Protections cover actuator bounds, finite values, command horizon, single arm resource, stale task/authority/observation rejection, native machine interlocks, and the implemented tool workspace checks. They do not certify whole-arm, swept-path, carried-object or contact safety. The frozen planner explicitly has no collision-free certificate. Contact metrics are observations, not an automatic protective stop.

No dedicated host `/run-program` service exists. `status.program_execution` distinguishes this from shell execution in an externally qualified namespace: any permitted program can use only its invocation's same bounded gateway. Qualification and resource limits of that executor belong to the registered launcher revision, not this host. Token fencing plus the isolated broker prevents the old namespace from acquiring a successor token; the trusted Windows runtime endpoint directory must never be mounted into that namespace. Full supervisor/computer restart remains outside this bounded invocation-restart contract.
