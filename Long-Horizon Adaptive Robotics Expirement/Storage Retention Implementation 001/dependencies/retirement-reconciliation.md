# Interrupted retirement and receipt-chain reconciliation

The authorized image-retirement policy and original deletion manifest did not change. The initial retirement queue job lost its worker and was officially marked `interrupted`; its partial output was not accepted as a successful completed retirement. Original receipts, the outstanding intent, and the interrupted queue record remain intact.

The [interrupted queue receipt](../records/queue-20260927T021811180808Z-32339c6c-interrupted.json) records job `20260927T021811180808Z-32339c6c` and the queue's worker-loss error. There were 446 complete intent/complete pairs and one outstanding intent beginning at original manifest ordinal 892,000. No missing or extra receipt files were found. No cause beyond the recorded worker loss is inferred here.

## Independent interruption proof

The additive `--interrupted-receipt` mode of `reconcile_retirement_receipts.py` differs from its ordinary receipt-only mode: it performs a queued filesystem reconciliation and hashes every retained camera artifact using eight workers. It preserves all evidence and original receipts. The original job's interrupted status is failure context; the new check must separately succeed before its result is used.

Official job `20260927T023446312868Z-ad2f82c7` succeeded with exit 0. The [interruption proof](interruption-reconciliation-001.json) verifies:

- Every completed original batch's original-manifest ordinals, exact ordered-path SHA256, count, and logical bytes; all of those paths were absent.
- Within the issued outstanding intent, exactly 296 further absent paths formed a contiguous prefix. These are recorded as **observed absent within the interrupted intent**, without inventing a historical completion receipt.
- Every following deletion-manifest path was present with its original size and modification time. The exact remaining suffix began at ordinal 892,296.
- All 215,419 retained files had their original SHA256 values, and all 3,323 protected non-frame metadata identities matched.
- The manifests and original receipt set remained unchanged throughout inspection.

## Successful continuation and final accounting

The root continuation program used a fresh gate and separate receipt directory. It logged only actual new unlinks, retaining original global manifest ordinals. Official continuation job `20260927T025045669593Z-dd2397c9` succeeded with exit 0; see its [receipt](../records/queue-20260927T025045669593Z-dd2397c9.json) and the [combined completion record](../records/r4-policy-001-deletion-complete.json).

Independent final job `20260927T030241674659Z-a7c4cc13` also succeeded with exit 0. Its [receipt](../records/queue-20260927T030241674659Z-a7c4cc13.json) authenticates the [exact receipt-chain reconciliation](receipt-reconciliation-001.json):

| Disjoint part of original deletion manifest | Files | Logical bytes |
| --- | ---: | ---: |
| Original completed batches | 892,000 | 83,044,499,760 |
| Independently observed absences within interrupted intent | 296 | 31,936,436 |
| Newly completed continuation unlinks | 1,403,378 | 130,061,991,305 |
| **Total** | **2,295,674** | **213,138,427,501** |

The final checker streams the authenticated original manifest and verifies every original completed receipt, the original outstanding intent, and all 702 new continuation batches. It checks 893 original receipt files and 1,404 continuation receipt files, exact counts/bytes/path digests, contiguous non-overlapping ranges, chronology, immutable source identities, successful proof/continuation queue receipts, and final completion totals. Every original manifest ordinal is accounted for exactly once. Original incomplete receipts are neither overwritten nor relabeled successful. This final checker reads manifests and receipts; the separate post-retirement filesystem check establishes actual absence and retained-file integrity again.

The original retirement process did not persist its initial free-space measurement before worker loss. The completion record therefore explicitly binds the earlier preflight census disk baseline and reports its wider observation interval, plus a separate continuation-only observation. Logical retired bytes are exact. Disk free-space deltas also include allocation metadata and unrelated host activity; they are not substituted for manifest totals.

## Reusable checks

`reconcile_retirement_receipts.py --retirement-receipt <receipt> --partition <partition> --output <fresh-json>` handles an uninterrupted successful retirement. Its `--interrupted-receipt` alternative establishes the read-only interrupted-prefix proof described above. Both modes require queue ownership; the interrupted mode opens surviving evidence solely for metadata/hash checks.

`reconcile_retirement_chain.py --continuation-receipt <receipt> --partition <partition> --output <fresh-json>` handles the authenticated interrupted-proof/continuation chain and requires queue ownership. It never opens camera files.

`compare_policy_records.py --staged <validation> --staged-receipt <receipt> --post <validation> --post-receipt <receipt> --partition <partition> --output <fresh-json>` checks compact records after both jobs officially succeed. It authenticates their source jobs and exact required inputs, requires the post job to use the final retained manifest, and compares every semantic/provenance field. Only execution phase/job/time, the documented retained-input file identity, and the phase-specific guard probe may differ. Camera files and scientific streams are not read by this compact comparison.

Six synthetic receipt/interruption/comparison tests and four synthetic chain tests pass. They exercise tampered path hashes, counts, bytes and ordinals; missing/extra/failure receipts; noncontiguous interrupted absences; reappearing completed-prefix files; changed original receipts; and gaps in the continuation chain. The fixtures use temporary synthetic records and never mutate original evidence.

## Completed staged/post reader comparison

Post-reader job `20260927T030245197537Z-335c5ed4` officially succeeded with exit 0 at 2026-09-27 03:35:55 UTC; its [saved receipt](../records/queue-20260927T030245197537Z-335c5ed4.json) authenticates the [post validation](../records/post-policy-001/validation.json). The post job used the final retained manifest, not merely the earlier required-input list.

The independently authenticated [compact comparison](policy-comparison-001.json) passes. All seventeen remaining semantic/provenance fields match the staged record exactly after excluding only the documented execution phase/job/time, retained-input file identity, and phase-specific guard probe. This includes all twelve unchanged selected-reader reconstructions and complete package comparisons; all twelve current trace manifest identities plus the saved validation004 dependencies; all 899 diagnostic-window checks; all 264 source-bound dispositions and unchanged analysis binding; the Explorer's four episodes, 1,273 payloads, and 5,070 frame references; all reader/comparator/presentation source identities; and zero unexpected denied reads. The current package manifest remains 27,784 bytes with SHA256 `8999e9170a0b8fa1154b06dfd704f84a2d0ad233ef0ae7837e754459ade93ad7`.

This establishes equality of the current readers and their provenance under the applied retention policy. It does not turn the outcome-selected visual windows into a representative sample or reconstruct retired pixels. Full post-retirement filesystem checks, independent original-analysis recomputation, browser QA, and the final storage census remain separately recorded by the root implementation workflow.
