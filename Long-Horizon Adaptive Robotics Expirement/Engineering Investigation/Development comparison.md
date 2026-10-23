# First two conventional-baseline development traces

These observations describe development recordings, not a scored architecture comparison or a controlled causal estimate. Both manifests identify the conventional baseline, persistent condition, nominal scenario and seed 0. Original raw records remain immutable; current canonical assessment `B01-dev-C0-002-result-correction-1` withdraws the second run's old full-completion claim because both inserts remained in the fixture. The old evaluator omitted those completion predicates. The workspace exposes the current correction before the historical raw assessment.

| Recorded assessment | B01-dev-C0-001 | B01-dev-C0-002 |
|---|---|---|
| Current task outcome | Failure; time cap | Partial; unsupported old completion claim withdrawn |
| Historically recorded accepted count | 0 | 3: A1 and A3 in tray1, B2 in tray2; not strictly re-scored |
| Observed wall duration | 300.000 s | 142.906 s; old evaluator stopped early |
| Full-task completion time | Unavailable | Unavailable; 142.906 s is not a valid full-task completion time |
| False completion assertions | 0 | 0 |
| Actual-host timing gate | Passed | Failed |
| Complete windows outside real-time-factor tolerance | 0 / 300 | 4 / 142 |
| Current validity | Unknown; readiness gates incomplete | Invalid; actual-host timing gate failed and old evaluator omitted insert-state predicates |

The second recording does not establish full-task completion, scored readiness or acceptable timing. The retrospective correction does not recompute every physical predicate or historical accepted count. The recorded timing failure does not itself assign fault to the candidate.

## Transport, visibility and the next decision

In the first run, request 6 transports A1 to the fixture and physical service event 103 reports the trajectory ended at 9.064 simulation seconds. Observation 102 at 9.002 s and subsequent captures through 10.502 s contain no A1 detection. Evaluator snapshot 97 separately places A1 at approximately `[0.5718, -0.0001, 0.0336]` metres. Reply 107 retains an unresolved transport; the trajectory feedback explicitly requires observation to establish the physical outcome. The [actual frame](../Evidence/raw/B01-dev-C0-001/frames/000086.png) shows the arm over the fixture. A raw motion sample at 9.072 s records TCP `[0.5673, 0.0001, 0.1883]` m.

In the second run, observation 113 at 10.002 s detects A1 in the fixture. Observation 116 at 10.302 s records 144 tag pixels and the position approximately `[0.5722, 0, 0.0336]` m. Dispatch 120 parent-links that capture; reply 121 resolves the transport with the recorded reason “fresh visible destination, measured open gripper and no visible holding of that part.” Request 122 at 10.386 s then starts A1's cycle. The [actual frame](../Evidence/raw/B01-dev-C0-002/frames/000099.png) shows the fixture tag exposed beside the returned arm. A raw motion sample at 10.382 s records TCP `[0.4023, 0.0002, 0.4653]` m.

This sequence supports the supervising operator's interpretation that the added return to a clear-view posture removed the immediate visibility blockage. The images, detections, context and action sequence establish the local difference. Two development runs do not isolate the return motion's causal effect on full-episode success; runtime changes, timing, and the absence of repeated controlled runs limit that inference. Candidate rationale is recorded reasoning, not independent grading authority.

## Source identity

| Run / file | SHA-256 |
|---|---|
| 001 events.jsonl | `027881c1f22de1819b3ef8b6911ef4f7b776427bc1ddcc8a18c0d3fc3907df27` |
| 001 result.json | `2c3a5c48810437c32a673a3b0335d01df93a23cecfbb1f05707b5ba53d49d357` |
| 002 events.jsonl | `fc110a6b0151dcc3dbb6ebcf3499fccb66c160247147fc749b5e0d9aab392568` |
| 002 result.json | `7e2393527166ba2e48b061e92bd526780c942e2a98d8e98c5815f807c5343b5d` |

The viewer also retains manifest and motion source hashes. Event times above are the logger's simulation clock; result duration is elapsed episode wall time. They have different origins and are not interchangeable.
