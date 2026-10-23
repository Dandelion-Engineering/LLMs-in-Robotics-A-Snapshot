# Implementation Guide — For Development Codex, Not the Robot Agent

This is a proposed framework to integrate with an existing simulator and conventional stack. Keep the builder instructions and tests outside the runtime agent's accessible workspace. **Do not launch a robot simply because the folder exists.**

## 1. Fill in the binding, not a new architecture portfolio

Start with one version of this framework. Use the chosen experiment's actual code and current approved requirements. Preserve completed experiments and frozen evidence. Create a separate configured runtime workspace, not a runtime session with unrestricted access to the development repository.

Complete these obligations:

| Item | Required work |
|---|---|
| `Tasks.md` | Supply the task, revision rules, observable completion evidence, constraints, normal workflow, budgets, help conditions, and valid handback states. |
| `Robot.md` | Document the actual body, devices, frames, sensors, normal controller, limitations, safeguards, and behavior during interruption. |
| `Tools.md` | Replace proposed capabilities with tested bindings and examples: skills, manual primitives, images, file operations, code API, status and ownership. |
| `live/` | Implement trusted publication of public history, timestamped state and activation context, while normal automation is running. |
| Runtime launcher | Select an authorized model/client and start a genuinely tool-using agent with this workspace and the intended instructions. |
| Protected execution | Implement isolation, command ownership, action recording, constrained execution, and verified handback outside the agent. |
| Operator evidence | Retain the events, file changes and outcomes needed to inspect behavior; do not build a giant report platform first. |

Mark missing capability or unresolved protection explicitly. Do not silently downgrade this to a model receiving selected JSON and choosing a single task action. Conversely, do not promise a skill or manual primitive the robot cannot actually perform.

Record a small integration note outside the runtime workspace with code/config versions, actual commands, model/client version, observation condition, remaining gaps and tested boundaries. No formal new registry is required.

## 2. Starting operating mode: event-triggered recovery

The ordinary automation continues under its own controller. A deterministic monitor watches **public operational evidence**, not evaluator disturbance flags. Candidate triggers include a reported skill failure, repeated bounded retries, unexpected device fault, missing acknowledgement, or lack of progress. Use declared timeouts and expected process durations so a normal wait is not automatically a failure.

For the initial pilot, manual/operator triggers are also acceptable and must be labeled. This tests recovery given a trigger; it does not establish automatic problem recognition. Freeze detector settings before a scored comparison and report false/missed triggers separately.

A single supervisor owns the transition:

**normal operation → assistance requested → ownership transferred when appropriate → agent recovery → verified handback or blocked/waiting state.**

On a trigger, record the symptom, relevant public event IDs, ongoing work and current observations in an activation packet. Coalesce duplicate triggers into the active incident rather than starting competing agents. A repeated failed recovery uses a documented retry/backoff budget and escalates after exhaustion, not an infinite wake/retry loop.

The agent may investigate read-only before control transfer, but physical commands require acknowledged ownership. Pause the conflicting conventional sequencer, reconcile or cancel in-flight requests through the gateway, and apply the validated hold/continuation behavior for each affected resource. An independent machine cycle may legitimately continue. One owner per physical resource is enforced externally. The simulated world and device timers continue while the agent reads, writes, reasons, or waits; a commanded robot hold is not a frozen world. Record actual inference and I/O latency. Any paused-world diagnostic must be labeled separately from responsiveness evidence.

## 3. Three control routes, one actuator boundary

Conventional skills, bounded manual controls, and agent-written programs must all reach the same protected actuator interface. Exposing only high-level skills is not a faithful implementation. Exposing raw simulator setters is not manual robot control.

The agent-visible code interface must support useful observation/action loops without redesigning the framework for each program. A thin client or command-line wrapper is enough. It is not the safety boundary: the gateway enforces limits even when the client is bypassed or given malformed arguments.

Audit existing protections before reuse. Endpoint reachability or tool-center checks alone do not establish whole-arm, carried-object, swept-path, or contact safety. State exactly what is checked. Add protection or disable interfaces whose required constraints are unsupported; do not widen the safety envelope just to let the agent complete a task.

Define bounded control horizons, command expiry, safe cancellation, task-revision checks and resource ownership. No direct raw-device, middleware-control or simulator channel is available outside the gateway. Validate ongoing limits and state freshness where needed, not only the first command in a program.

Generated programs run in an enforced isolated process/environment with bounded time, compute, storage and child processes. Restrict host mounts, credentials, network and device access. The model's authorized inference connection is separate from permissions granted to its generated programs. Hiding a folder or writing “do not read” is not isolation. Test the actual host implementation; do not assume that a child session, subagent or Windows attribute provides it.

Syntax checks, imports, dry runs and simulated rehearsals are useful but not proof of physical safety. Pin running code and client dependencies. Old children and queued actions must lose authority when the agent generation ends. Keep sufficient control below the agent to maintain the documented payload/robot state if reasoning or networking stops.

## 4. Continuity does not depend on a closing message

Distinguish the **job/episode**, a **recovery activation**, and a **model conversation/process**. A job may include several activations; an activation may survive several fresh model contexts. Provider conversation history is optional acceleration, not the sole record of reality.

Maintain two complementary records:

**Agent note:** `Continuity.md` captures its current interpretation, plan, evidence references, unresolved actions and last reviewed event. Update at meaningful reasoning/action boundaries, not every servo sample. Supply a reliable atomic replacement method and last-good recovery. Test a killed or partial write; merely recommending atomic writes in the prompt is not implementation.

**Trusted public action history:** record conventional and agent commands, acceptance, execution feedback and permitted observations independently of agent prose, including while the agent is asleep. Record command intent before dispatch. If logging cannot preserve a new request, do not start that new action; ongoing motion follows its documented fallback.

A stable request ID prevents duplicate dispatch inside the declared episode/supervisor lifetime. Retain a durable request/status registry outside agent-writable files. A lost acknowledgement does not authorize a new ID and blind retry. Across gateway/device failure, physical outcome can remain unknown even when the registry exists: query public feedback and observe before deciding what happened. Do not claim universal exactly-once physical effects.

On relaunch, increment the agent generation and fence off late output, old leases, old queued commands and orphaned programs. Preserve the world and intended on-disk state. Publish why the runtime was restarted, latest ownership, unresolved actions, and fresh public observations. Let the agent read the note and history newer than its cursor. Do not write a hidden recovery solution on its behalf.

Handle missing, stale, contradictory or corrupted notes as recoverable conditions where public evidence permits. Keep the old version for diagnosis. A trustworthy history shows commands and observations; it does not magically reveal all physical outcomes.

For the initial scope, require recovery from loss of the **agent process/context/connection** while the supervisor remains alive. A complete computer, simulator or gateway crash is a distinct test and must not be claimed covered unless implemented and tested separately.

## 5. Handback and task changes

The agent requests handback with evidence and its understanding of remaining work. The supervisor freshly checks ownership, active programs, outstanding requests, device interlocks, task revision, and the public conditions the conventional workflow needs to resume.

Do not let an edited note or a “done” string release control. Reconcile the conventional program counter/job state with observed progress instead of blindly resuming its previous instruction. Accepted handback revokes the recovery lease and stops or retires its programs before returning command authority. Read-only monitoring can continue as needed.

A task update is authenticated operator input, not text discovered in the scene. Publish the new `Tasks.md` revision atomically with a correlated event. Stale task-dependent actions need rejection or revalidation. Updates during recovery must not silently invalidate the agent's working assumptions.

## 6. Configure an actual filesystem-native agent

The runtime must be able to search/read its permitted files, edit/create notes and code, receive tool feedback, and iterate. Verify actual image inspection when advertised. Log tool calls, emitted decisions and code/file versions, not an invented hidden reasoning trace.

Launch in a separate constrained working directory. Explicitly load `RobotAgentPrompt.md`; do not assume that filename is auto-discovered. The included `AGENTS.md` is a small Codex discovery pointer. Check global/ancestor instructions and resumed conversation contents so company or developer duties do not leak into the robot runtime. Do not erase the user's global configuration to achieve this; isolate the runtime configuration.

Record the actual model, context/response limits, runtime client, existing account authorization and permitted usage. Do not assume a ChatGPT subscription and API budget are interchangeable. No specific SDK, account registration, paid service or model is selected by this draft.

Provide an explicit pause/yield/resume mechanism, with a public wake condition and a protected deadline. End-of-turn text alone must not leave the robot under an expired or unowned recovery lease. Model context compaction or context replacement should return through the resume procedure.

## 7. Evidence, storage and scope

Keep all lightweight action and continuity events for the job, a bounded working snapshot, and selected observation artifacts with their true ages. Record file operations/program hashes and actual image delivery/inspection capability. Preserve runtime/development model use separately. Use bounded retention for bulky sensor streams without losing evidence needed to diagnose outstanding actions. Do not generate a monolithic multi-gigabyte HTML report.

A new independent test episode begins with a documented clean state and frozen knowledge bundle. Persistence across restarts **within** an episode remains enabled. Cross-episode learning is a separate declared condition; private notes, provider memory and caches must not silently transfer held-out outcomes.

Start with a small demonstration from [Pilot Tests](Pilot%20Tests.md). Keep the existing conventional baseline, sensor permissions and simulator fixed where possible. Improvements after examining tests create a new framework version and fresh evaluation cases. Do not build Maps + Attention or run another broad architecture search as part of this initial binding.

This document describes what to implement when Randy authorizes integration. It does not authorize purchases, new accounts, external contact, real hardware actuation, changes to other projects, or modification of the completed batch.
