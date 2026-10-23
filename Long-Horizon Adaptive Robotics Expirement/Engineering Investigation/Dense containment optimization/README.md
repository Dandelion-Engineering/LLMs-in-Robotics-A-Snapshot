# Guarded assessor integration — applied

Root applied the exact guarded assessor at 2026-09-23 10:12:32.2786281 UTC; [integration.json](integration.json) records the identities. Eight focused staged checks passed in 2.331 s before application; the existing assessor suite passed **10 tests in 4.829 s** afterwards. Both official receipts report succeeded/0. No Runtime, physics or rule changes accompanied this integration. The five-job construction derivation coordinator is now active with the applied assessor and its dependencies held unchanged; no coordinator completion is claimed here.

| Artifact | SHA-256 |
| --- | --- |
| Archived original assessor | `300b32a136790802ce57781a7ee8b12e2cfe7923b8702d0d998e3c4f3e783192` |
| Applied complete assessor | `cb1ddce3ef6a919c1df1d30cc63db55fd8fe63c2dc4a9feaafbebdc7307dd91e` |
| `dense-containment.patch` | `13d19b6e53a8d343070020f74edec5ef5c8096acb70eb1f3cf59f5a51d8e8ef8` |

The historical [manifest](manifest.json) retains its original unapplied/test-deferred status, absolute target/archive paths and standalone reviewed helper identity. The separate integration record establishes application; do not rewrite the historical manifest. The patch adds NumPy, inserts the class directly into the assessor, creates one private instance at the start of `dense_assessment`, and redirects its per-box containment call. The public `box_union_contains` remains byte-for-byte unchanged. There is no new runtime import from Engineering Investigation.

The source-only reviewer found no concrete semantic issue. This is review evidence, not an execution result. Preserve the original corridor order, exact numeric fallback, uncovered-piece ordering and original 20,000-piece unknown behavior.

The pre-application focused entry completed under [official job `20260923T101130338583Z-5474a53a`](../../Evidence/queue-receipts/20260923T101130338583Z-5474a53a.json), ending 10:11:33.379100 UTC:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/test_prepared_corridor_containment.py'
```

The eight checks use the archived exact original, not a guard that requires the installed file to remain old forever. They require the installed assessor to equal either the exact original or exact proposed hash. Before application, they load the exact staged class and dense function by AST; afterwards they load those definitions from the exact installed file. They also verify class AST equality with the reviewed helper, unchanged original public subtraction, and exactly the two intended dense-function edits. No full assessor or Runtime import occurs in these focused checks.

After official test success, root checked the exact original/proposed hashes and applied the verified proposed bytes. Keep the archived reference and patch unchanged; do not rerun application against the already modified target or regenerate the proposal around changed sources.

The post-application `Batch 01/Restart Qualification Tools/test_assess_validation.py` suite completed under [official job `20260923T101232373935Z-d5ed862b`](../../Evidence/queue-receipts/20260923T101232373935Z-d5ed862b.json), ending 10:12:37.930432 UTC: root reports **10 passed in 4.829 s**, correcting the earlier expectation of 12. The focused test entry remains capable of checking the installed class, but no separate post-application rerun of those eight checks is claimed. No additional Runtime suite ran for this assessor-only edit. Integration and the existing assessor checks finished before the new extraction/compact coordinator began; the final assessor remains held throughout those jobs.

See [the cost and semantics proposal](../Dense%20containment%20optimization%20proposal.md) for the completed-metadata workload estimate, exact unknown-preservation argument and remaining sampled-other-body loop. Neither review nor passing synthetic checks grants a speedup, physical support or recovery qualification.
