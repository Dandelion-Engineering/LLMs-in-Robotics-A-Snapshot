# Native008 conventional admission race

Native008/dev033 remains a failed apparatus qualification: five of six native reference cases passed, but home-1 reached the 240-second simulation cap with B2 processed and uninspected. The original assessment passed 65 of 66 checks; only home-1 `independent_success` failed. All six strict owner timing and resource checks passed. No model ran and no scored recovery result is claimed.

The official native008 job `20260928T050615339435Z-e73b2225` and comparator native007 job `20260928T042546825249Z-ade91f92` were freshly authenticated as succeeded with integer exit status 0 before outcome access. [Original failed assessment](../qualification/native-008-assessment.json); [failed final admission](../qualification/final-qualification-009/native-008/disposition.json); [exact hash-bound evidence and source inventory](native-008-admission-analysis.json).

## What happened

The protected home-1 journal records this order. Event IDs also equal physical JSONL line numbers. Native completion time, sensor capture time and supervisor journal time are distinct and must not be substituted for one another.

| Event | Journal simulation time (s) | Retained fact |
|---|---:|---|
| 560 | 54.408 | Reference handback completed; conventional control, epoch 3. |
| 786 | 75.978 | B2 transport to inspection requested as `825118e0-9924-4118-a05a-0eef94e83828`. |
| 897 | 86.938 | Observation 851: capture 86.882, packet time 86.920; B2 visibly at inspection, jaws open, no visible held part. |
| 898 | 86.954 | Inspect B2 requested as `270cac0d-4f3c-4ff2-bfd1-6a3323da3a7d`. |
| 899 | 86.958 | Inspect rejected: `resource_busy`, “Another command is outstanding.” No native admission or native action is retained for it. |
| 900 | 86.964 | Supervisor records the prior transport terminal receipt; its native completion time is 86.932. |
| 901–902 | 87.042–87.044 | Observation 852 and the prior transport's public-effect verification are recorded. |
| 1345–1346 | 132.090 | Controller requests help for the unresolved inspection and control changes to robot. |
| 2436 | 241.000 | Episode stops at 240 elapsed simulation seconds. |

The controller checkpoint independently retains a successful **visible-effect** resolution for the transport at packet sequence 851, while its public feedback was still only `accepted`. It then stores the inspection as pending, with `feedback: null`. At the end that same inspection remains pending with `unresolved_timeout: true` and `halted: true`. The independent evaluator records accepted count 0, no first success, B2 processed but uninspected, and one unmet requirement. These are actual failure facts, not missing report recognition.

[Native008 protected journal](../../local-evidence/campaign002/qualification/RCI001-C02-native-008/RCI001-C02-native-008-home-1/host/public-history.jsonl); [command registry](../../local-evidence/campaign002/qualification/RCI001-C02-native-008/RCI001-C02-native-008-home-1/host/command-registry.json); [final controller checkpoint](../../local-evidence/campaign002/qualification/RCI001-C02-native-008/RCI001-C02-native-008-home-1/host/baseline-workspace/candidate-state.json); [original result](../../local-evidence/campaign002/qualification/RCI001-C02-native-008/RCI001-C02-native-008-home-1/host/result.json).

## Source-supported explanation

Both frozen archives contain identical bytes for the seven listed supervisor, adapter, worker, host, controller, cell and evaluator files. The JSON records each archive/member SHA-256 and the exact source line ranges. Consult the frozen entries rather than a prospectively edited checkout.

- `continuous_adapter.py:72–80,231–232` makes physical busy state a worker snapshot. `physics_worker.py:151–164` drains a finite queue batch. `continuous_adapter.py:268–310` durably processes captures and native feedback, and `run_host.py:426–438` calls the conventional decision afterward. The owner continues advancing independently.
- Original `host/supervisor.py:406–411` checks physical busy state but omits `active_command`. Its `command` method at 310–334 correctly rejects new work while a supervisor command remains outstanding. The rejection path at 249–254 persists a terminal rejection without calling the controller's `accept_feedback`; normal admission and native terminal paths do deliver feedback.
- `Runtime 004/candidates.py:1037–1048` persists pending inspection. Lines 369–380 would reconcile a supplied rejection, but none is supplied here. Lines 442–461 only correlate feedback to the current request, so the prior transport's later receipt cannot fill the inspection record. Lines 429–434 and 1098–1102 preserve the unknown outcome and request help after the deadline.

The protected event order and source gates support an admission race between newer physical-idle state and an outstanding supervisor command. Exact thread interleaving and drain-batch membership were not logged. This diagnosis does not identify OS scheduling, device latency, fsync or sensor noise as the unique cause.

[Dev033 source snapshot](../../../Architecture%20Map/releases/RCI001-C02-dev-033/snapshot.json); [dev033 archived source bytes](../../../Architecture%20Map/releases/RCI001-C02-dev-033/code.zip).

## Retained comparator

Native007 home-1 used the same seed 173, noise seed 24002, reference mode, 240-second simulation cap and 420-second wall cap. Its prior transport completed natively at 87.242 and was processed by the supervisor at 87.256. The controller resolved its visible effect at packet sequence 855/time 87.328, after completion had been processed. Inspection was requested at 87.368, admitted, and completed at 89.404; delivery then produced independent task success. The differing ordering illustrates the race window. This is an existing comparator, not a controlled causal rerun or a substitute passing qualification.

[Native007 protected journal](../../local-evidence/campaign002/qualification/RCI001-C02-native-007/RCI001-C02-native-007-home-1/host/public-history.jsonl); [native007 checkpoint](../../local-evidence/campaign002/qualification/RCI001-C02-native-007/RCI001-C02-native-007-home-1/host/baseline-workspace/candidate-state.json); [native007 result](../../local-evidence/campaign002/qualification/RCI001-C02-native-007/RCI001-C02-native-007-home-1/host/result.json); [dev029 snapshot](../../../Architecture%20Map/releases/RCI001-C02-dev-029/snapshot.json); [dev029 archived sources](../../../Architecture%20Map/releases/RCI001-C02-dev-029/code.zip).

## Prospective correction and limits

The coordinator has declared `CONVENTIONAL_ADMISSION_ORDER_V1.md`: defer conventional decisions at the Campaign002 host boundary while a supervisor command remains active, and continue draining genuine terminal feedback. Preserve the original controller, supervisor, evaluator, action semantics, timing thresholds, deadlines and model instructions. Do not synthesize feedback, replay the rejected inspection or clear an outstanding command without its receipt.

Deterministic ordering tests, a new source freeze, fresh host/transport diagnostics and all five fresh final qualifiers are required before campaign admission. The original native008 assessment and admission remain failed. V9 stopped at this native stage; subsequent boundary, smoke and pilots were not launched. This analysis changes no source or outcome and makes no implementation-success claim.
