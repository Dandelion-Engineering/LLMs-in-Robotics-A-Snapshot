# Dense containment optimization — applied

Root applied the exact guarded assessor at 2026-09-23 10:12:32.2786281 UTC; the [integration record](Dense%20containment%20optimization/integration.json) retains the original and applied hashes. Eight staged equivalence checks passed before application; 10 existing assessor checks passed afterwards. The derivation coordinator is now active with those sources held. No actual assessment speedup or recovery qualification is claimed.

The original assessor repeated `all(valid_box(b) for b in corridors)` for **every interval × geometry box** before exact subtraction. `valid_box` checks both three-element arrays, every scalar's finite type/value and strict bound ordering. It then copies/subtracts against corridors in their original order. Even a first-cover containment success paid the whole corridor-validation cost. This is source evidence of avoidable repeated work, not a measured runtime diagnosis.

Original reviewed source: `Batch 01/Restart Qualification Tools/assess_validation.py`, SHA-256 `300b32a136790802ce57781a7ee8b12e2cfe7923b8702d0d998e3c4f3e783192`, functions `box_union_contains` and `dense_assessment`. Applied assessor SHA-256 is `cb1ddce3ef6a919c1df1d30cc63db55fd8fe63c2dc4a9feaafbebdc7307dd91e`. Root changed only the assessor for this integration; Runtime, Recovery Qualification, rules and original evidence remain unchanged. Historical proposal files and manifest retain their original status.

## Completed metadata scale

Only the completed construction-003 compact JSON metadata and retained official receipts were read; no dense trace or cover-file arrays were streamed. Parking1 job `20260923T094229717164Z-170731a4` succeeded/0 at 09:42:50.881419 UTC; parking2 `20260923T094351661484Z-fef0b04a` succeeded/0 at 09:44:12.440442 UTC. Both metadata files report every selected construction trial processed. Their embedded queue snapshots describe launch, while the separate official receipts establish completion.

| Destination/location | Input interval boxes | Covers at 10 / 20 / 50 mm bins | Repeated corridor validations at 50 mm |
| --- | ---: | ---: | ---: |
| parking1 A1 | 132,054 | 2,906 / 1,481 / 587 | 77,515,698 |
| parking1 B10 | 79,196 | 2,252 / 1,163 / 463 | 36,667,748 |
| parking1 B2 | 36,322 | 2,755 / 1,485 / 610 | 22,156,420 |
| parking2 A1 | 116,974 | 3,295 / 1,671 / 670 | 78,372,580 |
| parking2 B10 | 74,802 | 2,575 / 1,362 / 554 | 41,440,308 |
| parking2 B2 | 33,228 | 2,932 / 1,540 / 629 | 20,900,412 |

The last column is `input_box_count × cover_box_count`: the work that would occur if these completed construction boxes were assessed against their own location's indicated compact cover. Across all six groups it is 277,053,166 checks at 50 mm and 1,337,634,402 at 10 mm, before subtraction. This is neither the independent validation workload nor a selection of bin, padding, location or cell; B2 remains separately unsupported. Future validation counts and actual time savings remain unmeasured. Sampled other-body overlap checks are a separate remaining loop and are unchanged by this proposal.

## Narrow applied change

[prepared_corridor_containment.py](prepared_corridor_containment.py) retains the standalone historical proposal; root integrated that class directly into the assessor, keeping the existing public `box_union_contains` as the original reference. Each `dense_assessment` constructs one private prepared corridor snapshot and replaces only the per-box call with that instance. It supplies the existing `valid_box` and `require`, with the same output dictionary, error text, 20,000-piece cap and no epsilon. No rule fields, source bindings, clock/interval logic, failure counters or contact predicates changed.

The private corridor snapshot is validated lazily on the first valid query, preserving per-record malformed-input handling and the no-consumed-record case. Each incoming box still receives its original validation. The cache exists only within one assessment over that fixed private rule value; it is not a mutable-rule/global cache and is not an independent evidence assertion.

For finite exactly Float64-representable coordinates, an array comparison selects only corridors with positive-volume intersection with the **original input box**, preserving corridor order. A removed corridor cannot intersect any remaining piece because every remaining piece is a subset of the original. Touching-only corridors are exact no-ops. Larger integers fall back to scalar processing, avoiding Float64 rounding. Original Python coordinate values remain in subtraction and reports.

At each retained corridor's original position, a direct containment check can finish with the original pass result; otherwise the original subtraction body and resource cap execute unchanged. There is deliberately **no upfront “any later cover contains the box” return**: earlier covers can exceed the existing resource cap before that later cover is reached, so such a shortcut could incorrectly turn unknown into pass. Skipping disjoint covers cannot hide that cap because preceding effective covers retain their original cap checks.

## Completed synthetic verification

[test_prepared_corridor_containment.py](test_prepared_corridor_containment.py) passed **8 tests in 2.331 s** against the staged class under [official job `20260923T101130338583Z-5474a53a`](../Evidence/queue-receipts/20260923T101130338583Z-5474a53a.json), succeeded/0 at 10:11:33.379100 UTC. It extracts numerical and dense-assessment reference functions from the exact archived assessor, with no Runtime or evidence imports. The candidate is the exact staged class before application, or the exact installed class afterwards; class and dense-call AST checks preserve that binding. The checks compare complete result dictionaries or exception type/message for direct containment, touching, split-cover union, a one-ULP gap, malformed/nonfinite values, output isolation, signed zero, unsafe-large-integer fallback, ordered uncovered pieces, deterministic mixed overlaps, and a 27-slab-per-axis case that reaches the original resource cap before a late enclosing cover. Full dense-record comparisons also preserve empty-trace, malformed-corridor and partial-record accounting.

After application, the existing assessor suite passed **10 tests in 4.829 s** under [official job `20260923T101232373935Z-d5ed862b`](../Evidence/queue-receipts/20260923T101232373935Z-d5ed862b.json), succeeded/0 at 10:12:37.930432 UTC. These actual counts replace the earlier expectation of 12 existing tests. No separate post-application rerun of the eight focused checks is claimed. [The integration handoff](Dense%20containment%20optimization/README.md) records exact hashes and the available installed-source regression strategy. The test results establish these synthetic comparisons, not measured assessment speedup.

Retained focused-test entry (do not rerun while the active coordinator holds these sources):

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/test_prepared_corridor_containment.py'
```

A later benchmark should use the same fixed valid synthetic corridor/query inventory for original and prepared implementations, retain first-use and repeated-use wall times, and assert exact output equality. Actual validation evidence processing remains a separate queued step. This proposal changes no scientific threshold, geometry sampling frequency, corridor coordinates, union ordering or qualification requirement.
