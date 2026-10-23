# Recovery continuity
Run episode-f7e6ac6e69044449; activation activation-001; invocation pilot-6e2c3d8b8fdf. Handback acknowledged: owner conventional, authority epoch 4, order revision 1. Recovery ran under incarnation 3, restart generation 0.

Last reviewed event: 40 (startup events 1-40, no reported gaps; notes/startup-history.json). Later command receipts and current status were inspected; intervening observation history was not scanned.

Task: one family A part, recipe A, passing cycle-linked inspection, tray1; no rework. Final order completion is not claimed.

Incident: assistance event 28 reported no publicly supported eligible action. A1 was raw on quarantine from initial event 1, with no earlier process or inspection recorded. Interpretation: its location excluded it from conventional stock selection.

Recovery outcome: request recovery-a001-a1-to-parking1-v1 (request event 1240) was admitted under epoch 3/revision 1, terminal completed at sim 137.598. Receipt reports public observation support, sequence 1351. Explicit observation recovery-a001-post-parking1-observe-v1 (request event 1439) completed, sequence 1411.

Physical evidence: notes/post-parking1-status.json at sim 153.392, capture 153.324 / sequence 1508, age 0.068 s at read: raw A1 detected on parking1 near world [0.34444,0.03940,0.01759] m; insert_A seen in fixture, insert_B at home. Jaw width 0.080 m, holding_visible_id null; TCP at home view pose, negligible joint velocities. Fixture ready, idle, unclamped, guard open, no fault or visible part. No active or unresolved commands. Action budget used 1/20. Structured detections and telemetry only; no PNG content viewed.

Handback outcome: recovery-a001-handback-v1 (request event 1915) terminal completed at sim 190.618, returning owner conventional and authority epoch 4. Admission used observation sequence 1880. Supervisor verification public_resumption_conditions names next_operation transport. Recovery complete; no further actuation authorized for this invocation. Conventional control must load A1, run recipe A, inspect and deliver the eligible passing part to tray1. Final processing/inspection/delivery remains unverified here. A subsequent status read failed; exact reply saved in notes/post-handback-status.json.
