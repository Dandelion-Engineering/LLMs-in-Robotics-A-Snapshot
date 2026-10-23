# External Campaign 001 storage guard

The guard runs beside the unchanged, directly queued `readiness-session-10/orchestrator/physical.py`. It never starts a model/simulator, wraps or alters that queue argv, changes queue state, deletes evidence, or modifies a frozen framework source. The campaign owner starts it before submitting each immutable attempt and checks its final receipt with the official queue receipt.

Randy's latest approval makes 37,962,254,720 additional bytes a **planning allowance**, not a hard limit. Exceeding it produces a notice; 1.5 times that allowance produces a stronger notice to notify Randy. Neither threshold automatically invalidates an attempt or stops admission. An observed capacity threat stops admission and requests protected host shutdown: the trigger is below the preserved 100,000,000,000-byte reserve plus 2,000,000,000 bytes for bounded retirement. No historical deletion or additional campaign is authorized.

## What is measured

[policy.json](policy.json) fixes these native scopes:

- `Robot-Codex Integration 001/local-evidence/campaign001`: all host and orchestrator evidence, including model/tool transcripts and exported runtime copies.
- `Robot-Codex Integration 001/campaign-001`: manifests, registration, monitoring, assessment and investigation records.
- `C:/Users/cresp/AppData/Local/RobotCodex/Campaign001`: all native runtime workspaces.
- `C:/Users/cresp/.codex/sessions`, `.codex/sqlite`, and only top-level `.codex` files beginning `state_`, `logs_`, `thread_history_`, or `session_index.`: session/transcript and service database growth. Watched contents are never opened. The prefix filter does not traverse private directories or read login credentials.
- The shared queue's `runtime/logs`: metadata growth only; log contents are not consumed while execution is pending.

WSL accounting covers **all** `/var/tmp/robot-codex-session10`, including every durable runtime workspace, continuity backing, generated program/note, protected synthetic control, namespace identity record and retained temporary file within that root. This discovers new random runtime roots even before `runtime-location.json` is published. The exact frozen namespace exposes only `notes`, `programs` and `.continuity` as writable durable binds. Its `/tmp` is namespace-local tmpfs; its memory/swap use is not claimed as durable evidence. Runtime/model transcripts retained by the Windows orchestration are included in the native scopes above.

Regular files are deduplicated by volume/device and file identity across overlapping roots and hardlink paths. Separate copies with identical contents still count separately. Symlinks/reparse points are not traversed; an accounting root that is itself an alias is rejected. The fixed `Continuity.md` symlink has its ordinary `.continuity/Continuity.md` backing counted once. Socket/device entries and skipped links are reported separately. This is logical-file accounting, not allocated cluster measurement or content authentication.

The initial immutable baseline records each distinct identity's logical size. Later samples sum **positive growth per identity**, including every new identity. Shrinkage or deletion elsewhere never offsets additional evidence. Shared Codex/queue/WSL growth is conservatively included; it is not attributed entirely to Campaign 001. Native and WSL growth are added. The WSL VHD's byte size is not added again to that logical sum; native volume free-space readings capture its actual host-disk capacity impact. WSL filesystem free space is checked separately.

## Interface

The implementation is [storage_guard.py](storage_guard.py). The accepted initial preflight/baseline is [baseline-001.json](baseline-001.json); [preflight-001.json](preflight-001.json) is an earlier engineering measurement, taken before the additional alias-root check, and is not the bound qualification input. The policy and monitor source hashes in [qualification.json](qualification.json) identify the implementation to seal in campaign admission.

Create a fresh baseline only before scored work, while preparing admission:

```text
python -X utf8 -B storage_guard.py baseline --config policy.json --output baseline-001.json
```

Start each monitor before submitting its attempt, with absolute paths:

```text
python -X utf8 -B storage_guard.py monitor --config POLICY --baseline BASELINE --output EXECUTION/RUN/storage --job-file EXECUTION/RUN/queue-submit.json --run-id RUN --manifest MANIFEST --evidence ORCHESTRATOR --host-evidence HOST --workspace WORKSPACE
```

Use a hidden Windows subprocess (`subprocess.Popen` with an argv list and `creationflags=subprocess.CREATE_NO_WINDOW`), or a terminal process. The output directory must be fresh. The owner waits for `storage/ready.json` and checks that neither `admission-stop.json` nor process failure exists. Only then submit the unchanged direct physical command through the shared queue, and atomically save its official submit JSON to `--job-file`. The monitor accepts the official `id` field (or `job_id`). Default maximum waiting time is 12 hours. It polls only the supported queue `status` command and never `cancel` or edits queue files.

Outputs:

- `ready.json`: first complete healthy native/WSL sample finished; safe to submit this attempt from a monitoring perspective, subject to independent campaign admission.
- `samples.jsonl`: timestamped aggregate samples, per-scope logical totals/additional bytes, counts and volume free bytes. A final sample follows official terminal queue state.
- `live-status.json`: current peak, minimum free bytes, sample count, notices and latched stops.
- `admission-stop.json`: persistent stop signal on capacity threat, scan/status failure, excessive sampling gap or monitor deadline. The owner must stop new admission. A failure cannot later become a pass merely because capacity recovers.
- `queue-receipt.json` and `receipt.json`: final official state plus source/policy/baseline bindings, exact run/path identity, hashed samples and queue receipt, time coverage, peak and minimum capacity.

`coverage_complete=true` requires first monitoring time no later than official queue `started_at`, a final sample no earlier than `ended_at`, and no latched failure. Coverage does not mean the queue succeeded: independently require official `state=succeeded` with integer `exit_status=0` before consuming experiment outputs. A missing monitor receipt is incomplete monitoring, not a pass. The campaign assessor separately checks source, configuration, scope and final receipt hashes.

## Stops, qualification and limits

When a stop is latched, `safe_stop=true` permits only the current attempt's ephemeral protected host-control capability, read in memory from that attempt's `operator-endpoint.json`. No user login credential is read. The URL must be explicit IPv4 loopback without redirects, credentials, query or path. The guard reads protected status, then requests `/operator/stop` using its observed authority epoch. Only accepted/failed status, time and exception class are retained; capability, URL, request headers and response content are never copied to monitoring receipts. Root separately verifies the frozen orchestrator's cleanup and namespace retirement. The guard does not kill processes and an accepted host stop alone does not prove namespace retirement.

[qualification.json](qualification.json) records **12 passing non-model tests**: native hardlink/overlap deduplication, independent-copy counting, deletion/shrink counterexamples, no watched content reads, optional/missing-root behavior, top-file filter isolation, flexible planning versus hard free-reserve handling, actual WSL hardlink/symlink escape controls, synthetic protected-stop HTTP exchange and redaction, early/late queue coverage, and scan failure refusal. Queue interval tests use synthetic receipts; the stop endpoint is a bounded local fake, not the physical host. The real preflight measured 1,657 native files and 217 WSL files in 3.267 seconds, with approximately 418.845 GB native free and 1,009.128 GB WSL free. These are point-in-time readings, not a promise of future capacity.

The guard targets a sample start every 5 seconds and latches a gap above 30 seconds; WSL scans have a 10-second timeout. Metadata races from atomic mirror replacement are counted, and each native/WSL pair is an interval rather than an atomic volume snapshot. Reported temporal peak is the **maximum observed sample and a lower bound on the true peak**. It can miss brief between-sample files and growth. It is external monitoring with prudent headroom, not a kernel allocation quota or a proof that an arbitrary writer cannot cross the reserve before shutdown. Native scans are metadata-only but their elapsed time is not forcibly capped; any stall appears as a failed gap at the next cycle. Independent frozen timing assessment must still detect undue monitor or host load. Nothing here grants timing, scientific admission or task success by itself.

Reproduce qualification without a model/simulator:

```text
python -X utf8 -B qualify.py --preflight baseline-001.json --output qualification-NEW.json
```

Keep prior qualification outputs unchanged. Seal the exact tested monitor, policy and external assessor before the first scored outcome; no tuning follows campaign outcomes.
