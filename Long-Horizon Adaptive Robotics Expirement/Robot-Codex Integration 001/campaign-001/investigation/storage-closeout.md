# Campaign 001 storage closeout

Storage did not trigger the campaign stop. All ten started attempts have authenticated, complete guard coverage with no storage notice, reserve stop or protected-stop request. The maximum observed cumulative additional storage during those attempts was **430,748,225 bytes (0.431 GB)**, against the approved **37.962 GB planning allowance**. Minimum observed C: free space was **417.790 GB**, preserving the 100 GB reserve by 317.790 GB. The campaign stopped for the separately recorded infrastructure-invalid sequence, not a storage threshold.

The [compact JSON evidence](storage-closeout.json) binds each guard receipt, official queue receipt, sample stream, common baseline, monitor and policy. It records all 24 dispositions as observed: six valid successes, four infrastructure-invalid attempts with task outcome unknown, and fourteen not run. This closeout does not reinterpret task scores.

## Verified monitoring record

Every opened official queue receipt reports `succeeded` and integer `exit_status=0`. The ten guard receipts' run identities, hashes, monitor/policy/baseline bindings, sample counts, before/after queue coverage, recomputed sampled peaks and recomputed native/WSL minima agreed. There were no verification discrepancies.

| Slot | Attempt | Samples | Cumulative observed additional peak, MB | Minimum C: free, GB |
|---:|---|---:|---:|---:|
| 1 | stock-01 | 56 | 43.599 | 418.513 |
| 2 | home-01 | 80 | 97.533 | 418.220 |
| 3 | home-02 | 70 | 143.905 | 418.148 |
| 4 | stock-02 | 61 | 190.228 | 417.852 |
| 5 | stock-03 | 50 | 226.686 | 417.790 |
| 6 | home-03 | 71 | 274.630 | 419.752 |
| 7 | home-04 | 69 | 320.631 | 419.652 |
| 8 | stock-04 | 46 | 353.361 | 419.591 |
| 9 | stock-05 | 48 | 384.797 | 419.316 |
| 10 | home-05 | 72 | 430.748 | 419.258 |

All sizes above use decimal MB/GB. The peaks share one campaign baseline and **must not be summed**. They include conservatively counted shared-service growth, not just each attempt's own artifacts.

Across **623 samples**, maximum monotonic sample-start gap was 5.016 s; the separate reconstruction from saved UTC timestamps was 5.023845 s. Both are below the sealed 30-second monitoring-gap limit. The first guard sample began at 19:09:00.869873 UTC and the last completed at 20:10:31.253720 UTC on September 27. Coverage is complete for each queued interval; it is not claimed continuous between attempts. Minimum observed WSL-filesystem free space was **1,009.098 GB**. Native free space is checked separately because a virtual filesystem's free capacity does not establish available physical host capacity.

## Fresh capacity and completed export

A metadata-only scan ran from **20:13:58.169825 to 20:14:01.820555 UTC** after the ten attempts, without a model, simulator, queue job or whole historical-project census. Relative to the same baseline, it observed **459,370,950 additional logical bytes**: 457,870,687 native and 1,500,263 WSL bytes. Current free space was **419,273,232,384 bytes on C:** and **1,009,088,638,976 bytes in WSL**.

Separately counted current campaign roots were:

| Root | Distinct logical bytes | Regular file paths |
|---|---:|---:|
| Native campaign host/orchestrator evidence | 280,676,346 | 545 |
| Campaign compact package and investigation | 31,489,136 | 419 |
| Native Campaign001 runtime workspaces | 109,359,838 | 72 |
| Entire retained WSL session10 root, including earlier runs | 2,571,915 | See snapshot |

These root totals describe present contents, including pre-existing preparation where applicable; they are not equivalent to per-identity growth above the baseline. Metadata snapshots are not atomic and the report package can grow while closeout proceeds.

The portable frame export had **already completed before this snapshot**. Its [official receipt](frame-export-queue.json), job `20260927T201306381734Z-651d8291`, reports `succeeded`, integer exit 0, from **20:13:06.615033 to 20:13:14.102707 UTC**. That finish precedes the snapshot start by 44.067 seconds. The [export index](frames/index.json) was created at 20:13:10.332251 UTC; all **128 exported original PNGs, totaling 7,991,942 bytes**, existed by 20:13:10.332252 UTC. A focused reconciliation verified every indexed PNG's hash and byte count. The export remained below its 128,000,000-byte cap.

Focused metadata inspection showed the then-existing `report.html`, `data.json` and `provenance.json` last written at approximately 20:13:13 UTC, before the scan. Those outputs and the frames reside inside the scanned campaign root. **Do not add the 7.992 MB export again to the 459.371 MB additional-growth measurement.** The snapshot already covers their location and followed their completed creation. The report artifacts were subsequently rebuilt at 20:19:51 UTC; the hashes and exact timestamps in the correction record identify those later versions, not the versions measured by the original snapshot. Earlier report-version hashes were not preserved. The snapshot is a non-atomic metadata measurement, not a final package freeze; later report, note and closeout revisions are outside it.

**Correction:** the original closeout incorrectly described this measurement as pre-export and the export as pending. Reconciliation with the official receipt and file timestamps corrected that interpretation without changing any recorded sample, capacity value, root count or hash-verification result. `storage-closeout.json` retains additive correction metadata, the superseded description, its original JSON hash, the completed export/index bindings and file-timestamp evidence. No new capacity census was performed for this correction.

## Retention and scope limits

Read-only Git checks found **no tracked deletion against HEAD, no staged deletion and no missing tracked path** anywhere in the checkout. All **624 frozen `RCI001-wsl-010d` source files**, totaling 6,361,616 bytes, remained present and matched their snapshot SHA-256 values. Exact check commands, snapshot binding and results are retained in the JSON. This is a tracked-deletion/source-identity check; ignored or untracked historical bulk was not fully rescanned or content-rehashed, so it is not a new historical integrity qualification. No historical evidence was deleted, compacted or moved for this closeout.

The monitor counts native campaign evidence, runtime workspaces, compact/report records, shared queue logs, selected Codex session/database metadata and all durable WSL session10 backing. It deduplicates hardlinks by file identity, counts separate copies separately, and sums only positive identity growth from the initial baseline; shrinkage/deletion elsewhere never subsidizes new evidence. Shared service growth is included without asserting it all belongs to this campaign. The WSL virtual-disk allocation is reflected by native free-space changes rather than added twice to logical totals. Other system activity can change free space independently, including the observed increase between slots 5 and 6; this report does not attribute that increase to a campaign deletion.

The temporal peak is the **maximum sampled value and a lower bound on the true between-sample peak**, not a kernel quota or exact allocated-cluster measurement. Later closeout/report/export writes are outside the completed attempt intervals. Storage coverage and reserve sufficiency do not establish scientific validity; the four invalid dispositions remain invalid for their separately recorded reasons.
