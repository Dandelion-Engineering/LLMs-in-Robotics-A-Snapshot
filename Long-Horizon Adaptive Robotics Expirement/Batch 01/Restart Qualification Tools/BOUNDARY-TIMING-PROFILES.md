# Completed boundary timing diagnostics 001–003

All three official queue jobs succeeded with exit 0, and all selected physical trials passed. **Actual host timing failed in 001 and 002, then passed in the single diagnostic 003.** Each ran only the original `parking1-corner-B-5` construction trial (population 10, payload B10); the other 39 original declarations remain explicitly deferred. All summaries report unchanged sources, `diagnostic_only: true`, `qualification_evidence_eligible: false`, and `qualification_granted: false`. None is a full construction screen, qualification, candidate-performance result, or readiness claim.

This note reads only the completed small summary/result files and retained receipts. It neither reads raw streams nor changes original evidence.

| Measurement | Diagnostic 001: original scheduling/sealing | Diagnostic 002: seal priming + fixed-entry catch-up |
| --- | ---: | ---: |
| First at-cut rich capture | 35.5871 ms | 16.7445 ms |
| Immediately after cancellation capture | 17.6431 ms | 14.4566 ms |
| After-absence capture | 16.5665 ms | 15.6275 ms |
| Before-dispatch capture | 16.3833 ms | 16.9606 ms |
| After-admission capture | 20.1839 ms | 18.4936 ms |
| Cut classification | 0.3872 ms | 0.3914 ms |
| Forced geometry sample range, all recorded boundaries | 2.1429–3.0015 ms | 2.0152–2.7323 ms |
| Maximum measured lag | 71.5387 ms | 56.8304 ms |
| Maximum timing sample gap | 65.6291 ms | 47.5795 ms |
| Failing one-second RTF windows / complete windows | 4 / 18 | 2 / 18 |
| Failing window starts (wall seconds) | 6, 7, 11, 12 | 11, 12 |

In 001, the first cut capture through the after-cancellation forced geometry occupied 64.2720 ms with no simulation advancement. The after-absence capture through after-admission forced geometry occupied 71.2266 ms with one 2 ms simulation step. The narrower before-dispatch through after-admission group alone occupied 48.8899 ms without a step. These elapsed spans include intervening unprofiled work; they are not sums attributable solely to the exporter.

In 002, the fixed-entry catch-up performed 12 ordinary steps, advancing simulation by 24 ms while consuming 11.7746 ms of wall time. It left 11.2081 ms of measured lag. The following before-dispatch through after-admission group occupied 47.0456 ms without a step. The failing 11–12 and 12–13 second windows had RTF 0.9458828235 and 1.0541171765; interpolated lag at wall 12 s was 54.1172 ms. First-capture cost decreased in this observed repeat, but warm accumulated delay remains a demonstrated failure. A single repeat is not a general speedup estimate or proof of a sufficient repair.

The full recorded before-cancel→accepted-admission hold in 001 covered 2,501 tick checks plus two endpoints, 5.0020 simulation seconds and 5.0055517 wall seconds; in 002 it covered 2,512 tick checks plus two endpoints, 5.0240 simulation seconds and 5.0342729 wall seconds. All recorded hold checks passed. These are discrete-tick and endpoint observations, not continuous-time guarantees or qualified absence bounds. Additional pacing steps change actual state and supported duration; later qualification must retain that measured interval.

The wrappers time complete capture/classification/forced-geometry operations. Native export, snapshot conversion/hashing, event encoding/write/flush and nested geometry costs were not separately instrumented. The evidence supports addressing accumulated delay between observation groups while keeping each cut/cancel and dispatch/admission group intact. Root subsequently authorized a prospective feedback pacer using ordinary steps until fresh public sensing and current lag no greater than the existing timestep; its single-trial outcome is recorded below. No clock reset, erased lag, observation movement, tolerance relaxation or qualification grant follows from these diagnostics.

## Diagnostic 003: bounded feedback pacing, one observed pass

The revised pacing rule checks actual current wall-minus-simulation lag against the existing 2 ms timestep alongside public readiness. The fixed entry target remains descriptive only. The eight-second phase timeout, ordinary physics/hold/geometry steps and existing timing monitor/caps remain in effect. The report records success after 23 ordinary ticks: simulation advanced 46 ms while wall time advanced 21.7537 ms, reducing entry lag from 25.8311 ms to 1.5848 ms. The final predicate measurement was 1.5828 ms; the separate exit measurement retains the small additional elapsed cost.

| Diagnostic 003 measurement | Observed value |
| --- | ---: |
| At-cut / immediately-after-cancel rich capture | 17.3046 / 17.0054 ms |
| After-absence / before-dispatch / after-admission capture | 17.5378 / 16.3832 / 18.4450 ms |
| Cut classification | 0.3766 ms |
| Forced geometry sample range, all recorded boundaries | 1.8917–2.6367 ms |
| Before-dispatch through after-admission group, no intervening step | 46.3187 ms |
| Maximum measured lag / timing sample gap | 47.4839 / 47.8476 ms |
| Failing one-second RTF windows / complete windows | 0 / 18 |
| Actual host timing pass | true |

The full before-cancel→accepted-admission hold covered 2,523 tick checks and two endpoints, all passing, for 5.0460000 simulation seconds and 5.0456211 wall seconds. This includes the additional pacing ticks and normal accepted admission; it is not a newly certified absence bound. Both physical and host-timing checks passed for this diagnostic, while all-declared summary flags remain false because 39 declarations were deferred.

This repeat supports the local pacing repair under this observed workload, without establishing a broad timing margin, a full construction result or qualification. At this addition, root reported the fresh 28-trial construction 003 active under job `20260923T092904839719Z-04533969`; no active output was read, and all 12 reserved validation trials remained untouched. The retained 001/002 failures and their original measurements are unchanged.

## Retained small artifacts and exact byte identities

001 ran 2026-09-23 09:18:21.186646–09:18:45.986400 UTC. 002 ran 09:22:10.366950–09:22:46.256224 UTC. 003 ran 09:27:27.027284–09:28:02.917146 UTC. Receipt argv binds the same declared diagnostic to each fresh output directory.

| Artifact | SHA-256 |
| --- | --- |
| [001 official receipt](../../Evidence/queue-receipts/20260923T091820736439Z-183e9e54.json) | `fdd1e89dcd532b26a56a51b32f7ee3f723ddfa0497127b3696d0a86e9a717024` |
| [001 summary](D:/CodexEvidence/LLMs-in-Robotics/recovery-boundary-timing-001/summary.json) | `f2a228c97480e11f41303a76d285b3d2f665c278c2af3b33f05b11d13c52df4d` |
| [001 child result](D:/CodexEvidence/LLMs-in-Robotics/recovery-boundary-timing-001/parking1-corner-B-5/result.json) | `f9f9b7332613a85a5db1f3a770d847ba35b961da9328ca3fde64b192588d4a4c` |
| [002 official receipt](../../Evidence/queue-receipts/20260923T092209931696Z-474527be.json) | `607d4d5ebc67124c58ed39cc01ccb1bc957d76610afc9928454e8186d013c201` |
| [002 summary](D:/CodexEvidence/LLMs-in-Robotics/recovery-boundary-timing-002/summary.json) | `d39986068afa6bfced95107dc8c331b5f6ac5912d9dd29353a7ab460bf8e83bc` |
| [002 child result](D:/CodexEvidence/LLMs-in-Robotics/recovery-boundary-timing-002/parking1-corner-B-5/result.json) | `24e625e5585c3f885ff3659680d48346c22db2e8b24208d2ffb9768143da5c96` |
| [003 official receipt](../../Evidence/queue-receipts/20260923T092726598704Z-d98fed6a.json) | `efad86ade275cf0dee6ef03bf412ce7c39c3daf2a4328ce61c553961086d2447` |
| [003 summary](D:/CodexEvidence/LLMs-in-Robotics/recovery-boundary-timing-003/summary.json) | `4181dc250abcd580a1ffaae85f3a40642a135c445b9d98935de9b34e26697853` |
| [003 child result](D:/CodexEvidence/LLMs-in-Robotics/recovery-boundary-timing-003/parking1-corner-B-5/result.json) | `866db87de604f4b7a1e327cbedfec055763ff5ea75d6b06a3ca8603a7cdb202f` |

Each rehashed child result matches its summary's `result_sha256`. Full measurements and the exact list of 39 deferred trial IDs remain in the originals.
