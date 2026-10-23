# Smoke008: incomplete public Tools.md output

The original smoke008/dev037 qualification remains **failed: 61/62 checks**. The sole failed check is `both_models_read_fixed_startup_and_initial_continuity_bytes`; only interrupt `Tools.md` is unverified. The original admission error is `Actual-model interruption/resume smoke qualification missing/failed`. Owner timing passed (maximum lag 7.734299 ms, 0/660 bad windows), and both codehost lifecycle checks passed. Those checks do not establish complete public command-output projection.

Official job `20260928T054358854785Z-239662b1` was freshly authenticated as `succeeded` with integer exit status `0` before evidence consumption; it ran 2026-09-28 05:43:59.160517–05:55:02.859482 UTC. This is a read-only diagnosis, not a new assessment or a task score.

## Exact byte comparison

Interrupt tool `exec-2cded1a1-4ec7-4174-a89c-81aceadb5674` ran `/usr/bin/bash -lc 'cat /workspace/Tools.md'` in `/workspace` (executor cwd `file:///workspace`, RPC 65, PID `23102`). Native and public exit codes are zero, and native `sandboxDenied` is false.

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| Initial/runtime Tools.md and full native stdout | 13029 | `68f879b2d94fd34b536968ed3a8bb4b78e64ec73871b473914c5200ca7566b47` |
| First native chunk, absent from public output | 8192 | `2b778060396ebe8dcb20aaea57ea84a1ae030992d80640b11d01036f2a42b62f` |
| Second native chunk = public delta = public aggregate | 4837 | `2ab73a92fe9d4586154e2b8eeae2e41f40a90b5907fd41af3be36135c30dcea3` |

The retained runtime bytes match the initial hash. The frozen readiness-session-10 Tools template is 13,128 bytes with CRLF; newline normalization yields exactly those 13,029 runtime bytes. Both captured chunks independently decode as UTF-8 and contain no NUL. The sole public Tools command is at client lines 105–107. The complete missing prefix occurs in none of the 33 retained public completed command outputs. No later Tools read supplies complete output.

## Capture and public event chronology

Capture sequence numbers equal physical JSONL line numbers. The complete 605-record hash chain and retained-message hashes were independently checked. Each listed native response has a unique subsequent send-completion receipt; output original/retained blob hashes and lengths match.

| Capture line | Native message | Native seq | Wall Unix seconds | Send completion line |
|---:|---|---:|---:|---:|
| 219 | process/start, RPC 65 | — | 1790574271.1676977 | — |
| 222 | process/start response, PID 23102 | — | 1790574271.175231 | 223 |
| 224 | process/exited, exit 0 | 1 | 1790574271.1777442 | 225 |
| 226 | stdout first 8192 bytes | 2 | 1790574271.1802542 | 227 |
| 228 | stdout final 4837 bytes | 3 | 1790574271.1817598 | 229 |
| 230 | process/closed | 4 | 1790574271.1827638 | 231 |

Public client line 105 starts the item at `1790574271181` ms; line 106 contains the sole 4,837-byte output delta, and line 107 completes the item at `1790574271187` ms with the same 4,837-byte aggregate. The first capture send completion precedes the app start timestamp by about 0.746 ms; these differently resolved timestamps do not establish causation. A later terminate request appears at capture line 248.

## Why the original check fails

The original literal-read proof already identifies and consumes all 13,029 source bytes. Its `app_projection_equals_executor` is false, so the unchanged startup gate refuses promotion. This is an actual retained output mismatch, not a finite-command grammar gap. The older startup recognizer likewise requires the complete initial bytes in a public aggregate. Every other startup/Continuity bucket in both invocations passes.

Frozen `executor_capture.py:134–139` captures an original response, awaits WebSocket send, then records `delivered`. This establishes send completion, not an app receive acknowledgement or model-visible full output. Frozen `bootstrap_client_v2.py:131–138,169–177` durably logs app-server notifications. Frozen `literal_read_segments.py:252–270` requires equal app/executor bytes for startup promotion; `assess_bootstrap.py:61–87` also requires complete startup bytes. Exact archive member hashes are bound in the JSON.

## What remains unknown

The evidence does not identify which upstream or consumer stage omitted the first chunk. The public command item and process/start RPC have no output-limit field; no truncation marker appears. However, raw model `tools.exec_command` arguments, code-mode request limits, native consumer aggregation logic and relevant defaults are not retained here. An explicit/default output cap or aggregation behavior cannot be excluded. Do not call this a proven native aggregation defect or infer model attention from a send receipt.

Keep the failed historical verdict and the complete public startup-read requirement. Prospective producer/consumer delivery diagnostics are supported; parser relaxation and a specific repair are not justified by these records alone. No runtime, assessor, frozen source, model instructions or thresholds were changed for this diagnosis.

## Bound evidence

[Machine-readable diagnosis, exact source hashes and input bindings](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair/smoke-008-output-delivery-analysis.json>)

- [Authenticated retained official queue receipt](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/qualification/smoke-008-queue.json>)
- [Frozen two-invocation manifest](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/qualification/smoke-008-manifest.json>)
- [Original failed independent assessment](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/qualification/smoke-008-assessment.json>)
- [Original failed final admission](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/qualification/final-qualification-010/smoke-008/disposition.json>)
- [Frozen dev037 source snapshot](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-037/snapshot.json>)
- [Frozen dev037 source archive](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-037/code.zip>)
- [Original registered invalid result](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-037/result-RCI001-C02-smoke-008/result-record.json>)
- [Public app-server events](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/client/events.jsonl>)
- [Protected executor capture](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/executor-2-capture.jsonl>)
- [Protected executor requests](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/executor-2-requests.jsonl>)
- [Initial runtime input hashes](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/runtime-input-hashes.json>)
- [Retained runtime file bytes before close](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/runtime-before-close.json>)
- [Retained runtime file bytes after close](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/runtime-after-close.json>)
- [Client launch metadata](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/client/launch.json>)
- [Original interrupt client result](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/interrupt/client/result.json>)
- [Original two-invocation sequence result](<C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/local-evidence/campaign002/qualification/RCI001-C02-smoke-008/orchestrator/sequence-result.json>)
