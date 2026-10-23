# Recovery continuity

Run episode-85f09f0794d04f26; activation activation-001; invocation pilot-c6d522a211c8. Recovery ran under epoch 3, order revision 1, incarnation 3, restart_generation 0. Handback a001-handback-v2 completed at sim 272.778 s and returned acknowledged ownership to conventional at epoch 4. This invocation no longer has control.

Last reviewed event: 25. Events 1-25 were inspected without gaps and saved in notes/start-history.json. Later command/query/status receipts listed below were inspected separately; intervening observation history was not scanned. All scene evidence is structured RGB-D detections; no PNG was visually inspected.

Order version 1: one family B part, recipe B, tray2, no rework. Processing, linked passing inspection and final delivery remain unverified and belong to the conventional controller after handback.

Incident: setup(B) destination-occupied rejections, events 3-16; assistance/ownership events 19-23. A1 was on insert_home_A, blocking return of insert_A.

Recovery and outcomes:
- a001-clear-a1-parking1-v1 (request event 1017) transported A1 to parking1; terminal completed at sim 121.762 s. Observation 1335 (capture 136.088 s) positively confirmed A1 parking1, open empty jaws and idle arm/station.
- a001-handback-v1 (request event 1749) was terminal rejected at sim 175.084 s: unsupported_resumption, frozen conventional controller lacks a supported next action. Ownership stayed robot; clearing the obstruction alone was insufficient for reconciliation.
- a001-setup-b-v1 (request event 2066) ran native setup(B); terminal completed at sim 239.464 s with public observation support sequence 2369 (capture 239.488 s).

Latest independent outcome evidence: status at sim 241.018 s, observation 2383 acquired 240.888 s, age .130 s. insert_A positively detected on insert_home_A at world [.1875,-.2494,.0080] m; insert_B positively detected in fixture at [.5718,0,.0080] m and station.fixture_insert B. A1 remains parking1, B2 raw. All four known objects accounted for. Station ready/idle/unclamped, no fault or seated part. No active or unresolved command, near-zero joint velocity, jaws .080 m and no visibly held ID, TCP [.2782,.2865,.4674] m. Insert exchange is physically supported by these observations.

Handback outcome: a001-handback-v2, request event 2740, terminal completed at sim 272.778 s, owner conventional, new epoch 4. Envelope used refreshed observation 2701. Supervisor verification: public_resumption_conditions, next_operation transport. Recovery activation is finished; no further actuation is authorized. A subsequent read-only status request returned invocation_capability_denied, so actual conventional motion and order completion after handback were not observed. The denial does not negate the explicit completed handback receipt.

Unresolved recovery commands: none. Budget 2/20 action requests, 0/50 explicit observations; automatic subsequent acquisitions supplied the verification. Non-actuating /canary.py checks qualified. Use python3. Remaining uncertainty: subsequent order processing/inspection/delivery have not been observed. The attempted final robot.py continuity commit was rejected with invocation_capability_denied after successful handback. Protected Continuity.md remains the pre-handback note; this notes/next-continuity.md is the local supplemental outcome record. Reconcile request a001-handback-v2 through public history on a future authorized invocation.
