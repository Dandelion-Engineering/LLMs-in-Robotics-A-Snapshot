# Sustainable storage implementation 001

**Implementation and preservation validation are complete. Exact retirement passed, and measured future recording meets the 30/40 GB campaign controls. Large scientific admission remains closed by existing capacity and release-specific qualification gates.** This additive record follows Randy's September 26, 17:43 PDT direction in the active Audit Storage chat. The [original audit](../Storage%20Audit%202026-09-26/README.md) and [accepted retention proposal](../Storage%20Audit%202026-09-26/Sustainable%20Retention.md) remain historical documents; they are not rewritten as implementation claims.

The adopted boundary preserves every event/motion/resource stream, scoring witness, model/file record, manifest, result, restart record, frozen source and current viewer. It deliberately gives up arbitrary pixel/depth reassessment outside the retained visual selection. Deleted pixels cannot be recreated exactly from detections, reconstructed camera views, or reruns.

The [completion index](records/session-completion-001.json) binds the final accepted checks and explicit scientific-admission limits.

## Current evidence and gates

- [Source baseline](records/source-baseline.json) binds the exact audit/provenance files and original implementation-start revision.
- [Preflight census](records/preflight-001/summary.json) measured 433,086,253,656 logical project bytes and 204,416,208,896 free C: bytes at its start. It found no traversal errors or reparse points. The census is a timed snapshot, including small concurrent implementation changes; it is not a physical-allocation census.
- [Audit reconciliation](records/audit-comparison-001.json) confirms exact r4 counts and bytes: 2,511,093 RGB/depth artifacts, 233,212,545,122 bytes. All r4 files together and event/motion totals also match the audit exactly.
- [Aggregate reanalysis](records/analysis-pre-equivalence.json) reproduces the existing Analysis005 bytes exactly with its frozen settings and source bindings.
- [Browser baseline](records/browser-pre-001.json) records current Explorer and Investigation007 workflow checks.
- [Successful retained-only reader validation](records/staged-policy-001/validation.json), with its [official queue receipt](records/queue-20260927T011020829402Z-faeae531.json), reproduces all 12 historical trace packages exactly. The unchanged Explorer validator passed; all 264 source-bound dispositions, all13 current/saved trace dependency manifests and all 899 windows remained valid, with zero unexpected attempts to access proposed-deletion artifacts.
- [Numerical source reconciliation](dependencies/source-reconciliation-001.json) matches all263 terminal event-stream hashes to their previous diagnostic bindings. The administrative partial keeps its separately recorded extraction identity. This supports source preservation; it is not a claim that every scientific diagnostic was recomputed by the reader gate.
- [Full dry-run](records/r4-policy-001-pre-001-validation.json) passed all215,419 retained hashes, all2,295,674 proposed-deletion identities and all 3,323 protected nonframe metadata identities. The immutable [pre-deletion completion record](records/pre-deletion-completion-001.json) binds31 supporting records, the exact partition and the deletion digest. [Writer inspection](records/no-affected-writers-002.json) found no affected original-evidence writer. All60 future qualification image inputs were separately [verified as retained with matching hashes](records/future-image-retention-002.json).

Retirement requires the complete retained/deletion partition, every retained artifact SHA-256, current dependencies and diagnostic windows, the unchanged readers under a retained-only policy, and a hash-bound pre-deletion completion record. It does not require another permission question: Randy explicitly authorized the exact manifest once these gates pass.

`retention.py` restricts deletion to the exact declared r4 `attempts/<run>/evidence/frames/<six-digit>.png` and `-depth.npz` leaves. It checks resolved containment, rejects path aliases/reparse points, authenticates supporting records and manifest digests, and verifies each source size/mtime before unlinking. It never recursively removes directories. Fsynced write-ahead batch records identify exact immutable-manifest ordinals; completed receipts add the removed-path digest. Any mismatch stops execution. An interrupted batch needs explicit receipt/filesystem reconciliation; a second invocation refuses to overwrite existing receipts.

Read-only dry-run and post-retirement validation use eight workers in bounded batches of256 while retaining every original path, identity and SHA check. Unlink remains serial. [Twelve fixture tests](records/retention-tests-002.json) include same-size/same-mtime corruption, tampered manifests, protected changes and exact pre/post accounting across the batch boundary. The [original source snapshot](records/retention-source-001.py) preserves the implementation used for the initial census/partition; its deletion procedure is unchanged in the current version.

Millions of exact paths are versioned as deterministic gzip JSONL. `gzip.open(path, 'rt', encoding='utf-8')` streams their ordinary JSON objects. This is compact manifest storage, not compression or migration of original evidence.

The first retirement job lost its worker after446 completed batches (892,000 files) and one additional issued intent. The supported queue `doctor --repair` marked it [interrupted](records/queue-20260927T021811180808Z-32339c6c-interrupted.json); its [partial log](records/interrupted-retirement-001.log) and every original receipt are preserved. The cause is not established. No agent issued a process-kill or signal probe. `records/resume_retirement.py` refuses a blind retry: it requires a new successful queued reconciliation of completed-prefix absence, the exact contiguous absent prefix within the unfinished intent, every later candidate's original identity, every retained SHA and protected nonframe metadata. Any continuation uses a new gate and separate receipts with original global manifest ordinals. Observed interrupted-batch absences remain distinct from old completed receipts and new successful unlinks.

The [successful interruption reconciliation](dependencies/interruption-reconciliation-001.json) found exactly 892,000 completed-receipt absences (83,044,499,760 bytes) and 296 contiguous absences within the outstanding intent (31,936,436 bytes). Every later candidate remained present with its original identity; all 215,419 retained hashes and all 3,323 protected nonframe metadata identities passed. The verified remainder begins at global ordinal 892296 and contains 1,403,378 files / 130,061,991,305 bytes. The [new continuation gate](records/continuation-gate-001.json) binds this proof and its [successful queue receipt](records/queue-20260927T023446312868Z-ad2f82c7.json). [Seven temporary-fixture tests](records/resume-retirement-tests-001.json) cover continuation accounting, strict leaf/identity checks, partial failure, immutable original receipts and blind-retry refusal.

The continuation completed successfully at 03:01:35Z on September27. Exact accounting separates892,000 files from old completed receipts,296 independently observed absences within the interrupted intent, and1,403,378 new successful unlinks. The [chain reconciliation](dependencies/receipt-reconciliation-001.json) authenticates446 original completed batches and702 continuation batches, covering every approved manifest ordinal exactly once. The interrupted record remains interrupted; it is not relabeled successful.

The original worker did not persist its starting free-space observation. The completion therefore reports the wider **preflight census to retirement completion** interval: C: free space rose from204,416,208,896 to425,213,227,008 bytes, an observed increase of220,797,018,112 bytes. The exact retired logical amount is213,138,427,501 bytes. Volume observations include filesystem allocation/metadata effects and other host/prototype writes, so their difference is not attributed solely to deletion.

The [complete post-retirement filesystem validation](records/r4-policy-001-post-001-validation.json), with its [successful official receipt](records/queue-20260927T030244562569Z-f35ab10f.json), rechecked every retained SHA, every approved absence and all 3,323 protected nonframe identities with zero errors.

The [post-retirement browser check](records/browser-post-001.json) verified original recorded RGB, model/checkpoint inspection, previous-call navigation, all 12 available trace bundles and the264/253/11 paired-analysis denominator. The [availability example](records/availability-example-post-001.json) explicitly identifies an exact retired depth archive as `retired_by_policy_unavailable`. A [post-retirement numerical replay](historical/post-image-retirement-equivalence.json) reproduced the complete original A2 C14 diagnostic and qualified-continuity outputs, apart from a documented creation timestamp; this is one representative replay, not an all-run recomputation.

## Exact r4 visual selection

The [immutable partition](records/r4-policy-001-partition.json) reconciles every one of the 2,511,093 original artifacts. Decimal GB means 1,000,000,000 bytes.

| Selection | Artifact files | Exact logical bytes |
|---|---:|---:|
| Original r4 RGB/depth | 2,511,093 | 233,212,545,122 |
| Retained | 215,419 | 20,074,117,621 |
| Retired | 2,295,674 | 213,138,427,501 |
| Current viewer union, within retained | 33,332 | 3,060,837,178 |
| Additional retained beyond viewers | 182,087 | 17,013,280,443 |

The retained set contains 107,709 complete RGB/depth capture pairs plus one preserved unmatched RGB file from the administratively interrupted C24 replicate2 A1 persistent run. That unmatched leaf is historical, not a new loss. Retention contains 107,710 PNG and 107,709 NPZ files; artifact counts must not be presented as paired-frame counts.

[Detailed statistics](dependencies/retained-statistics-001.json) give exact unions and overlaps. The broader consumer/reference union is 39,171 files (3,563,668,838 bytes), including historical recovery inventory and audit literal references. Those references are deliberately preserved even where a current viewer does not need them. The 179,380-file diagnostic-window union and 387 orphan/unmapped files overlap other groups; their counts must not be added to the viewer union as though disjoint.

[Dependency decisions](dependencies/extraction-001/decisions.json), [899 explicit windows](dependencies/extraction-001/windows.json), and [window completeness checks](dependencies/window-completeness-001.json) define the selection. Rules retain final20 seconds of valid/infrastructure failures; first/last false-completion assertions per distinct reason with five-second context; restart context from five seconds before to fifteen after; first/last physical ambiguity/failure and runtime-anomaly context; the ten largest recorded run contact peaks; and both members of the two baseline/A3 discordant pairs at quartile windows and the final30 seconds. Repeated assertions with the same reason do not silently expand into full camera retention.

The fixed12 representative traces remain the predeclared presentation selection. Additional outcome-selected failure/contact/restart windows are diagnostic evidence, not a representative sample. All original event/numerical decision evidence remains available across the entire batch.

For a specific historical path, use the additive policy reader from the project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Storage Retention Implementation 001/retention.py' availability --name r4-policy-001 --path '<original repository-relative RGB/depth path>'
```

Its result is `retired_by_policy_unavailable` only when the exact manifest has a matching completed retirement receipt. Before completion, unexplained absence remains `missing_without_completed_retirement_receipt`; an absent retained member is `corrupted_or_missing`. This policy overlay preserves the old manifest's historical assertions without pretending retired files still exist. Original pixels outside the retained selection cannot be recovered from the overlay.

Every retained PNG/NPZ has a new SHA-256, checked against historical artifact hashes where present. The retained manifest digest is `55569a0375eacc9c71dc39e9e3b006392c657e7619b21f3f196c5a91f67bc09d`; the executed deletion-manifest digest is `6fa55705fec3d6f0553a65dcd8a4b077db2ca9c6a6b329a9199e122133e84ff8`. The [successful continuation receipt](records/queue-20260927T025045669593Z-dd2397c9.json), [retirement completion](records/r4-policy-001-deletion-complete.json), and [independent exact receipt-chain reconciliation](dependencies/receipt-reconciliation-001.json) establish execution.

## Future recording and historical prototype

- [Future recorder](future/README.md): separately versioned full-precision object/numerical storage, bounded paired imagery, compatibility readers, measured qualification and fail-closed admission. Frozen r4 is untouched.
- [Historical codec](historical/Results.md): representative exact-byte roundtrip measurements and recommendation. All original r4 event/motion files remain in place. Full historical migration requires a later explicit decision.

The target is 30 GB permanent per comparable campaign, with a 40 GB admission ceiling including declared headroom, a 150 GB project evidence ceiling after normalization and a 100 GB C: reserve. Measured qualification and current capacity determine admission; budgets alone never establish readiness. No Robot-Codex integration task or new scored campaign is started by this implementation.

The completed [qualification007](future/qualification.json) projects **27,964,986,654 bytes permanent and 36,956,233,318 bytes with headroom**, meeting the 30/40 GB controls. It uses the maximum measured real replay-window core rate (91,096 bytes per task-second), real encoded image sizes, the full 156,600-task-second/264-run plan, fixed evidence allowances, 25% uncertainty and 2 GB temporary space. Twenty tests, ten real replay windows, two whole-chain continuity comparisons, a1,200-second synthetic fixture and paired native-supervisor fixtures passed. These are measured bounded qualification results, not a guarantee for unseen workloads. Whole-task/inference/restart timing and frozen future release binding remain integration gates.

The first full generation preserved semantics but projected79.57 GB permanent and101.46 GB with headroom. That failed-budget result remains under `future/history/qualification-003/`. Subsequent optimization and the canceled pre-durability generation also remain visible. Current format3 finalization verifies and durably publishes the compressed database and manifest before removing its own temporary working database. All future qualification source images belong to the immutable retained set.

## Final reconciliation and remaining capacity

[Final reconciliation](records/final-reconciliation-001.json) authenticates all successful queue receipts, exact retirement and census accounting, protected nonframe totals, the original/pre/post identical Analysis005 bytes and all 17 unchanged audit sources. [Staged/post comparison](dependencies/policy-comparison-001.json) verifies all 17 semantic/provenance fields, including all 12 original packages, all 899 windows, all 264 dispositions and the unchanged Explorer. Browser checks and the representative original diagnostic/qualified-continuity replay remain separately scoped evidence.

The postflight snapshot measured 220,838,315,820 logical project bytes (489,586 files),175,841,527,628 Evidence bytes,219,064,795,788 bytes for the entire experiment and424,121,774,080 free C: bytes. Evidence is 25,841,527,628 bytes above 150 GB; the conservative whole-experiment admission scope is 69,064,795,788 bytes above it before a new campaign. Whole-experiment counts include runtime/model hardlinks, code, presentations and local prototypes. The original audit's 25,535,928,636 repeated model-hardlink bytes remain a separate logical-versus-physical caveat.

The entire Evidence reduction equals the exact approved retirement. Other project storage grew 890,489,665 bytes during implementation. The census is a timed snapshot before final handoff metadata and Git publication; the commit adds repository objects afterward. Current admission must use fresh capacity and a qualification bound to its actual future workload.

The [actual admission result](future/admission-result.json) and [CLI check](future/admission-check.json) retain the fail-closed outcome. The 100 GB free reserve is available, but existing capacity and missing whole-task/inference/restart timing plus a frozen new release prevent a large scientific campaign. These components are ready to support bounded integration/setup in the next session. Randy explicitly deferred the new 19:36 PDT Robot-Codex message to that session; no part of it was started here.
