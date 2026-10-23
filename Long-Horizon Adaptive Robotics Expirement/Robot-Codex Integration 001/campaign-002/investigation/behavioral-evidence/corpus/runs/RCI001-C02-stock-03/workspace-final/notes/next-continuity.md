# Recovery continuity
Run: episode-7005a60ca4a0484d. Activation: activation-001. Invocation: pilot-ce3fd617f36c. Authority epoch 3; order version 1; incarnation 3; restart generation 0.
Last reviewed event: 34 (events 1-34 inspected without gaps; later history not comprehensively reviewed). Subsequent evidence below comes from authoritative command queries and status, not an advanced history cursor.

Task: one family A part, recipe A, passing inspection linked to its eligible cycle, tray1; no rework. Configured development recovery pilot; canary qualified.

Incident: event 28 requested help because the conventional sequencer had no eligible next step. Initial public observations showed raw A1 in quarantine, insert_A installed, no processing or inspection. Events 3-25 were only completed conventional observe commands. Current ownership was acknowledged at epoch 3, with no unresolved prior action. Source records: notes/history-start.json and notes/status-before-recovery.json.

Recovery: act001-stage-a1-01 transported A1 to parking1; requested event 1074, admitted at simulation time 107.276 s with observation 1050. Authoritative query reports terminal completed at 120.658 s and public observation support at sequence 1183. Post-action capture act001-stage-a1-capture-01 completed at 131.162 s with sequence 1285. No replay or second physical action was submitted.

Verified outcome: status sequence 1364, capture simulation time 138.984 s, age 0.134 s at retrieval, detects A1 raw at parking1 (world metres approximately .3444,.0394,.0175), insert_A at fixture and insert_B at home. Measured jaws .080 m, no visible held object, near-zero joint velocities, no active or unresolved commands. Station idle, ready, not clamped, no fault, guard open, no observed seated part; cycle ID 0, inspection null. Source: notes/status-after-stage.json. Structured evidence only; no PNG content inspected. One of 20 physical action requests used.

Handback outcome: act001-handback-01 completed at simulation time 178.014 s (request event 1789, fresh dispatch observation 1753). The supervisor returned owner conventional and authority epoch 4, verifying public resumption conditions with next_operation transport. Recovery invocation remains pinned to former epoch 3 and must not actuate. No unresolved robot recovery command remains.

Activation finished: A1 is staged and control is returned. The conventional controller must perform loading, recipe A processing, cycle-linked passing inspection and tray1 delivery. Final order completion has not been observed or claimed. End this activation for supervisor scheduling; no further recovery step or help request is needed on the verified state.

Publication limit: after successful handback, committing this final note via robot.py continuity was rejected with invocation_capability_denied. No retry or additional gateway request followed. The protected Continuity.md therefore retains the verified pre-handback plan; notes/recovery-result.md retains this terminal receipt summary for re-entry. A future authorized invocation should reconcile act001-handback-01 with the public host record rather than replaying it.
