# Smoke021 completion chronology diagnosis

The chronology rejection is an unsupported timestamp comparison, not evidence of contradictory process completion. This finding does not change Smoke021's failed qualification or establish the separate initial Continuity read requirement. The full identities, hashes, source correspondence and captured timeline are retained in [the diagnostic JSON](smoke-021-chronology-analysis.json).

The official job `20260928T233326435233Z-0d68834d` was freshly authenticated as `succeeded` with exact integer exit 0 before empirical inspection. Its original independent assessment remains failed. The affected command is `exec-387ba72e-57aa-48ce-a73e-5ada4420568d`, process `75238`, executor RPC 63: `/usr/bin/bash -lc 'cat Tasks.md Robot.md Tools.md'`. It does not read Continuity. Its complete executor stdout and app aggregate both contain 20,767 bytes with SHA-256 `980c9c70afa1c5fe948ba478100ef2d6167d6b8ce2e913732cf3782d44470625`.

| Retained event | Capture sequence | Wall time, seconds |
| --- | ---: | ---: |
| Process request | 209 | 1790638440.971517 |
| Pre-send process/closed capture | 220 | 1790638440.984023 |
| Post-await close delivery log | 221 | 1790638440.9850233 |
| Native item/completed | client line 127 | emittedAtMs = 1790638440985 |

The frozen literal reader requires `request < close <= delivered <= emittedAtMs/1000` at `assessment/literal_read_segments.py:190`. It rejects delivery 23.3 microseconds after the truncated point `.985`. The pinned native clock source uses `SystemTime` duration `.as_millis()`, so that native value represents the half-open interval `[1790638440.985, 1790638440.986)`. The delivery time lies inside it. No arbitrary epsilon is needed to explain this rejection. `empty_startup_reads.py:255` repeats the invalid predicate.

There is also a distinct general scheduling issue. In `harness/executor_capture.py:133–139`, the response is durably captured, `websocket.send` is awaited, and only then is the delivery log timestamp sampled. The receiver can emit its event before the sender resumes to write that receipt. Receipt logging is not an acknowledgment from the app. The observed 23.3-microsecond gap does not tell us whether that scheduling race occurred; millisecond truncation alone makes these observed times compatible.

The pinned native startup path does not promise every successful completion follows process closure. `process_manager.rs:1572–1661` permits output collection to stop on a deadline; its short-lived branch at lines 768–815 then emits completion. In `process.rs:574–597`, exit state can precede output closure. This matters because the affected app item identifies `unifiedExecStartup`. The reviewed tag is `rust-v0.157.1`, not an attestation that the installed executable was built from those exact source bytes. No timer-resolution or cross-OS calibration claim is made.

The prospective [READ_EVIDENCE_V3 method](READ_EVIDENCE_V3.md) preserves exact native milliseconds, the original timestamps, complete identities, byte equality, capture sequence and all delivery receipts. Its conservative accepted subset requires request strictly before close capture and close strictly before the native interval's exclusive upper endpoint. That latter condition is a proof restriction, not a universal native lifecycle theorem. A separate `evidence_complete_upper_wall_unix_s` is the maximum of that upper endpoint and all required authenticated local delivery-log times. Strict invocation, episode and mutation checks must use this conservative bound. An early interval cannot be hidden by taking a maximum, and missing delivery, invalid clocks, ambiguous identities and overlapping boundaries still fail closed.

[Six standalone synthetic checks](smoke-021-chronology-development-001/receipt.json) passed. They extract the actual frozen `execution_proof`, `outbound`, and durable `Capture` functions from dev070, demonstrate the quantization rejection and a post-await logging race, and test early events, exclusive interval equality, mutation overlap and invalid inputs. They start no native executable, model, network process or simulation. They do not replay the original assessment. Their [source](smoke-021-chronology-development-001/counterexample.py), [stdout](smoke-021-chronology-development-001/stdout.txt) and [stderr](smoke-021-chronology-development-001/stderr.txt) remain separate development evidence.

The seven relevant local assessor/runtime sources were byte-equal to the dev070 archive when inspected. The original assessment, source archive, captured streams and registered verdict were not edited. The separate [initial-read diagnosis](smoke-021-read-proof-diagnosis.md) addresses the Continuity recipes.
