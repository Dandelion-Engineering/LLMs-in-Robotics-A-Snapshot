# Session18 — Synthetic trace coverage passed; native diagnostic ready

Campaign002 remains unfinished with zero scored starts or registrations. The
six-event synthetic collector now passes its declared coverage checks. A fresh
native interruption diagnostic is tested, frozen and ready for the next desktop
session. No native model, queue job or scored attempt launched in Session18.

I pulled main from99a3c99b to30748932 and worked without subagents. Randy then
explicitly approved bounded process scope and, after that failed, bounded host
scope in this Codex task. Later he interrupted for an app update and said he was
leaving the desktop: finish unattended work and leave any step needing him for
the next session. Preparation is complete; the remaining access step is one
Windows UAC consent. I did not open that prompt while he was away.

## What the live synthetic traces established

| Attempt | Actual exit and bounds | Independent outcome |
| --- | --- | --- |
| Exact Session17 helper resumed once | Integer0;0.7343255s;11,960bytes | Controls and cleanup passed, but the trace had only three metadata records and no FIN/RST coverage. |
| netsh TCPIP event attempt001 | Integer0;1.9512944s;2,031,616bytes | Twelve intended control rows, plus out-of-scope endpoints and process rundown/command lines. Scope failed. |
| Direct process-filtered attempt002 | Integer1;0.0152256s | Logging-mode guard refused before fixture release; cleanup passed. Terminal trace also showed six PID0 and two unrelated-PID closure records, so process scope failed despite successful filter API calls. |
| Explicitly approved host-scope attempt003 | Integer0;0.0592714s;196,608bytes | All nine checks passed: four synthetic controls, exact endpoint/QPC joins, six-event scope, bounds, no loss and complete cleanup. |

Evidence: [helper resumption](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/admin-coverage-resumption-001/README.md),
[event001](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/tcp-event-coverage-001/README.md),
[event002](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/tcp-event-coverage-002/README.md),
[qualified event003](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/tcp-event-coverage-003/README.md).
The original canceled elevation and every failed scope/coverage assessment
remain unchanged. UAC was the only desktop action; Codex collected the evidence
directly, without manual commands or screenshots from Randy.

The qualified trace uses TCPIP IDs1038,1039,1040,1043,1044,1468, ignores
keyword-zero events, and requests no packet contents, application buffers,
command lines, stacks, process rundown or other providers. It contained24
synthetic and12 other closure records plus required trace metadata. Raw ETL and
decoded host data remain local; repository records contain the synthetic
projection, counts, hashes and cleanup evidence. The original metadata-only
ETL copy is also excluded from Git. Test ETL placeholders contain no trace data.

Generic close/abort events may have payload PID0. Ownership must use exact
endpoint pairs and QPC time, not PID alone. Passing synthetic metadata coverage
does not prove complete kernel visibility, explain the native abort or qualify
the robot apparatus.

## Prepared native diagnostic and checks

[Diagnostic005](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/native-os-closure-001/README.md)
is frozen as `RCI001-C02-dev-097`, with986 source inputs. All958 dev096 inputs
and the original624 remain unchanged. The map now has155 revisions,472 declared
runs and471 results; the additional development run is prepared and unexecuted,
with no terminal result. Every earlier canonical map prefix is byte-identical.

The unchanged physical runner will perform one interruption with no resume.
A wrapper starts the qualified trace immediately before its first existing
retirement call, measures that overhead, and always calls the original cleanup
even if tracing fails. A one-shot elevated helper accepts only authenticated,
run-bound start/stop metadata, retains the worker's PID/image/creation identity,
and collects for at most25seconds plus a five-second stop allowance. Raw trace
is bounded to16MiB. No persistent privilege broker or security setting changes
are involved. Existing model, bootstrap, isolation, action and timing policies
are unchanged; this is diagnostic-only and cannot count as a qualifier.

The final control suite passed eleven lifecycle cases and six protocol guards
using real owned synthetic workers and simulated ETW. The wrapper suite passed
nine normal/failure cases and eight launch/configuration checks with mocked
external processes. PowerShell syntax and the desktop-unavailable guard passed
without elevation. Missing observer readiness prevents model launch; failed
arming retains original retirement; failed trace completion fails the wrapper.
Earlier source/test receipts remain preserved. These checks do not substitute
for the still-unrun elevated/native integration.

No operational observer configuration/key, elevation intent, native output,
storage monitor or queue submission exists for diagnostic005. Its README gives
the exact next-session procedure: validate frozen sources, create fresh local
control metadata, request one UAC consent, then submit the sole worker through
the existing storage-guarded queue after authenticated observer readiness.
Denied/timed-out consent must be recorded, with no alternate elevation route or
unchanged retry. No manual command or screenshot work is needed from Randy.

## Remaining scientific work

Smoke027/V29 remains permanently stopped. Its retained WinError10053 preceded
actual stdin closure by7.2268ms, excluding that later operation as this event's
cause; the OS/native cause is still unknown. Native004's nonreproduction remains
inconclusive. No supported runtime repair was established in this session.
After the new diagnostic, continue supported repair and full fresh
Raw/Transport/Host/native/boundary/smoke plus both pilots before the fixed twenty
scored slots and actual-results investigation. Preserve invalid/unknown/not-run
states, original deadlines, evidence gates and no-replacement rules.

Campaign001 remains frozen at6 valid,4 invalid,14 unrun. Qualifier history stays
at129 rows; accounting, production runtime, native assessors and historical
exports are unchanged. Session15's122-job accounting and31 observed-model-start
lower bound remain historical, not a fresh global census. The current pause is
the desktop-access boundary Randy explicitly requested, not campaign completion.
