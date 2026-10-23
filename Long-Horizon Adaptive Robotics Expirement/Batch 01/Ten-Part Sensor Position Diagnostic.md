# Ten-part sensor-position diagnosis from physical-calibration-001

The two biased detections are **A7 and B8**, partially covered by the robot in the overhead camera. Their visible-fragment centroids are not their tag centers. B10 is almost entirely occluded and does not meet the detector's minimum 12 matched pixels. This is a separate limitation from process-mark classification; the marker-core correction does not establish position accuracy or ten-part readiness.

The three existing ten-part measurements are events 30, 33 and 37 in [the protected static-sensor event stream](../Evidence/calibration/physical-calibration-001/static-sensors/events.jsonl), using development seed 2. No new simulation or rendering was performed.

| Part | Position error in samples 1 / 2 / 3 | Matched pixels in each sample | Dominant error |
|---|---|---:|---|
| A7 | 5.600 / 5.499 / 5.636 mm | 119 | x about −3.3 mm; y about −4.5 mm |
| B8 | 11.202 / 11.120 / 11.229 mm | 39 | y about −11.0 mm |
| B10 | Not detected in any of the three samples | Below admission threshold | No position estimate returned |

All six A7/B8 comparisons exceed the fixed public `uncertainty_m=0.004` scalar. Repeated small sensor noise does not explain the much larger, consistently directed planar bias. These are direct comparisons retained by the calibration probe, not a statistical coverage estimate.

[Static frame 01](../Evidence/calibration/physical-calibration-001/static-sensors/camera-2/static-01.png) visibly shows the robot covering those stock tags. Reconstructing the existing hue masks from this saved RGB image gives:

| Part | Main connected component | Visible-pixel median `(u,v)` | Independently projected full-tag center `(u,v)` | Foreground fraction over expected tag footprint |
|---|---:|---|---|---:|
| A7 | 115 pixels | (269, 313) | (270.454, 311.016) | 25.0% |
| B8 | 39 pixels | (309, 316) | (308.188, 311.112) | 74.56% |
| B10 | 6 pixels, below threshold | (266, 284.5) | (270.344, 279.427) | 97.92% |
| A9, unobscured comparison | 156 pixels | (347.5, 311) | (347.401, 310.980) | 0% |

The foreground diagnostic counts saved depth more than 20 mm closer than the expected tag plane within the independently projected tag footprint. Physical centers come from the protected, capture-aligned calibration comparison and are used **only to audit the detector**. They are not proposed perception inputs and must never enter candidate packets or service planning. The operational detector currently takes the median of all color-matching pixels without establishing that the whole tag is visible.

A7 also has four stray matching pixels around `(261.5,239.5)`, separate from its main tag component. Removing those four pixels leaves the same biased median `(269,313)`: component filtering alone would not fix its partial-tag center. B8 has one connected fragment. The minimum separation between the known tag palette hues is 0.078632, greater than twice the detector hue tolerance (0.048), so nominal identity-band overlap is not the cause. Stray image colors can nevertheless satisfy a tag's hue threshold, as A7 demonstrates.

The narrow proposed direction is an image-only component and tag-completeness check before an actionable center estimate. Compare a coherent, coplanar color component with the known tag geometry projected through the public camera calibration; reject partial/foreground-contaminated support rather than label its fragment median as a full-tag center. Missing or incomplete position evidence should remain explicit. The existing `.004` scalar must not be treated as a demonstrated bound for these partial detections. Increasing every part's uncertainty to cover the observed maximum would conceal the visibility defect and would not establish a principled bound.

Completeness rejection alone cannot make occluded stock visible. A shared public active-view operation or qualified additional view is needed, with actual recapture evidence showing useful tag coverage and calibrated center errors after the arm moves. Existing partial tag identity, if retained, must be distinguishable from a position that is safe to dispatch. Any adapter changes must apply equally to all entrants. No hidden pose substitution, candidate-specific view privilege or baseline scheduling fallback is proposed. Thresholds and view motions need a subsequent registered physical calibration; this note does not choose an unmeasured completeness threshold or claim that a static initial view can reveal all ten parts.

Exact extracted rows, component geometry, palette separation and protected comparison metadata are retained in [n10-position-diagnostic.json](SensorMarkProposal/n10-position-diagnostic.json). The inspected first RGB SHA256 is `a66fbd9540413e2360c337cb8d0a95e7edc9a4619dee20f715e59813e58f75dd`; corresponding depth SHA256 is `9cdcf805fc8d53c6a44f7e33b590a1e211f7b45baae19050c3a32c5003295a92`. Inspection covered the small nine-measurement calibration log and one static image/depth pair, with no full episode/motion aggregation. Runtime position logic is unchanged, and failed physical-calibration-001 remains retained.
