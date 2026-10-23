# Development 003 results

The eight original attempts completed, and all eight passed their recorded actual-host timing gate. C0 and A3 completed their three-part jobs; A1 completed no parts before its cap, and A2 completed one part before its cap. These are development observations: every canonical validity remains `unknown`, and the attempts do not establish scored readiness, a persistence benefit, or an architecture ranking.

The execution job was `20260923T104637848546Z-10f91c9b`, officially succeeded/0 at 2026-09-23 11:50:39.345071 UTC. The completed derivation `20260923T120012011674Z-75d4a1dc` succeeded/0 at 12:04:10.352697 UTC. Its [index](../Evidence/derived/development-batch003-001/index.json) retains all eight attempts, eight completed derivations and zero integrity findings; derivation completion is distinct from robot task success. Original records are in [runs.jsonl](../Architecture%20Map/runs.jsonl) and [results.jsonl](../Architecture%20Map/results.jsonl). The [execution receipt](../Evidence/queue-receipts/20260923T104637848546Z-10f91c9b.json) and [derivation receipt](../Evidence/queue-receipts/20260923T120012011674Z-75d4a1dc.json) remain authoritative for queue completion.

| Original run | Condition; scenario | Accepted | Outcome / termination | Wall duration (s) | Model calls | False completion claims |
|---|---|---:|---|---:|---:|---:|
| B01-dev-C0-010 | persistent; restart, n3, seed 0 | 3/3 | success / independent completion | 168.029 | 0 | 4 |
| B01-dev-C0-011 | persistent; restart, n3, seed 6 | 3/3 | success / independent completion | 171.528 | 0 | 4 |
| B01-dev-A1-005 | persistent; mixed, n6, seed 3 | 0/6 | failure / 600 s cap | 600.000 | 92 | 0 |
| B01-dev-A1-006 | no-persistence; mixed, n6, seed 3 | 0/6 | failure / 600 s cap | 600.000 | 100 | 0 |
| B01-dev-A2-003 | persistent; mixed, n10, seed 6 | 1/10 | partial / 900 s cap | 900.001 | 37 | 0 |
| B01-dev-A2-004 | no-persistence; mixed, n10, seed 6 | 1/10 | partial / 900 s cap | 900.000 | 37 | 0 |
| B01-dev-A3-003 | persistent; restart, n3, seed 2 | 3/3 | success / independent completion | 201.379 | 10 | 4 |
| B01-dev-A3-004 | no-persistence; restart, n3, seed 2 | 3/3 | success / independent completion | 200.486 | 10 | 4 |

All execution statuses are `completed`, including capped failures and partial outcomes. Maximum recorded lag ranges from 0.016133 to 0.043243 s. False completion claims are retained despite eventual independent success. The different scenarios, populations, caps and small development sample do not support cross-architecture performance comparisons or causal claims about persistence.

## Two restart prerequisites remain unresolved by these runs

**The original C0-010 public after-release milestone did not ensure a settled released part.** Its sole `restart_begin` is event/line 130, simulation time 11.014 s (episode elapsed 10.514 s). It exercised the configured first-transport milestone without fallback: phase 7, jaw width 0.065176 m, A1 delivered to `fixture`. The recorded classifier is `inadmissible`: `unheld_bodies_supported_and_slow` and `supported_target_part` failed. Open/no-hand-contact consistency and destination containment passed. A1 had 0.828652 N upward nonhand support, but its angular-velocity y component was 0.156922 rad/s, already above the 0.1 rad/s angular-rest norm limit. Thus open jaws and destination containment at that public phase did not establish the required rest state. Eventual 3/3 completion does not repair the original cut. See the completed [C0-010 diagnostic](<D:/CodexEvidence/LLMs-in-Robotics/C0-010-original-restart-002/restart-diagnostic.json>) and its [receipt](../Evidence/queue-receipts/20260923T121046690455Z-cfac2f83.json).

**The two original A3 carry cuts fall outside the supplied route's joint-state support.** Both cuts exercised first-transport `closed_grip_transfer`, phase 4, without fallback. Both recorded `measured_grip_envelope=pass`; the sole required failing predicate was `measured_recovery_route`. Its `joint_start` and `joint_velocity` checks were false. All other route checks were true, including TCP start, finger velocity, payload identity, destination identity/availability and corridor clearance; blocker lists were empty.

| Original cut | Event/line | Simulation time (s) | TCP z (m) | Joint 1 position (rad) | Joint 3 velocity (rad/s) |
|---|---:|---:|---:|---:|---:|
| A3-003 | 108 | 8.500 | 0.080239196 | -0.019757062 | -0.588737477 |
| A3-004 | 108 | 8.484 | 0.080238660 | -0.019695053 | -0.588810617 |

For concrete recorded witnesses, the supplied joint-1 start range is `[-0.112519, -0.052519]` rad and joint-3 velocity range is `[-0.579202, -0.379202]` rad/s. Both cuts are outside those respective ranges. Their active A3 transport objectives requested clearance 0.25 m, speed scale 1.0 and vertical approach. These values locate the support mismatch; they do not prove its entire cause or authorize wider envelopes. The full seven-joint vectors, unchanged predicates and original calibration entries remain in the [A3-003 diagnostic](<D:/CodexEvidence/LLMs-in-Robotics/A3-003-original-restart-002/restart-diagnostic.json>) and [A3-004 diagnostic](<D:/CodexEvidence/LLMs-in-Robotics/A3-004-original-restart-001/restart-diagnostic.json>), completed under receipts [152684c6](../Evidence/queue-receipts/20260923T121124591330Z-152684c6.json) and [2d25d4aa](../Evidence/queue-receipts/20260923T121215575285Z-2d25d4aa.json).

These diagnostics preserve the original cuts; they do not choose later favorable states or rerun the classifier. Public-milestone repair and any broader measured route support require prospective verification. No future repair, replacement probe or new qualification is claimed passed here. Later source edits do not change these original results.

## Evidence-check correction and limits

The initial C0-010/A3-003 `-001` diagnostics incorrectly treated every physical-class identity key as a literal Runtime ZIP filename. That produced a false source-mismatch flag: `descriptor_exporter` is the hash of `restart_physical_class.py`, while `mujoco_build` and `robot_assets` are composite native-build/asset identities. This was a diagnostic evidence-check bug, not evidence that the original episode's Python source bytes differed. The original `-001` outputs remain unchanged.

Schema 1.1 reads the alias declaration from the exact archived source and reports each Python comparison separately. All three fresh reports show matching Python source/archive, snapshot-content, classifier/result-copy, exposure and authority-revocation checks, with no reported missing links. Native-build and robot-asset identities are retained as **not applicable to the Runtime source archive and unverified by this check**. That narrower correction grants no physical qualification and leaves the original inadmissible predicates intact. The existing continuity derivations retain their separate unknown qualification/admissibility scope; this note does not overwrite them or create an evaluation denominator.

Only completed canonical records, completed derived metadata and officially completed diagnostic outputs were read for this note. No raw event/motion scan, experiment, reclassification, test, queue operation or evidence mutation was performed. The diagnostic contexts are finite samples, not continuous-state or future-recovery guarantees.

| Retained artifact | SHA-256 |
|---|---|
| Development 003 derivation index | `592aec1d8f8b1d831794f0f1b1cc6992e5a82fadf713c7803a84182c1abf10bb` |
| C0-010 corrected `-002` report | `6975c27d81327a034b2c793ccb08931e42f18bb03d0ace33c788d93b3936990c` |
| A3-003 corrected `-002` report | `478ae1b8b7d813794d97fa7c3b9070c4a43037a7ac7ab4cd5977e6dfafa529ef` |
| A3-004 `-001` schema-1.1 report | `9de6f28f8b81978bd8631ca1cc04589d2f7236fe83802a504d8155bbe136c150` |
| Schema-1.1 diagnostic helper | `9fd36fe549d5d83a8da4c6b58d148736e36eed1f7410604d786404fc8dd8eada` |
