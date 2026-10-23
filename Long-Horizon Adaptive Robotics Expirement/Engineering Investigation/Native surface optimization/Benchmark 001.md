# Static exporter benchmark 001

Official job `20260923T084415083917Z-00143ee6` succeeded with exit 0, 2026-09-23 08:44:15.533103–08:44:18.121406 UTC. The [official receipt](../../Evidence/queue-receipts/20260923T084415083917Z-00143ee6.json) and [complete result](../../Evidence/derived/native-surface-benchmark-001/benchmark.json) retain authority, exact sources, every measurement, and output identities.

| Operation | Original wall time, ms | Proposed wall time, ms |
| --- | ---: | ---: |
| Warm class export, median of 16 calls | 25.02025 | 9.7624 |
| Warm rich capture, median of 16 calls | 27.98365 | 12.7093 |
| First memo-cold class export | 25.2934 | 25.0557 |
| First memo-cold rich capture | 26.2229 | 25.8089 |

All original/proposed output dictionaries matched exactly, and native state and source inventories remained unchanged. Eight pairs of warm calls alternated implementation order. The fixture was one n10 native model initialized with `mj_forward`; no `mj_step`, Cell, sensor, planner, policy or candidate ran. First-call measurements clear the proposed memo but use an already initialized evaluator index cache, so they do not represent fresh-process startup.

Root applied the exact guarded exporter patch at 08:45:14.343321 UTC; [integration.json](integration.json) records the original/staged hashes and patch identity. Static warm-operation cost improved in this benchmark. Later construction 002 passed 28/28 physical trials and 24/28 timing checks, with maximum lag 0.0728303 s and 12 bad RTF windows in the four n10 B point-1/point-5 trials across both destinations. **Recovery qualification remains unestablished.** Earlier construction timing failures remain part of the evidence; this benchmark does not assign the remaining bottleneck.

Root subsequently verified the full Runtime suite passed all 436 tests in 40.855 s under job `20260923T084539361298Z-0e0c1c2e`; 29 fixture checks also passed in 0.315 s. The 12 staged exporter checks and 12 applied hold regressions are retained in [validation.json](validation.json). Construction 002's [official receipt](../../Evidence/queue-receipts/20260923T085627326649Z-366dbd1a.json) ended 09:07:26.321833 UTC; numerical construction findings here come from root's completed small-summary review, with no physical-trace processing in this documentation update.

Result SHA-256: `685805242377ae256ffec35ead98b654f49930a27800600faa9bf98585abe797`.

Receipt SHA-256: `07fbb4f845c5846b7e1ddc1f8828b1cac9f56f0ca5cc3aa19ed5c6457286dc5e`.
