# A1 repeated setup diagnostic

Development-only, read-only diagnosis of `B01-dev-A1-003`, recorded 2026-09-23 UTC while its pilot batch was running. No Runtime source, running process or experiment setting was changed. This is a bounded early trace, not the final A1 outcome or a comparison with the pending A2/A3 pilots.

The observed loop is a sequence of correctly formatted, admitted **already-satisfied setup requests**. The model had fresh evidence that insert A was installed and alternative admissible stock-loading actions. The shared candidate validator still offered setup A, the gateway correctly reported it already seated, and the following model context omitted that just-resolved action. The trace establishes these interface conditions and repeated choices; it does not establish the model's internal reason for choosing them.

## Exact evidence boundary

Sources are the [registered A1-003 snapshot manifest](../Architecture%20Map/releases/B01-dev-A1-003/manifest.json) and [protected events](../Evidence/raw/B01-dev-A1-003/events.jsonl). The manifest SHA-256 is `4fb88ecdee7749ab57f0d3bec8aa9fb8afa2142e25b9f382f77e0ae1303f4949`. Its source hashes match the current held-stable files inspected:

| Source | SHA-256 |
|---|---|
| [candidates.py](../Runtime/candidates.py) | `36d94a22de889f1e48ec23ff6902755ecfb5730e4cde8e1eb73ed052b01735ec` |
| [cell.py](../Runtime/cell.py) | `cafb32898367bbba3416e89a62dd0b28d92db41796ae0504a75a8a0b26383bc2` |

The inspected event prefix ends at event **179**, byte offset **1,064,251**; SHA-256 of those exact prefix bytes is `877a3221d9e57d198e53a53b84dfc6cb3247420fae2e6f30198dbdd7046da570`. The file was still growing, and `result.json` did not exist at the first read. This prefix hash is deliberately not presented as the final event-file hash. Request events carry their own `payload_sha256`, and each response below links its request through `parent_ids`.

The registered model is Qwen/Qwen3-14B-GGUF, revision `530227a7d994db8eca5ab5ced2fb692b614357fd`, Q4_K_M weight SHA-256 `500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0`. This attempt is nominal, persistent, three parts, world seed 0, combined policy/noise seed 11 and 300-second cap. Earlier 4B pilot outcomes cannot be substituted for this live trace.

## What the model actually received and selected

Event **9** delivered packet sequence 1, incarnation 1, with capture time 0.502 simulation seconds and delivery time 0.584. Detection ages were 0.082 seconds. Request **11**, parent candidate reply 10, included:

- `station.fixture_insert="A"`, `busy=false`, `occupied_visible_id=null`, `fault=false`.
- Fresh auxiliary detection `insert_A`, kind `insert`, family A, zone `fixture`; insert B was at `insert_home_B`.
- Fresh raw parts A1, B2 and A3. The menu included both `transport(A1,fixture)` and `transport(A3,fixture)`, alongside 12 other transports, both setup families, and other legal alternatives.
- `last_error=null`, `failed_attempts={}`, and a fixture belief explicitly based on the observed insert tag.

The second delivered packet, event **46**, sequence 21, was captured at 2.500 and delivered at 2.586 seconds, age 0.086 seconds. Request **48** again included the same relevant fresh facts and alternatives after the first setup had resolved. The later sampled requests also contained station insert A and both setup choices. These were actual model inputs, not merely frames captured by the sensor worker.

| Request → response event | Response wall time (s) | Returned action | Measured call latency (s) | Prompt / output tokens |
|---|---:|---|---:|---:|
| 11 → 31 | 1.908389 | `setup`, family A | 1.809351 | 2,405 / 16 |
| 48 → 68 | 3.890945 | `setup`, family A | 1.793595 | 2,407 / 16 |
| 85 → 105 | 5.899183 | `setup`, family A | 1.818017 | 2,398 / 16 |
| 122 → 142 | 7.896724 | `setup`, family A | 1.807368 | 2,407 / 16 |
| 159 → 179 | 9.894545 | `setup`, family A | 1.809227 | 2,404 / 16 |

All five sampled responses were recorded as nonstale. Their subtotal is 12,101 tokens and 9.037558 seconds of measured call latency; these are prefix values, not episode totals. The measured cached-token counter was zero for these calls.

The first four actions were requested at events **36, 73, 110, 147**, admitted at **37, 74, 111, 148**, and received protected gateway feedback at **39, 76, 113, 150**: `status="completed"`, reason `requested insert already visibly seated`. Candidate replies **47, 84, 121, 158** reported setup resolved because public fixture-insert state matched the request. These are four already-satisfied command completions, not four physical insert exchanges or four units of useful work. The prefix stops at the fifth model response, before its eventual command outcome.

## Source mechanism and limits of the diagnosis

`Candidate._validate` (setup branch near line 487) requires an idle, observably empty fixture but does not reject an already-installed requested family. `_admissible_actions` proposes both setup families and filters them with that validator. A1's generated JSON schema enumerates this same admissible menu. Therefore setup A was explicitly allowed by both the schema and local validator; further required-argument schema tightening would not remove this particular loop.

`Cell.admit` (setup branch near line 465) detects that the requested insert is already visibly seated and completes the command without exchanging it. That is truthful, safe idempotent service behavior. `_reconcile` (near line 365) resolves setup when a new packet shows the requested insert. `_finish_pending` (near line 320) emits a resolution event, clears pending state and removes that action's failure count on success. It retains no bounded history of successful actions. `_context` (near line 713) includes current state, parts, failure counts and errors but not the just-resolved action or its receipt. `_request_model` sends a fresh system message plus current context, with no previous request/response conversation.

Consequently the wrapper presents the next decision with the same legal already-satisfied choice and no explicit recent-success record. This explains why existing failure limits do not stop this *successful-service/no-progress* pattern. It does not prove that missing history caused the model choice: the current observation alone already identifies setup A as unnecessary. Menu ordering, grammar behavior, prompt interpretation and deterministic model preferences are alternative hypotheses, not measured causes. The menu starts with clear-view observe and fixture transports, so these samples are not simply selection of its first listed action.

## Smallest recommended change after the pilot batch

**First change: give `setup` a common state-change precondition for new decisions.** In the shared candidate validation used by all entrants, reject a newly proposed setup when the requested family is already directly and freshly observed installed. Use current station insert state plus the matching fresh auxiliary insert detection; do not use retained `fixture_belief` alone, an occluded tag or private evaluator state to declare the action unnecessary. Emit an explicit local reason such as `requested insert already freshly observed installed`.

This one predicate automatically removes the known no-op from A1's generated menu/schema. It must also apply when A2 actually dispatches a procedure node and when the conventional/A3 wrapper validates an action. Do not reject an entire A2 future procedure merely because a setup step is unnecessary in its initial state: the same step may become useful after an intervening insert change. Validate against the public state at dispatch. Keep idempotent gateway receipts for repeated request IDs and races; a new policy decision and replay of an existing transaction are different cases.

This is a declared common-interface change before freeze. It removes an operation with an already-established postcondition; it does not select a stock part, preferred next step, route or procedure for the model. Preserve other legal alternatives, including observe, wait, help, a real change to insert B and alternative transports. Add a brief shared prompt/API statement that setup means changing the insert and already-satisfied setup is not new work. Do not introduce an automatic stock-load action, baseline fallback, preferred-action rank or hidden truth. The model must still choose useful progress and can still fail or oscillate.

**Separate optional refinement: expose bounded recent consequential resolutions.** If further development needs explicit feedback continuity, retain a small fixed history (for example, the last four resolved commands) with request ID, operation/arguments, order/incarnation, public receipt status/reason, resolution observation sequence/time and the candidate's resolution basis. Distinguish `already_satisfied` from a measured state change; never invent `progress=true` from an acknowledgement. Put the same history field into all LLM contexts. Persist only in the permitted candidate checkpoint; it disappears at a no-persistence restart, while the existing common bounded receipt service remains unchanged. Charge its actual bytes/tokens and freeze its bound. This is a distinct memory-interface change and should not be silently bundled when attributing the no-op predicate's effect.

Further operation/guard schema work is not the first fix for these five samples: their syntax and arguments were valid. Any future A2 guard correction must use its actual retained pilot evidence. The pending pilots may reveal different problems; this report supplies no verdict on them.

## Focused validation for the next revision

Before registering the next development snapshot, test that fresh installed A excludes a new setup A while leaving setup B and multiple stock/transport choices; unknown/stale/occluded insert evidence is not treated as confirmed satisfaction; A2's initially unnecessary future setup becomes eligible after a genuine state change; all entrants use the same rule; repeated transaction receipts remain idempotent; and no implicit action is dispatched when the model selects an invalid choice. If adding history, test its boundedness, exact public provenance and persistence/control behavior separately.

Then register a new immutable development attempt and retain A1-003 unchanged. Measure actual task progress, model choices, tokens, timing and assisted/unassisted behavior; passing a no-op unit test does not establish physical competence. No new run or source edit is authorized or performed by this diagnostic document. The current pilot's final outcome, later loop frequency, physical progress, timing validity and comparative architecture effect remain outside this inspected prefix.
