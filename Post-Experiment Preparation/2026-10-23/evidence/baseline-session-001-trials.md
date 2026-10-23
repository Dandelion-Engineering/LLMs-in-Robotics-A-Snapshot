# Session-001 throwing results

These measurements came from public status and observation feedback during 2026-10-10 practice. No environmental ground truth was read. Coordinates below are commanded arm targets in meters; every trial used the initial base location with throwing heading approximately -0.3208 rad in dead reckoning.

| Trial | Desired grip | Preparation (x,z) | Acceleration target (x,z), seconds | Opening target (x,z), seconds | Landing time, simulation s | Inside | Forward/left error, m |
|---|---|---|---|---|---|---|---|
| 1 | .055 | (.32,.80), 1.2 s, included in trajectory | (.75,1.10), .25 | (1.01,1.29), .12 | 158.940 | false | -1.281 / +.428 |
| 2 | .025 | (.35,.90), separate 1.2 s arm command | (.76,1.12), .25 | (1.02,1.30), .12 | 236.168 | true | +.135 / -.043 |
| 3 | .025 | same as 2 | (.76,1.12), .25 | (1.02,1.30), .12 | 303.880 | true | +.173 / -.055 |
| 4 | .025 | same as 2 | (.76,1.12), .27 | (1.02,1.30), .13 | 378.516 | true | +.055 / -.015 |
| 5 | .025 | same as 2 | (.76,1.12), .27 | (1.02,1.30), .13 | 448.792 | true | +.055 / -.015 |
| 6 | .025 | same as 2 | (.76,1.12), .28 | (1.02,1.30), .135 | 525.332 | true | +.037 / -.009 |

All y targets and wrist pitches were zero. Opening target width was .15. Trials 2–6 began with a separately verified lift at (.60,0,1.20), then retraction to (.30,0,1.15), then base rotation to the observed clear throwing direction.

Observed pickup center was approximately (.60,0,.935) facing the pedestal at initial-frame yaw -1.5708. Requested width .025 yielded measured width about .089 and effort 19.17, with bilateral contact and secure-lift confirmation at 1.20 m. Initial .055 request yielded effort 10.25; trial 1 changed multiple other factors, so it does not isolate grip strength as the cause of failure. Its reported landing time preceded trajectory completion; the failure mechanism remains uncertain.

Trials 5 and 6 exercised Programs/Learned/throw_orange.py. Their raw program output is in session-001-trial-5.jsonl and session-001-trial-6.jsonl. Trial 6 was closer to center but tested once; the repeated .27/.13 settings remain the program default.

Head images actually viewed: observation 11 showed the orange object inside the bin after trial 3. Observations 3/4 established pickup geometry. Observation 8 showed the charger and supplied selected-pixel points.
