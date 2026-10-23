# Prospective representation after construction 001

**Recommendation:** after timing repair and repeated construction, use separate, explicitly local **A1** and **B10** cells for parking1. Keep B2 outside that proposed scope. Use a union of the recorded interval/per-geometry boxes, followed by exact duplicate/contained-box pruning, as the initial geometry basis. Do not use one whole-arm box or per-geometry phase hulls. This note chooses no numerical cell limits, padding, rule, qualification or validation outcome.

The completed screen physically passed all 28 construction trajectories, but 14 failed the unchanged host-timing check. Twelve of the 14 timing passes are calibration-boundary worlds outside the half-open generator domain; the other two are the n3 A1 trials, one per destination. **No qualification follows.** All 12 original validation trials remain deferred and untouched. Root is repairing timing and will repeat construction; these observations diagnose representation needs, not substitute for that repeat.

Sources: [construction procedure](CONSTRUCTION.md), [completed dossier](../../Evidence/derived/recovery-construction-dossier-001/construction-dossier.json), [completed extraction](../../Evidence/derived/recovery-construction-001/extraction.json), [original successful queue receipt](../../Evidence/queue-receipts/20260923T081350223056Z-c2819dc2.json), [dossier receipt](../../Evidence/queue-receipts/20260923T082925658341Z-a63c2d10.json). Dossier SHA-256 `a63c0cea80dc29303f15cbb18888ce651e218f1493a95d6bbf07e2bf2a996df8`; extraction SHA-256 `94f71a4b4a9513ef49d340358c7000cdbed315c571dffc66b3e5e68b09fd60b1`.

## Coupled state evidence

The following are **observations**, rounded here for readability. They are not proposed acceptance bounds. The dossier retains the full precision and the same-trial joint, pose, force and source tuples. “Both” includes cut and pre-dispatch observations; those are different physical states. **The current `_route` evaluates its start bounds at the cut, not at dispatch.** The pre-dispatch measurements describe the subsequent physical transition and do not automatically become additional admissible cut states.

| Parking1 group | In-domain construction trials | Cut TCP approximately, m | Pre-dispatch TCP approximately, m | Both-state jaw, mm | Both finger force range, N | Timing passes |
|---|---:|---|---|---|---|---:|
| A1 | 4: corner A1/A5, n3 A, n6 A | (0.317267–0.317271, −0.369546–−0.369542, 0.080289–0.080295) | (0.316941–0.316945, −0.369255–−0.369251, 0.095478–0.095484) | 41.8526–41.9242 | 1.04551–1.06342 | 1/4 |
| B10 | 2: corner B1/B5 | (0.320364–0.320371, −0.087423–−0.087422, 0.080093–0.080097) | (0.320246–0.320252, −0.087383–−0.087382, 0.086878–0.086883) | 41.7709–41.9242 | 1.04000–1.16551 | 0/2 |
| B2, separate | 2: n3 B, n6 B | (0.403326, −0.369146, 0.080267) | (0.402953, −0.369056, 0.098450) | 41.9079–41.9242 | 1.02576–1.07181 | 0/2 |

“Corner A1/A5” above means declared `parking1-corner-A-1` and `parking1-corner-A-5`, not different payload IDs. A1 is the payload in both. The B equivalents carry B10.

A1 cut→dispatch rises about **15.19 mm**, B10 about **6.79 mm**, and B2 about **18.18 mm**. A cut-only TCP start box need not include those dispatch postures. Keep the cut→hold→dispatch transition as separate measured support, with its full arm/payload geometry covered by the corridor. Widening the cut start box to include dispatch would also admit additional, potentially unmeasured cut postures and is not required by the current predicate. The in-domain relative-pose rotation diameters across these two landmarks are respectively **0.0134441, 0.0133057 and 0.0180021 rad**. They describe transition observations, not cut-admission thresholds. A chosen cut reference rotation and its angular bound must use cut-state support and the unchanged trace/acos comparison.

The fixed construction layout gives only micrometre-scale variation in A1/B10 cut TCP coordinates. For example, the in-domain A1 cut x span is **4.059 µm**; B10 cut y span is **0.647 µm**. This does not measure independent-layout variation. B10 and B2 differ by approximately **83 mm in x and 282 mm in y**; pooling them into one marginal box would also join substantially different joint configurations and unmeasured coordinate combinations. The smallest scope compatible with the existing one-cell-per-template mapping is therefore A1-local and B10-local, with B2 states reported outside/unknown. Preserve the original n3/n6 B validation rows even if that prospective rule excludes them.

Retain the exact coupled tuples as the measured core, with cut-admission and transition-support roles kept distinct. Rectangular cut-admission projections remain an **explicit empirical Cartesian-product assumption**, not a measured product domain; do not pool pre-dispatch coordinates into them merely to cover the later transition. Do not add a numerical epsilon to satisfy strict-box validation. The combined-landmark relative-position spans shown by the dossier are nonzero (smallest axes **28.41 µm A1**, **62.46 µm B10**), but these transition spans establish neither cut-box widths nor transfer tolerances. Any additional cut-admission width must be declared before untouched validation and justified as a proposed transfer allowance. Raw layout differences between two draws can exceed 3 mm; perception, IK and link motion do not supply an automatic rigid 3 mm whole-arm bound.

## Quantified corridor obstruction from time pooling

I read only the completed dossier and derived metadata for three representative parking1 trials. There are **26 recorded robot/payload geometries** in each. The table compares their retained **phase-wise dense outer boxes** against the same trial's actual *other movable cut bodies*, using the existing overlap condition (strict overlap greater than 1 µm on every axis).

| Representative | Per-geometry recovery-phase box/object overlaps | Other-body blockers from one whole-arm recovery hull | Absence / settling per-geometry overlaps |
|---|---:|---:|---:|
| [A1 center, n10](../../Evidence/derived/recovery-construction-001/parking1-corner-A-5/trial.json) | **57** | **7** | 0 / 0 |
| [B10 center, n10](../../Evidence/derived/recovery-construction-001/parking1-corner-B-5/trial.json) | **0** | **2** | 0 / 0 |
| [B2 center, n3](../../Evidence/derived/recovery-construction-001/parking1-center-n3-B/trial.json) | **8** | **3** | 0 / 0 |

A concrete A1 witness is left-finger geom **84**, whose recovery-phase box spans x `[0.301472, 0.400367]`, y `[−0.417150, 0.264605]`, z `[0.009545, 0.510795]` m. Against the cut B2 box, its axis overlaps are **15.555 × 42.000 × 26.347 mm**. B2's analogous phase hull overlaps A1 by **39.120 × 42.000 × 26.620 mm**. These are real failures of the proposed *box representation*, not evidence of those physical collisions: a low z attained near parking is combined with a southern y attained earlier. Padding such hulls cannot repair that obstruction.

The three whole-arm recovery hulls include the base's z minimum **−0.07744 m** while spanning moving distal links. Even B10's per-geometry recovery phase boxes, which have no recorded cut-body blockers in this representative, become blocked when combined into one whole-arm hull. Thus “one box enclosing the robot” fails before transfer padding is considered.

Sources for the actual other-body bounds and complete state identity: [A1 measured states](../../Evidence/derived/recovery-construction-001/parking1-corner-A-5/measured-states.json), [B10 measured states](../../Evidence/derived/recovery-construction-001/parking1-corner-B-5/measured-states.json), [B2 measured states](../../Evidence/derived/recovery-construction-001/parking1-center-n3-B/measured-states.json). Their SHA-256 values are respectively `f9fbd8b9b7776e7541744225a1c5c83c8b72196d78b9d053628d32069ed64f9f`, `284c73ef11163d246bebb65382993eb22bc95185f0eb42ec67c7700e089cc68e`, `8a9dbb65037831a889b482f6d7da492566332b51168f64f7a61e2024b753b6d9`.

## Smallest next computation and cost constraint

Prepared [construction_geometry.py](construction_geometry.py), with three synthetic tests passing in 0.187 s. It has **not** been run on physical evidence by this agent. Root can queue it with the completed extraction and independent successful screen/extractor receipts. It retains all 40 declared statuses, streams only selected construction traces, exports every complete interval/per-geometry box overlapping cut→placement, and reports exact intersection, unchanged Runtime overlap, and signed AABB axis-separation witnesses. Boundary-straddling intervals remain whole.

The predeclared comparisons are **0, 1, 2, 3, 5 and 10 mm** uniform expansion; these are proposed empirical-transfer alternatives, not derived error bounds. A1, B10 and B2 unions stay separate. In-domain A1 and B10 cut/pre-dispatch tuples are reported separately from out-of-domain boundary points and timing failures. No allowance is selected automatically.

The helper exports the full boxes plus an exact union-preserving removal of duplicates and boxes wholly contained in another retained box. It reports both counts and the group union against every member's actual other-body cut scene. This exposes the Runtime cost of `corridors × other_objects`, and of repeatedly hashing a large bundle, before choosing a representation. The 50 mm spatial hash in the implementation is only an acceleration index: it changes no box coordinate or corridor.

If exact pruning leaves too many boxes, a separately declared compact cover could separate the stationary base, elevated transit, and low parking-descent volumes. That is only a **candidate representation**: its added volume must pass complete dense-box containment and blocker checks at every proposed allowance before use. Do not silently substitute phase hulls, discard troublesome geometries, round away blockers, or infer a continuous sweep bound. The native cached-transform/next-qpos alignment limitation remains. The existing 5 s engineering hold and approximately 5.002 s measured simulation interval to admission do not establish an operational restart-duration guarantee.
