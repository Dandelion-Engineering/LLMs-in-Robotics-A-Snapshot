# Sensor-mark calibration after physical-calibration-001

Both held-recovery probes in physical-calibration-001 correctly retained failure: the first captured packet contained no part classified as raw. The common classifier introduced after C0-004 rejected ordinary unobscured markers. Passing its initial synthetic checks had not established real-image usability.

The retained [held-recovery frame 000001](../Evidence/calibration/physical-calibration-001/held-recovery/camera-0/000001.png) explains the failure. An 8 mm marker projects to approximately 3.55 pixels in the calibrated overhead view. The fixed five-column crop includes a colored tag edge and a body/background edge. For A1/B2/A3, only 80% of the full crop meets depth consistency; the three central columns are all coplanar and dark. The earlier 90%-of-whole-crop rule therefore returns unknown despite a clear visible marker.

The recorded processed A1 in [C0-004 frame 000419](../Evidence/raw/B01-dev-C0-004/frames/000419.png) adds a second necessary case. Its central columns are coplanar; two are white with channel spread about 0.004, while the adjacent edge is a tag/white blend with spread about 0.196. Requiring all three columns to be achromatic would still reject this clearly visible processed marker. B10's false-positive crop in the same frame remains entirely foreground robot, approximately 564 mm closer than its tag.

The revised common [classifier](../Runtime/sensor_worker.py) retains the 4 mm plane-depth tolerance and uses the central three columns of the complete 7-by-5 search crop. At least 90% of that whole core must agree with the observed tag depth. Two adjacent columns must each contain at least 90% jointly supported pixels of the same appearance: dark (`max RGB < 0.25`) or white (`min RGB > 0.72`, channel spread at most 0.10). Any opposite-class pixel in the core prevents classification. Single-column evidence, mixed dark/white marks, occlusion, incomplete crops and other ambiguity remain unknown. No protected pose, process state, inspection outcome or evaluator label enters this function.

Exact crops from existing recorded RGB/depth artifacts now classify as follows:

| Recorded case | Revised classification |
|---|---|
| Held-recovery initial A1, B2 and A3 | raw |
| C0-004 frame 419 A1, visibly white processed marker | processed |
| C0-004 frame 419 B10, white robot foreground | unknown |

The [measurement record](SensorMarkProposal/marker-core-calibration.json) retains crop coordinates, tag depths, exact compressed numerical fixtures, classification outputs and SHA256 hashes of all four original image/depth files. Eleven marker tests include these five real-image cases plus synthetic noise, occlusion, partial support, opposing appearance and detector integration checks. The combined sensor/candidate subset passed **67 checks in 1.258 seconds**. No new rendering, physics, inference or queue job was run for this bounded image inspection. The corrected `sensor_worker.py` SHA256 is `1da12301ae5509ccdcf408c71f1181a39a7d58ec09ce360f885161abd2442fd0`.

This updates common perception calibration before a new physical probe; it does not change or relabel physical-calibration-001. It demonstrates classification of the retained crops, not successful held recovery or broad perception readiness. The fixed crop still assumes the calibrated overhead geometry and approximately aligned tag/marker projection. More severe rotation, partial tag localization or same-depth ambiguity may remain unknown or inaccurate and require separate evidence. Position uncertainty and ten-part visibility are a separate calibration issue.
