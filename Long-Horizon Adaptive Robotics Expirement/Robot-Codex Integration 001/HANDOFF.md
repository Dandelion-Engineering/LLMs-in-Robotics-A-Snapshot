# Robot-Codex Integration 001: development handoff

September 26, 2026, Development Codex session 8. The installed ChatGPT login and Astra Max catalog entry were found, but **actual Robot-Codex operation remains blocked at native isolation qualification**. No model turn, robot-model pilot, or scored campaign ran. This is the strongest tested development setup reached under Randy's permitted stop boundary, not a ready experimental release.

## 1. Challenge validation

Two new development families preserve the r4 Panda/MuJoCo cell, conventional controller, evaluator and low-level adapter. Source hashes match the frozen Batch 01 index. Ordinary off-pad stock was rejected as a candidate because the existing detector already classifies it as raw.

| Family | Missing conventional rule | Protected physical reference |
|---|---|---|
| Misplaced stock | Healthy unprocessed A1 in quarantine is excluded from normal raw-stock eligibility; there is no failed inspection | Existing transport moves A1 to parking1, then handback |
| Blocked insert home | A1 blocks insert A's return pad while the current B order needs a fixture exchange; the baseline cannot relocate the blocker | Existing transport clears A1 to parking1, existing setup installs B, then handback |

Initial poses are declared before the episode. Recovery changes no object state directly. Reference plans and evaluator outputs stay in operator-only code/evidence; public runtime files expose ordinary detections, current order and a symptom-based activation. No future disturbance or solution is included in the bootstrap.

The four exact manifests, code bundles and outcomes are append-only Architecture Map records under `RCI001`, revisions `RCI001-native-001` and `RCI001-native-002`. [Native evidence](records/native-development-evidence.json) contains the compact results, command phases/public verification, source hashes, and raw trace hashes. Each result was consumed only after its official shared queue record reported `succeeded` and exit status 0. See the four `*-queue.json` and `*-result.json` records. These are one placement/seed per family, not estimates of general success.

| Check | Terminal | Handbacks | Simulated episode seconds |
|---|---|---:|---:|
| Stock baseline | Requested assistance; task incomplete | 0 | 0.802 |
| Stock reference | Task success, accepted A1 in tray1 | 1 | 59.306 |
| Insert-home baseline | Requested assistance; task incomplete | 0 | 0.602 |
| Insert-home reference | Task success, accepted B2 in tray2 | 1 | 99.756 |

Both reference recoveries completed with later public observation support, and the unchanged conventional controller resumed useful work. Protected evaluation then established process/inspection/delivery/settling success for each test. Reference wall durations were 60.282 and 100.859 seconds; maximum measured wall-minus-simulation lags were 0.040 and 0.044 seconds. Four protected evidence directories total 25,926,840 bytes; this is not a campaign storage projection.

## 2. Runtime filesystem

The selected Downloads ZIP was `Robot_Agent_Filesystem_v0.1_RobotAgentPrompt.zip` (SHA-256 `341533914c936d25f1f35335e2f210fcce2607104fdd9917351448e56a61469d`). All 16 extracted files are byte-identical to the ZIP at the project root in `Robot Agent Filesystem v0.1/`; the older archive containing `AgentPrompt.md` was not selected. [Provenance](records/template-provenance.json) binds the generic template and frozen sources.

`runtime-template/` contains the experiment-specific Tasks, Robot, Tools, Continuity, live, notes and programs bindings, plus the stdlib CLI. Its `RobotAgentPrompt.md` remains byte-identical to the generic original. It is inactive staging material. Host, evaluator, source repository and reference scripts do not belong in the operational workspace. `smoke-template/` is separately non-actuating and tests instruction-file reads without prescribing recovery.

## 3. Launch path and authentication

The existing PATH CLI is 0.147.0 and did not advertise Astra. The already-installed desktop daemon CLI 0.157.1 does. `codex login status` reported ChatGPT subscription authentication. No credential file was opened, parsed, copied or printed; no API key, new login or billing route was used.

The [launcher](launch/README.md) pins that installed binary, verifies its hash, roots each fresh invocation in an external workspace, and submits exactly **`Follow the instructions in RobotAgentPrompt.md.`** It requests no user config/rules, strict config, no memory/plugins/apps/hooks/subagents and a filtered environment. Process creation is suspended until assigned to a kill-on-close Windows job; timeout/output overflow retires descendants. A successful same-workspace/binary/policy sentinel is required before model execution. No actual loaded tool/context inventory was captured.

## 4. Model configuration

Requested model is `gpt-6-astra`; requested reasoning is `max`, not `ultra`. Both were present in refreshed installed-client metadata. There is **no actual invocation header**, so effective model/reasoning and usable subscription inference remain unverified. The launcher requires the startup header independently of model prose. Development helper agents are separate from Robot-Codex; no Robot-Codex subagents ran.

## 5. Tool and control surface

The conventional controller normally owns the arm. A deterministic public monitor activates recovery on the frozen controller's help request or explicit public station-fault waiting; ordinary process/inspection waits do not themselves activate it. The host imports the frozen cell/skills and exposes loopback JSON through a capability bound to current authority. `robot.py` supplies status, bounded history, stable-ID query, image/structured observation, native skills, relative/world Cartesian movement, gripper, joint commands, trajectories, continuity and checked handback. See [API](host/API.md) and [robot-facing Tools](runtime-template/Tools.md).

History distinguishes requested, dispatched, admitted/executing, terminal and public post-action support. Independent evaluator output never becomes a robot observation. A received or completed command alone does not prove intended physical effect. Unknown mutating responses do not trigger automatic retries. Stale authority/task/observation, resource conflicts, finite-value/actuator bounds, manual horizon and native equipment interlocks are enforced by the host rather than trusted to the model.

No whole-arm, carried-object, swept-path or contact-force safety certificate exists. Observed contact metrics do not create a protective stop. Manual controls are implemented and unit-checked; no actual Robot-Codex manual-action smoke ran. Physics advances independently of client latency; native checks retain measured timing lag and do not establish production timing.

## 6. Continuity and restart

The protected journal and command registry are written before dispatch and mirrored into public runtime history. Atomic continuity commits retain the previous note outside the writable view. Stable IDs prevent duplicate physical dispatch within the host lifetime. Authority changes fence queued requests; the complete old launcher job must be killed before a new generation can read a rotated endpoint. Epochs alone cannot stop a still-running process that can read new workspace files.

A fixed task order is supported with revision fencing; an authenticated live task-update service is not implemented. Complete supervisor/computer restart recovery is not implemented. Synthetic tests cover restart/cancellation/identity/continuity behavior; an actual kill-and-fresh-model reconstruction remains unrun.

Trusted restart is an in-process operator method with a durable, queryable receipt. The robot-facing HTTP service rejects `/restart-agent` with `403 operator_only`; it cannot verify that an old launcher job has been killed. A protected lifecycle bridge joining the launcher to this host remains to be implemented and tested.

## 7. Isolation findings

All three native sentinel attempts failed qualification before any model turn. Root-deny was refused because the elevated sandbox requires effective root read. Users-deny failed applying deny-read ACLs. The narrower bootstrap-only diagnostic produced no output/checks before 30.031 seconds; its cause is unknown. Exit code 0 after timeout cleanup does not count as success. The diagnostic also leaves unrelated system/user paths potentially readable and is insufficient for robot/scored use. Preserve all failures; do not infer technical impossibility from them.

The read-only readiness response `ready` does not validate these policies. No filesystem-denial, inherited-handle, network or read-only-surface canary passed. Loopback-enabled model qualification is also unimplemented. Consequently evaluator/reference/credential isolation has not been demonstrated and no robot-connected model was launched. Raw probe evidence remains in Local AppData under `RobotCodex/Integration001/launch-evidence`; packaged-app aliases may resolve into its LocalCache, as recorded in each probe.

## 8. Validation boundary

| Requested stage | Evidence/status |
|---|---|
| A: subscription/filesystem bootstrap | Authentication/catalog preflight passed; all native policy probes failed; actual bootstrap/model read smoke blocked |
| B: tools and physical action | CLI fake-HTTP tests and protected native reference fixtures; no Robot-Codex tool/action invocation |
| C: fresh-context continuity | Synthetic journal/restart checks only; actual model kill/relaunch unrun |
| D: ownership handoff | Synthetic rejection/fencing checks plus native reference handback fixtures; no model-driven handoff |
| E: generated program | Deferred: no dedicated version-pinned program runner or per-program resource qualification; shell remains programmable |
| Optional one end-to-end Robot-Codex pilot | Not used; zero model turns |

The final source and test record is separate from the immutable physical-attempt snapshots. Final host corrections to queued-request fencing and restart receipts are unit-tested changes after the physical checks; they are not retroactively attributed to those runs. Sustainable native recording retains full-precision 100 Hz joint/TCP/effort samples, public event history and sparse imagery under declared caps. Raw traces stay local and Git-ignored; compact outcomes/hashes/queue receipts are checked in.

Final suites passed: 27 host tests (including actual local HTTP requests, queued generation changes and restart receipts), 21 fake-service client tests, and nine launcher lifecycle/policy/header tests. None of these instantiates a physical Cell or calls a model. [Final source binding](records/final-source-binding.json) records hashes and test scope; the complete unrun setup is Architecture Map revision `RCI001-setup-003`, separate from the two physically exercised host snapshots.

## 9. Next decision

Review this setup and its limitations before scored work. The next engineering step is to resolve and demonstrate native filesystem/network isolation with nonmodel canaries, capture actual tool/context inventory, then run A through D with the exact bootstrap and verified Astra Max. Only after those gates pass can the unused single recovery pilot be considered. Program execution needs its own qualified runner before E. Large campaigns remain closed by the prior storage/capacity and timing gates as well. No automatic retries, parameter sweep, new architecture campaign or historical evidence migration is part of this handoff.
