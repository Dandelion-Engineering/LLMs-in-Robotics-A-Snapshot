# Session 17 — Repair administrator diagnostic automation

The no-model coverage helper is repaired and locally validated. The attempted
Windows elevation returned **`The operation was canceled by the user.`**
The helper did not launch. Campaign 002 remains unfinished with zero scored
starts; OS trace coverage and the underlying native socket-closure cause remain
unverified.

The [diagnostic packet](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/admin-coverage-automation-002/README.md)
contains the declaration, code, source snapshots, test receipts, launch script,
source manifest and failed elevation record. Windows reported cancellation;
the retained evidence does not distinguish a user click from a consent timeout.
The specific remaining human action is UAC consent for that bounded helper.
Codex can manage the run and read files directly; Randy need not type commands
or send screenshots. No retry or alternate privilege route was attempted.

## What changed and what was checked

The original helper assumed `Popen.pid` must equal the fixture's ready PID.
The live probe confirmed a separate project-venv redirector and direct
base-interpreter child. The repair uses a private Windows Job Object assigned
atomically at process creation, with kill-on-close and no breakaway. It records
both identities and verifies image, creation time, direct ancestry, job
membership and exact endpoint metadata. Cleanup requires both an empty job and
signaled retained process handles.

Four live controls passed: normal FIN/RST fixture completion, interruption
before release, foreign PID rejection and malformed port rejection. Twelve
helper checks passed, including ten complete paths using real fixture launches
with **simulated** admin commands, plus two path guards. The original nine
preflight/filter/netsh guards also passed against the repaired helper. These
checks establish local control flow and cleanup, not actual trace coverage.

The source-bound launch uses `Start-Process -Verb RunAs -WindowStyle Hidden`,
the exact project Python and the fixed helper. It creates no service or
administrator broker and changes no security setting. The declared capture
remains exact-loopback-port FIN/RST only, a 40-byte prefix, 16 MiB ceiling and
30-second bound, with idle/empty preflight and owned stop/filter cleanup.
The PowerShell launch script parsed successfully. UAC was observed pending;
the command subsequently exited 1. At 20:18:43 UTC, neither the output directory
nor launch receipt existed, and no consent process remained.

## Preserved failures and limits

The first new launch probe passed normal completion but failed three forced
retirement checks: job membership could empty before retained process handles
signaled. The correction waits for both within the same three-second bound;
it does not weaken either condition. The original failed receipts and source
versions remain. A later point-in-time query found all eight recorded launch
and ready PIDs absent; this does not retroactively qualify the failed checks.

The first full-helper suite passed nine of ten checks. Its changed-filter test
double parsed the `-p` token as the port and failed before applying the intended
mutation. Correcting the test indexes made all ten pass. Subsequent output and
capture-path guards brought the source-bound final suite to twelve passes.
All earlier failed checks and exact sources remain available. All twenty files
preserved from the two previous user-run attempts still match their hashes.

No model, native diagnostic, qualifier, pilot, queue job, scored attempt, trace
or packet filter was started. No campaign runtime, assessor, map/history,
registration or historical evidence was changed. Campaign 001 stays frozen.
Existing qualification history and Session15 accounting were not recomputed;
the helper tests are lightweight local development work, not queue/scientific
qualification results.

## Next action

After Randy directs another elevation attempt, reuse the tested helper only if
its source bindings still match and the declared output remains absent. Retain
the canceled first attempt and use a separately identified launch receipt.
The only user action should be Windows consent. Independently inspect actual
coverage, endpoint/clock correlation, loss/wrap, bounds and cleanup before any
native diagnostic. Inadequate coverage requires a separately scoped trace;
successful collection alone authorizes neither a model retry nor scoring.

The completed claims are
[helper repair](../../../Work/Done/repair-bounded-administrator-coverage-automation.md)
and [handoff](../../../Work/Done/record-repaired-coverage-helper-and-elevation-boundary.md).
