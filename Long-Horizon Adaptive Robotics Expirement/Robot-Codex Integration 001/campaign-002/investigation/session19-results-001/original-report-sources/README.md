# Campaign 002 investigation

Current Session14 history contains 122 entries, including the inconclusive Native003 usage-limit diagnostic. Smoke026 remains the unresolved model-qualification gate; zero scored slots have launched. See [current diagnosis](../io-repair/socket-abort-native003-diagnosis-002/analysis.md) and [current campaign state](../README.md).

The currently generated qualification companion is the retained session-13
snapshot, whose endpoint was a failed qualification gate and blocked campaign.
In that historical snapshot, native003 stock-1 failed strict timing despite all
six reference tasks completing and all resource gates passing. Synchronous
protected-journal fsync was the concrete observed delay; the underlying cause
remained unresolved. PERSIST was not adopted, and the exFAT D: alternative was
not used because it could not preserve the existing Windows ACL boundary.
No subsequent model stage or scored attempt had launched at that snapshot.

The source [qualification history](qualification-history.json) may be newer
than the generated companion. Its `attempts` and bound `current_status` give the
current retained count and phase. Read the generated report's build time and
provenance to identify its snapshot; a history append does not rebuild it or
establish campaign completion.

The separate empirical builder is prepared to compare Campaign001's frozen
six valid successes, four infrastructure-invalid attempts and fourteen not-run
slots with all twenty actual Campaign002 dispositions after execution settles.
Its gate holds until those dispositions are terminal. These reports consume
authenticated retained evidence and never launch a model, simulate a trajectory
or alter outcomes.

The builder, exporter and event explorer adapt the Campaign 001 implementation
into this new directory. The Campaign 001 sources and report remain unchanged.

## Permanent qualification companion

`qualification_report.py` builds a separate compact investigation from the
explicit completed `qualification-history.json`. It remains useful before or
after scored launches. It shows the apparatus diagram, selectable original
verdicts, exact failures, inclusive phase measurements, and original analysis
JSON with source links. It does not require twenty dispositions or create
scored rows. The empirical builder's twenty-disposition gate remains intact.

The builder authenticates each official queue receipt before opening its
outputs, then verifies indexed artifact hashes and byte counts. A canceled
attempt must have no start time and no outcome artifact. Host diagnostics
follow assessment → bound host result → exact timing metadata → declared binary
hashes. When the original assessment has `timing: null`, raw phase/resource
measurements are explicitly diagnostic-only; they cannot replace a failed
strict verdict. Original GC002 and bridge003 analyses are preserved rather
than recomputed. The 23 recorder subphases are inclusive and overlapping;
missing older instrumentation is unavailable, never zero-duration evidence.

The continuous-owner apparatus has two execution threads: physics advances on
its owner thread while the supervisor synchronously persists Journal and SQLite
evidence. The original owner timing ledger remains the source of any strict
timing verdict. A separate `supervisory-diagnostics/timing-v2.json` and its
`timing-samples.bin` supply persistence attribution only. The companion requires
both files to be explicitly indexed with exact hashes and byte counts under
the assessment's bound host-result directory. Their declared sample identity
and clock origin must agree with the owner metadata. Both receive independent
provenance entries and source links. The phase selector keeps the ledgers
separate: inclusive durations overlap across threads and must not be added.
Absent older instrumentation remains unavailable. Describing this apparatus
or displaying its diagnostics does not claim that the repair qualified.

The companion also accepts `rci-c02-protected-io-assessment-1` as a fixed,
non-physics shared-durability diagnostic. Its `passed` boolean means diagnostic
completion, parity, ordering and evidence integrity; `qualification_passed`
remains false, `scorable` remains false and `task_outcome` remains unknown.
Original per-operation latency distributions are shown without recomputing or
pooling them. For this schema only, `queue_job_id` may be absent if the
assessment explicitly binds the exact authenticated history receipt through
`official_queue.path` and `official_queue.sha256`. The displayed job ID then
comes from that receipt; a provided ID must match it. A matching ID alone
cannot replace the receipt binding. The history entry must index the
`-assessment.json` artifact and official receipt with their exact hashes and
byte counts, and its passed/failed status must match diagnostic integrity.
No qualification success, model outcome, device-cause attribution or production
adoption is inferred from this diagnostic.

The companion also accepts the independent recorder-feasibility assessment's
`mechanical_feasibility_passed` boolean without requiring a host-result binding.
It preserves all eight fixed DELETE/PERSIST rounds and four abrupt-process
recovery-copy assessments, including failures or unavailable latency. Per-round
median/p99/maximum operation latency is descriptive and copied from the original
assessment; no pooled winner, task-performance result, physics timing pass,
power-loss guarantee or production adoption is inferred. The original checks,
errors, Reader fingerprints and storage boundaries remain inspectable. A new
feasibility history entry still requires an authenticated completed result.

Preflight withdrawals use the separate `campaign002-preflight-not-run-1`
contract: unknown validity, unknown task outcome, not assessed, and no queue
object. Its only permitted artifacts are the exact preflight-failure record,
manifest and source snapshot, with their hashes joined across identities.
The recorded `queue_submitted: false` must agree with absent launch metadata
and the expected evidence directory. No official receipt, assessment, timing
or attempt output is fabricated or read for this branch. This preserves a
source-inventory failure without treating its frozen revision as qualified.

The scored-launch card inventories configured launch intents, queue receipts,
registration and disposition files without reading scored assessments or
interpreting disposition outcomes. Nonempty execution metadata prevents a
later rebuild from calling the campaign unlaunched. The captured inventory
and its limitations are linked; out-of-band execution is not ruled out.
An existing empirical report is linked when available, and a later empirical
build links the companion. C001 remains the original 6/4/14 outcome inventory.

Queue this command from the repository root using its absolute virtual-env
interpreter (do not run the substantive build outside the shared queue):

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/investigation/qualification_report.py" --qa
```

It writes `qualification-report.html`, `qualification-data.json` and
`qualification-provenance.json`. `--qa` verifies links, original input bytes,
classifications and JavaScript syntax. Browser layout remains a separate
check after the authenticated queued build. `qualification_qa.py --source-only`
and `test_qualification_report.py` perform bounded source/synthetic checks
without reading active qualification outputs or building an empirical report.

## Build after execution settles

Submit exports and report building through the shared compute queue. All 20
dispositions must exist and be terminal before either operation reads outcomes.
The execution plan follows Campaign 001's `attempts` layout: ordinal, run ID,
family, immutable manifest path/hash, host evidence path, orchestrator evidence
path and storage receipt path. Valid IDs are stock-01 through stock-10 and
home-01 through home-10 under the `RCI001-C02-` prefix.

```powershell
python -X utf8 -B export_frames.py --plan ../execution-plan.json --snapshot <new-frozen-snapshot.json> --qualification-index qualification-history.json --build-report
python -X utf8 -B qa.py
```

Use the project virtual environment's absolute interpreter through the queue.
Run from this investigation directory, or provide absolute script and argument
paths. Alternatively `build.py --plan <plan> --qualification-index <index>`
builds without exporting more images. Default generated output is this directory.
`qa.py` checks the completed package and JavaScript syntax. Browser layout and
interaction QA must be performed separately; static QA never claims to provide it.

`storage/queue-receipt.json` is preferred, with `official-status.json` as a
fallback. The chosen bytes must match the assessment's receipt binding. Queue
state must be `succeeded` with an integer exit status of zero before any
assessment or trace is read. Scoring additionally requires the assessment's
explicit `scorable: true` and scientific admission. Raw episode assessments
remain unscored. Failed/cancelled queue outcomes are visible as diagnostic
dispositions; their output files are not consumed to infer task completion.
Every completed disposition must bind the exact assessment SHA-256 before its
contents are consumed; altered or unbound assessments are refused.

## Qualification history input

No-model prerequisite rows use `attempt_kind` values
`raw_event_preflight_diagnostic` or `transport_probe_diagnostic`, with the
existing `campaign002-history-diagnostic-1` contract. Supported result/command
pairs include the original raw-preflight-1 / `raw_event_preflight.py` and
codehost-probe-1 / `codehost_probe.py`, plus
`campaign002-raw-event-preflight-2` / `raw_event_preflight_v2.py` and
`campaign002-codehost-channel-probe-3` / `codehost_transport_probe_v3.py`.
Each row binds its original result, exact successful official queue receipt,
frozen snapshot and verified readiness entry. New entries may use the neutral
artifact label `Verified readiness entry`; the historical
`Verified v11 readiness entry` label remains supported. Exactly one is required.

Channel-probe-3 retains the ordered `cases[*].case` identities `multi_channel`,
`foreign_owner`, and `in_flight_eof`. The latter two must retain verified
expected-failure proofs, `diagnostic_only: true`, and
`production_qualified: false`. Their diagnostic check passes never become
production transport passes. The displayed case table and independent static
QA enforce this distinction. No prerequisite row advances the latest completed
qualifier, creates a scored outcome, or replaces an earlier failed assessment.
Schema support does not append history or rebuild the generated report.

Supply a settled, human-auditable closeout index so failed, cancelled and
superseded qualifications remain visible. The index is a report input, not a
qualification certificate. The report links the exact artifacts and does not
reinterpret a failed queue outcome as successful qualification.

The session-13 history snapshot retained these first thirteen qualification and
diagnostic dispositions (later entries and the current count are in the linked
[history](qualification-history.json)):
native001 passed, boundary001 canceled before start, boundary002 passed,
smoke001 failed, host-probe001 failed strict timing, boundary003 passed, and
host-probe002 passed its 240-second no-model diagnostic, and host-probe003
failed host timing and the maximum memory sampling gap. Host-probe004 passed
its 900-second no-model diagnostic with finer instrumentation; this does not
identify or erase the earlier stall or qualify model-loaded timing. Its 50
linked artifacts from those first nine include the authenticated GC correlation,
probe003 bridge delay, and probe004 recorder/timing analyses. The index also
preserves recorder-feasibility001/dev010 and native002/dev012 as preflight
not-run, unknown, and not-assessed, plus recorder-feasibility002/dev011 as a
passed mechanical benchmark. Native003/dev013 is the thirteenth retained
disposition: invalid/unknown, with five strict timing case passes and the
stock-1 failure at 100.1493 ms lag and two of 59 outside-RTF windows. There are
70 artifact links across those first thirteen. Its original diagnosis and six reference
case assessments remain inspectable, with observed reference task completion
separate from qualification validity and model scoring.
The benchmark's fourteen checks, eight rounds and four crash copies passed;
the separate engineering decision does not adopt PERSIST because these small
fixtures do not establish host-tail improvement or production-scale coverage.
Those retained attempts used the production behavior frozen for their own
revisions; later continuous-owner source changes do not revise their outcomes.
None is a scored Campaign002 recovery outcome. Add
later completed attempts without replacing these entries before the final build.

```json
{
  "schema": "campaign002-qualification-history-1",
  "attempts": [
    {
      "run_id": "EXAMPLE-ONLY",
      "revision": "exact frozen revision",
      "status": "cancelled",
      "reason": "Describe the preserved terminal disposition.",
      "artifacts": [{"label": "Official receipt", "path": "absolute local path"}]
    }
  ]
}
```

Permitted terminal labels are `passed`, `failed`, `cancelled`, `not_run` and
`superseded`. Omit the argument to display qualification history as unavailable;
the report then makes no independent requalification claim.

The index must retain `RCI001-C02-smoke-001` as `failed` whenever that attempt
is included. Its original dev004 assessment and raw evidence stay linked; a
later revision or passing attempt does not replace it. Include its official
receipt, assessment, and `../qualification/smoke-001-read-diagnosis.md` among
the artifacts. The builder rejects relabeling that known failed attempt as a
pass, cancellation, or superseded result. No absent attempt or future result is
invented when an index is not supplied.

## Inspecting the evidence

The report shows both campaign denominators, every new disposition, transport
and timing verification totals, and the full qualification closeout index.
Campaign 001 is linked directly. Its classifications are never recomputed under
Campaign 002's prospectively changed timing measurement method.

The earlier dev005 apparatus uses one Windows QueryPerformanceCounter clock
through `perf_counter` for elapsed loop time, pacing, and timing samples. Its
single-loop interval retains samples before catch-up, after host work, and at
the terminal boundary. The prospective continuous-owner apparatus instead
retains owner physics timing and separate supervisory persistence diagnostics
on their common clock origin. Initialization and cleanup remain outside the
declared interval. The retained metadata and frozen revision identify the
method used by each attempt. The original thresholds and full-window monitor
are unchanged. These source descriptions do not claim a timing qualification
or a causal repair benefit.

When an authenticated assessment binds `timing-v2.json`, the report retains its
phase diagnostics alongside the independent timing replay: physics, sensing,
public packet generation, observation updates, and journal serialization, open,
write/flush, fsync, close, replace, or retry waits where recorded. Parent/child
durations are inclusive and overlap, so they must not be summed. Bounded slow
rows aid attribution; they are not a continuous scheduler trace or proof that
an outside process caused a delay. Synchronous executor capture also adds disk
work; the final timing qualification must include that exact helper revision.
For a continuous-owner episode, the empirical assessment inventory must bind
both `protected_host/supervisory-diagnostics/timing-v2.json` and its sample
binary before the separate supervisory diagnostic can be read. The metadata
and binary hashes and byte counts are checked independently; their origin must
match the owner ledger. An unbound file is unavailable even when present.
The separate panel and source links preserve that distinction without adding
a second strict verdict.

Where later metadata provides them, the same hash-bound diagnostic panel also
shows `garbage_collection` and `host_memory`, together with the assessment's
collector/memory gate values. These describe prospective bounded cyclic-GC
deferral and native host-memory controls only when recorded. Older metadata may
have the earlier GC diagnostic schema or no memory receipt; it is not judged
against a later policy, and a missing field is not converted into a pass.

The output-capture panel separates three observations: the model-requested
literal source read, trusted executor stdout with completed websocket sends,
and the app's displayed aggregate. A send completion is local transport
acceptance toward the app, not an acknowledgment or proof that all bytes were
visible to the model. Full source-read correspondence requires exact
request/process/tool IDs and protected episode/invocation/observation identity;
the app projection keeps its separate byte count, hash, and equality flag.
Startup instruction checks still require their original app-visible evidence,
apart from an authenticated exact successful read of an empty continuity file.
Missing bytes, incomplete capture, and absent fields stay unverified. The
64 MiB combined capture-journal bound is per invocation, fails closed on overflow,
and does not relax the overall storage budget. A fabricated agent note cannot
replace an actual protected canary execution or missing source bytes.

The prospective [literal-read and canary method](../io-repair/READ_EVIDENCE_V2.md)
adds ordered, complete cat-chain segmentation and a separately labeled canary
check-values proof. The latter requires reviewed protected source, closed
execution environment and authenticated successful exit, plus the matching
saved boolean results. Redirected canary stdout is not relabeled as captured:
full JSON identity and variable diagnostic details remain unverified. Where
retained, `actual_canary_retained_evidence` is exposed in the source/capture
panel with each proof's scope; older absence remains unavailable.

Each episode synchronizes public model/tool receipts, protected world events,
authority, command lifecycle and continuity commits on their recorded wall
timestamps. Simulation times remain separate. The state panel shows only the
latest retained record at or before the selected receipt, with source and line
identity; it does not interpolate missing state or reconstruct private reasoning.

The first and last scheduled run in each family are always selected, including
not-run slots. Additional examples are explicitly outcome-selected first valid
failures and first infrastructure/behavior categories. An unrun preselection is
never replaced by a more successful run.

The exporter verifies the frozen recorder source, assessment inventory and
original PNG hashes. It selects up to 32 available images per selected episode,
including the first and last available frame, under a 128 MB presentation budget.
This is a display/export bound, not a campaign storage permission gate. Pixels
are copied byte-for-byte. Missing or retired images stay unavailable. Synchrony
uses an exact capture-simulation-time join to first public publication; the
automatic view never presents an image before it was published.

`test_build.py` and `test_frames.py` use temporary synthetic data only. They do
not read ongoing campaign outputs. No generated report/data in this directory
should be interpreted as complete until the queued build and final QA succeed.

## Later status and model-qualifier bindings

`current_status` retains the existing closeout schema. The legacy
`qualification_failed_blocked` state still binds its failed assessment.
`qualification_in_progress` instead binds the latest completed history row
through `basis_run_id` and `basis_assessment_sha256`; a boundary row may bind
its original `suite-result.json`. Neither state remains current if newer
scored launch metadata appears. Running-stage outputs are never a basis.

A boundary or native raw pass may still fail final admission. When that
happens, index the original coordinator `disposition.json` and place its exact
path/hash/bytes artifact binding in the row's `admission_disposition`. Its
manifest, snapshot, official queue and assessment entries must match the same
history row's indexed artifacts. The history status follows the retained
admission decision; the raw suite verdict, exact rejection and original checks
remain separately visible. Planned but unlaunched stages are not extra history
attempts unless they have the existing explicit preflight-withdrawal contract.

Raw model pilots use `robot-codex-campaign-assessment-2`; do not add a fabricated
`qualification_passed` flag. Index their original assessment, manifest, snapshot,
official queue receipt, coordinator stage disposition, coordinator preflight,
original admission verifier source and frozen base assessor source. Add:

```json
"pilot_admission": {
  "schema": "campaign002-pilot-history-binding-1",
  "disposition": {"path": ".../pilot/disposition.json", "sha256": "...", "bytes": 0},
  "preflight": {"path": ".../preflight.json", "sha256": "...", "bytes": 0},
  "verifier": {"path": ".../admission.py", "sha256": "...", "bytes": 0},
  "base_assessor": {"path": ".../assessment/assess.py", "sha256": "...", "bytes": 0}
}
```

These are placeholders: every binding must exactly match an indexed retained
artifact. The original preflight binds the verifier, the snapshot binds the
base assessor, and the raw assessment binds the queue, manifest, snapshot,
assessor and sibling `code.zip`. The builder reads the verifier's declared
`PILOT_CHECKS` without executing it. A passing admission additionally requires
valid task evidence, no failed checks, every declared check, the fixed model,
bootstrap, one-call family fixture and passing original timing/resource flags.
A valid task failure is allowed by the original apparatus admission contract;
the observed and assessed task outcomes remain separate from campaign scores.
Failed pilot admissions retain their original errors and observations.

To expose owner and supervisory phases for smoke/pilot stages, also index the
protected host `result.json`, both timing summaries and both sample binaries
(with GC/memory samples where declared). The raw pilot's protected-host evidence
inventory, or smoke's exact input path/hash map, must authenticate that host
result before its ledgers are consumed.

`qualified_campaign_in_progress` additionally requires a `final_ledger` artifact
binding with exact path/hash/bytes. The original completed-ledger schema must
contain native, boundary, smoke and exactly two family pilots. All five stages
must join exact passed history artifacts for manifest, snapshot, queue and
assessment, preserve their roles, and end with the current basis row. This
presentation checks the retained completion chain; it does not independently
reissue a scientific admission certificate.

`campaign_terminal` requires that same completed qualifier chain plus
`terminal_plan`, `terminal_stop` and an ordered list of twenty
`terminal_dispositions`, each an exact path/hash/bytes binding. They must identify
the actual `execution-plan.json`, `execution/campaign-stop.json` and each planned
slot's disposition. All dispositions must be terminal and slots after an early
stop must remain `not_run`. This establishes terminal accounting only. The
separate empirical builder still authenticates outcomes and retains its own
all-twenty-dispositions gate. No future status is inferred from source support.
