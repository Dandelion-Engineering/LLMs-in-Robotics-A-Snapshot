# Campaign 001 investigation

Open `report.html` locally. It contains all styles, JavaScript and report data;
no web server, fetch, package installation or external asset is needed. Once
exported, original PNG files are adjacent local assets under `frames/`; retain
that folder with the report. Exact raw
evidence links resolve relative to the report within this retained checkout.
The page is a snapshot at its displayed build time, not a live status monitor.

Rebuild from the repository root after completed records become available:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/investigation/build.py'
```

The builder reads `campaign-001/execution-plan.json`, then the fixed per-run
`execution/<run>/disposition.json`, `storage/queue-receipt.json` and
`assessment.json`. It writes only this investigation folder's `report.html`,
`data.json` and `provenance.json`; those derived outputs can be regenerated.
`--plan` and `--output` can select alternate read/output paths for isolated tests.

## Evidence boundaries

- Every planned slot remains visible. Missing terminal evidence means pending;
  only an explicit `execution_status:not_run` disposition makes a slot unrun.
- The official receipt must be `succeeded` with an actual integer exit status 0
  before the builder opens any assessment or outcome trace. Failed/nonterminal
  queue attempts receive no inferred task score or timeline.
- Assessments must be admitted Campaign001 results and bind the same run, queue
  job, exact receipt bytes and predeclared manifest hash. The builder consumes
  that assessment rather than re-running scientific qualification.
- Protected history, broker calls and model/client events are independently
  rehashed against the admitted assessment's retained evidence inventory before
  inclusion. Other large image/numerical artifacts are not reread for this report.
- Invalid attempts with successful queue execution may show observed behavior
  for diagnosis, clearly labeled infrastructure-invalid and excluded from scores.
- The report includes actual public model messages and completed tool calls. It
  does not reconstruct private reasoning, unseen pixels or unrecorded motion.

`provenance.json` lists every consumed input's hash, bytes and role. Long display
items are explicitly excerpted. Up to approximately 400 camera observations per
episode are sampled uniformly in observation index for display, including the
last observation. All non-observation protected records and completed public
model/tool items are retained. Each event links its exact original file and
physical JSONL line, with protected event ID when present.

The timeline aligns recorded host `wall_unix_s` and native-client `emittedAtMs`
relative to protected `episode_started`. Item completion timestamps are receipt
times, not reasoning start times. Simulation time remains separate. Untimed
items are retained without invented timestamps. Coincidence on this display is
not, by itself, a causal claim.

## Denominators and examples

By-fixture Wilson95% intervals use valid task successes / valid assessed trials.
They assume independent trials, which model-service process isolation does not
prove. Infrastructure-based selection and the early stop make these descriptive
intervals, not calibrated guarantees of campaign reliability. The pooled valid interval follows actual valid counts; if validity differs
by fixture it is not an equally weighted fixture estimate. All-planned completion
bounds retain the fixed equal-fixture allocation and treat every unresolved slot
as failure versus success; these are sensitivity bounds, not confidence intervals.

Observed evaluator completion has separate counts and a sortable table column.
Only an authenticated succeeded/exit0 admitted assessment can supply
`observed_task_outcome`. Observed successes/failures, unknown assessed outcomes,
and observed successes among infrastructure-invalid attempts remain separate
from valid scores and Wilson intervals. Operational completion denominators show
all planned slots, attempts with an official recorded start timestamp, and
authenticated assessments. A timing-invalid observed completion can appear in
this diagnostic count without being promoted to scored success. Failed queue
outputs never contribute an observed task outcome.

The first/last scheduled attempt of each fixture remains preselected even when
pending or unrun. Additional first valid failures and first distinct invalid
categories are marked outcome-selected. First observed rejected robot requests,
local-versus-protected continuity differences, missing program final receipts and
bounded program invocations and limits are also selected for inspection when present; those
categories do not establish a cause. The separate `stock01-investigation.md`,
when present, is linked as episode investigation/interpretation rather than used
as an authoritative source of scores. Matching `home01-investigation.md` and
other per-run investigation notes are linked by the same naming rule.

## Verification

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/investigation/test_build.py'
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/investigation/qa.py'
```

Twelve synthetic tests check Wilson bounds, all-planned denominators, actual
integer exit0, failed-queue outcome non-consumption, pending versus unrun,
assessment/receipt binding, outcome-independent example selection, and trace hash
rejection, separation of invalid observed completion from scores, and exclusion
of failed-queue observations. Test fixtures are temporary and never enter the
actual report.

The first actual build contained one admitted stock attempt with 487 displayed
events (420 protected-world, 40 public model/tool and 27 gateway) and 23 pending
slots; that is a build-time snapshot, not the final campaign result.

Browser visual QA was attempted with the provided browser tool. The in-app browser
was unavailable, and Chrome explicitly rejected the local `file://` report under
its URL security policy with an instruction forbidding alternate browser routes
or workarounds. No server/browser workaround was attempted. Static syntax and
structural checks are available; visual layout and live-control QA remain
unverified through that tool. This does not establish that ordinary local opening
by the user is blocked.

## Original sparse RGB frames

`export_frames.py` is a queue-compatible post-campaign analysis worker. It refuses
to proceed until all 24 slots have explicit terminal dispositions. Root must run
it through the shared compute queue after experiments settle, then require the
official job status `succeeded` / integer exit0 before treating its outputs as
complete:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/investigation/export_frames.py' --build-report
```

The command above is the **worker command to submit**, not a suggestion to bypass
the shared queue. It exports at most 32 original RGB PNGs per selected run and
128,000,000 aggregate PNG bytes. The selections are the predeclared first/last
run of each fixture plus the first valid failure of each fixture and the first
distinct infrastructure or observed-behavior category. Additional omissions due
to the export cap stay explicit. Uniform selected indices include the first/last
available original capture within each run; no inferred frame fills a gap.

The unchanged qualified `recorder.Reader` authenticates compressed and restored
SQLite identities and paired-image hashes. The exporter first checks the
container files against the admitted evidence inventory and checks the reader's
source against the original 010d snapshot. `Reader.image()` yields the already
encoded PNG; the exporter copies those exact bytes, with no image recoding,
resizing, renderer, simulation, generated image, or historical pixel replacement.
The paired depth is hash-checked by the existing reader but not duplicated in this
RGB package. A reader/container identity or format problem produces an explicit
unavailable entry, rather than substituted pixels.

The frozen host uses a 2-second sparse image policy with a 12 MB paired-image
quota. The availability table records every offered capture and its status;
quota exhaustion can leave late parts of a completed episode without retained
images. The panel shows offered, retained and exported counts, availability
reasons, last offered/available capture times, and selection/cap omissions. It
must not be described as complete episode footage.

Synchronization joins a frame's exact stored `capture_time_s` to the earliest
protected public observation with the same `capture_sim_time_s`. The original
capture simulation clock and public-observation publication wall/simulation
clocks remain separate. Capture wall time is unavailable and is not inferred.
The automatic viewer chooses the latest exported frame already published by the
selected event and reports publication age. Explicit manual frame selection is
labeled and can jump to the matched publication event. Unmatched original frames
remain inspectable without an invented wall-time association.

These are retained sensor images for human investigation. Model image viewing
remained disabled in the qualified framework; the panel does not claim that the
model received these pixels. Source records and public structured observations
remain the evidence for model-accessible information.

Four additional synthetic tests in `test_frames.py` cover bounded selection,
exact first-publication joins, export caps and refusal before all slots settle.
No actual frame extraction was run while the campaign was active. After queued
export, rerun `qa.py` and inspect representative original PNGs with the local
image viewer; no browser-policy workaround is needed for that image inspection.

## Final retained snapshot

All 24 slots have terminal dispositions: 10 started, 6 valid successes, 4
infrastructure-invalid, and 14 not run after the predeclared consecutive-invalid
stop. The 10 observed evaluator successes include 4 diagnostic invalid outcomes.
The pooled valid Wilson95 interval is 60.97%–100%; all-planned sensitivity bounds
are 25%–100%. Neither turns invalid or unrun attempts into scored successes.

The official frame export/build job `20260927T201306381734Z-651d8291` succeeded
with integer exit status 0. It copied 128 original PNGs for stock01, home01,
home02 and stock05, totaling 7,991,942 bytes. Camera quota exhaustion leaves late
activity unavailable; these sparse frames are not complete episode coverage.
Stock02 is an additional program-behavior example with no images in this bounded
export. Its one unique invocation has separate admission/final receipts and uses
public history/status plus local note writes, with no actuation calls in the
reviewed source. Final report-only rebuild and static QA receipts are retained
alongside the report.

Final report-only rebuild job `20260927T201949118812Z-6f7499f0` succeeded with
integer exit status 0. Static QA checked 247 local links, 24 fixed slots, 5,218
displayed events, original PNG hashes and image caps. Twelve report tests and
four frame tests passed. `image-inspection.json` records five actual 640×480
PNG inspections with exact hashes; this does not constitute browser layout or
interactive-control verification. The final HTML SHA-256 is
`b00762edd10e54f0561ba27f197bab94942bb32e86efa1dbcb976580caff97b3`.
