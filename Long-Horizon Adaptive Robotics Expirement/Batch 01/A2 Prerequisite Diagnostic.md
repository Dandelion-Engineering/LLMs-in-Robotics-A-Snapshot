# A2 missing prerequisites diagnostic

Development-only analysis dated 2026-09-23 UTC. This is separate from the [A1 no-op setup diagnostic](A1%20Loop%20Diagnostic.md): A1 repeatedly selected an already-satisfied setup, whereas these A2 samples guarded later actions on prerequisites that its procedure did not establish. The five-pilot queue batch was still active during inspection. Raw terminal evidence was available, but this note does not replace official queue verification or declare a scored outcome.

The [A2-001 manifest](../Architecture%20Map/releases/B01-dev-A2-001/manifest.json) has SHA-256 `d00f61cd834353d870542efb239639fb5404a7b85d41a06c7eca91f6cdc379b7`. The inspected candidate source matches its registered SHA-256 `36d94a22de889f1e48ec23ff6902755ecfb5730e4cde8e1eb73ed052b01735ec`. The [event file](../Evidence/raw/B01-dev-A2-001/events.jsonl) inspected through event 5023 was 31,945,116 bytes, SHA-256 `75be383031b71b59b5998fbd9147d3a26ae318a1ae611420a201228cb45cf8a0`.

Three exact request/response pairs illustrate the distinction:

| Request → response | Delivered current facts | Procedure omission or inconsistency |
|---|---|---|
| 4216 → 4389 | Request simulation time 259.780; current insert A; fixture empty and idle; raw B2 visible with age 0.062 s; setup B in the available menu; last error `procedure node 0: fixture unavailable or insert incompatible` | First node transports B2 to fixture with `insert_is(B)` guard, but the eight-node procedure contains no setup B. It does contain an inspect action. |
| 4416 → 4517 | Request simulation time 275.824; same relevant state; detection age 0.106 s; same admission error | Four-node procedure loads B2, cycles, unloads to inspection and delivers with `inspection_is(pass)`. It omits both setup B and the inspect action needed to produce a fresh passing inspection. |
| 5015 → 5019 | Request simulation time 300.320; same relevant state; detection age 0.108 s | Adds setup B but guards that setup on `insert_is(B)`, its own absent postcondition. It also omits inspect before guarded passing delivery. Response 5019 is explicitly `late_model_response`, after episode end at wall 316.196288 s; it is evidence of the generated proposal, not an executed late correction. |

Responses 4389 and 4517 are nonstale responses before episode end. Their parent IDs link exactly to requests 4216 and 4416. Request payload SHA-256 values are respectively `d301ac3f53ff5478deb6f5fc1db71bec49be32d498c17b4c7191c4fa3e293b94`, `dd48e89089ec0600062216d517a26b894653ebf575ea4cfe7a5d780adb051b12`, and `24afa7876f57e1e6f76a07da8a8a368b1d2c026f2fa6fe47f69773634ec8fa14` for the late pair.

The existing interpreter accepts bounded procedure syntax, tests guards against current public state, and revalidates each selected action at dispatch. A guard tests a condition; it does not cause that condition. The trace does not demonstrate a need to execute guarded actions anyway, fabricate inspection success, or automatically repair the procedure with conventional scheduling. It also does not identify an internal reasoning mechanism or establish that a prompt clarification will solve the problem.

The prepared [unapplied patch](Calibration%20Tools/a1-loop-fix.patch) adds common task/API knowledge: the chosen next family's different insert requires setup in an empty idle fixture; moving onto the inspection pad does not perform inspection. A2's instruction separately states that future procedure nodes must include actions establishing missing prerequisites, that `insert_is(B)` does not perform setup B, and that setup B must not be guarded on its own desired insert-B outcome. Similarly, `inspection_is(pass)` does not perform inspect.

These statements clarify existing operations for all entrants. They do not specify a preferred stock part, order, route, complete optimal program or fallback action. No Runtime edit has been applied. Register and measure any later revised pilot separately, preserving A2-001's actual source, proposals, late output and costs.
