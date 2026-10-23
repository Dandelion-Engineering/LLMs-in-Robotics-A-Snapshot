# Smoke005 failed-queue infrastructure diagnosis

Official job `20260928T034705357469Z-89ec0765` **failed with integer exit status 1**, from 2026-09-28T03:47:05.626640Z to 03:51:06.425939Z. Direct status was authenticated before this inspection and matched the [retained receipt](../qualification/smoke-005-queue.json). These files were read only to diagnose infrastructure failure. No empirical assessor ran; no qualification, task, recovery or timing result is inferred. The original outputs and qualification history remain unchanged.

The immediate failure is `Interruption stage failed its gate; restart not attempted`. The [raw sequence diagnostic](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/sequence-result.json) contains one interrupt stage with `injected_interruption: false`, no watchdog errors, and host exit code 0. The [raw stage diagnostic](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/stage-result.json) reports cleanup, retirement and retention complete, but those fields do not qualify a failed queue run. Resume and pilots004 were not launched.

## What reached the protected boundary

The [gateway diagnostic trace](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/broker-events.jsonl) has twelve entries: status/history traffic, one observation request and its query. It has no POST to `/command`, `/continuity` or `/handback`. Frozen `campaign-002/harness/physical.py:60–64` injects interruption only after the designated `smoke-open-001` command reaches the supervisor; lines 145–146 reject the next stage when that interruption was absent. That explains the downstream gate failure, without explaining why the model's next execution operation failed.

The model's [public final message at client line 375](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/client/events.jsonl) reports that the execution service disconnected before continuity was committed or the program ran. This is a report of its service experience, not independent proof of the transport cause. Earlier model assertions about task observations or canaries are not used as empirical evidence here.

## Retained transport chronology

- The last completed command is client line 240. The [executor capture](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/executor-2-capture.jsonl) retains the last request at line 478 (`process/terminate`, 1790567350.0660875), response at 479 (1790567350.0685964), and send completion at 480 (1790567350.0696015).
- Client line 313 finishes commentary about preparing the program at 1790567385.745. Lines 314 and 319 record stderr lengths of 479 and 536 bytes, respectively, but no diagnostic text. No later completed command appears.
- The model final finishes at 1790567464.143. Only afterward, capture line 481 closes at 1790567464.44757 with `ConnectionClosedError(None, None, None)`. This closure is not proof of an earlier executor disconnect. The capture hash chain was verified for diagnostic chronology.
- The [codehost bridge summary](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/codehost-1-bridge.json) has no pump exceptions and wrapper exit code 0. It does not retain the EOF time or which pump ended first. Both [codehost](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/codehost-1-retirement.json) and [executor](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/executor-2-retirement.json) retirement diagnostics show no normal-wait timeout or wrapper kill.

The retained [client launch](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-005/orchestrator/interrupt/client/launch.json) declares a 600-second deadline; the turn lasted 225.156 seconds. No 180-second idle limit was found in the reviewed frozen Python executor/bridge/client sources. The private codehost connection explicitly calls `channel.settimeout(None)` after its short connection attempt, so the earlier socket idle-timeout defect is absent. Opaque native app-server/codehost internal limits remain unknown.

## Concrete source defects and missing evidence

The immutable [dev027 archive](../../../Architecture%20Map/releases/RCI001-C02-dev-027/code.zip) and [snapshot](../../../Architecture%20Map/releases/RCI001-C02-dev-027/snapshot.json) bind the exact source discussed below. These defects support prospective engineering work, but none is established as the unique cause of smoke005:

1. `isolation-session-9/wsl/codehost_bridge.py` stops when either pump completes (line 101); its abort predicate at line 109 checks only exceptions or a nonzero observed wrapper exit. An unexpected clean EOF has no explicit failure classification.
2. `readiness-session-10/boundary/inside.py` enters codehost mode at line 111, then terminates/waits the private child without returning its exit code, unlike executor mode. Wrapper exit 0 cannot establish that the underlying native codehost exited successfully.
3. The bridge retains final byte totals rather than connection-open/EOF/end timestamps and the first-ending pump. An extra simultaneous client is silently closed at line 63 without a rejection receipt. A clean final summary therefore does not establish uninterrupted availability.
4. `readiness-session-10/orchestrator/bootstrap_client.py:160–162` intentionally discards ambient stderr content and records only byte counts. Its privacy boundary is appropriate; useful prospective diagnostics need bounded allowlisted categories and redaction, not blanket ambient-log retention. This run's discarded text cannot be recovered from the retained client events.

## Supported next step and limits

A material, testable correction is available: preserve underlying codehost exit status; classify unexpected clean EOF; and record bounded connection lifecycle, first-ending pump, client-finishing state and safe diagnostic categories. Expected client shutdown and deliberate cleanup termination must remain distinct from premature native-child failure. Keep isolation, authority, model instructions and experiment criteria unchanged.

Before any new model qualification, test fake processes/sockets for early clean EOF, native child nonzero exit, long idle, extra-client rejection, and normal shutdown. A prospectively declared bounded non-model transport probe can then validate the corrected lifecycle before a new source freeze and fresh qualifiers. An unchanged retry is unsupported. No credential, administrative, security-policy or other human-only change is established as necessary by the retained evidence.

The [structured diagnosis](smoke-005-failure-analysis.json) contains 21 file bindings, exact source hashes, event identities, observed facts, source defects and uncertainty. It records no empirical pass, no assessment and no historical rewrite. This diagnosis implemented no repair and launched no process workload or model.
