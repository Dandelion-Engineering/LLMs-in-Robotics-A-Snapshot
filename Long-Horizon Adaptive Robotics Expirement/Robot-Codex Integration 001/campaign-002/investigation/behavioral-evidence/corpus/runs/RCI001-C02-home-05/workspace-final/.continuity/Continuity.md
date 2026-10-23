# Recovery continuity

Run episode-5f510a500b414f74; activation-001; invocation pilot-c06112d19e32. Runtime incarnation 3 / restart generation 0. Last acknowledged ownership: robot, epoch 3, order revision 1. Order: one family B part, recipe B, tray2, no rework.

Last reviewed event: 24 (events 1-24 inspected, no gaps). Later evidence below comes from authoritative command queries/status, not intervening history review. Startup history: notes/startup-history.json.

Incident: three conventional setup(B) admissions rejected destination occupied (events 5,10,16); A1 was on insert_home_A. Recovery transport pilot-c06112d19e32-clear-a1-v1 (request event 1143) completed sim 134.666 s. Capture pilot-c06112d19e32-after-clear-a1-v1 completed sequence 1371; status 1467 confirmed A1 on parking1 and idle/open gripper state.

First handback pilot-c06112d19e32-handback-v1 was terminal rejected (event 1843, sim 184.036 s), unsupported_resumption: frozen controller lacked a supported next action. Ownership stayed robot. Interpretation: exhausted setup attempts required completing setup in recovery.

Recovery setup pilot-c06112d19e32-setup-b-v1 (request event 2296; admission observation 2264) completed at sim 261.934 s; query verification reports public observation support 2594. Explicit capture pilot-c06112d19e32-after-setup-b-v1 completed sequence 2727 at sim 275.296 s.

Verified post-setup evidence: notes/after-setup-status.json, observation 2831, capture sim 285.610 s, age 0.102 s at read. insert_B is in fixture at world [0.57195,0,0.00718] m; insert_A is at insert_home_A [0.18732,-0.24955,0.00718] m. A1 remains parking1 and B2 raw. Station reports insert B, idle/ready, unclamped, no fixture part and no fault. Arm stationary; jaw width 0.080 m and holding_visible_id null. No active or unresolved commands. Structured RGB-D detections and telemetry only; no PNG content inspected.

Next: protected handback pilot-c06112d19e32-handback-v2, PLANNED ONLY. The incident is physically resolved with setup(B) completed; the conventional next productive step is loading B2 for recipe B. On acceptance stop actuation; if response uncertain query this ID. Order processing, linked passing inspection and tray2 delivery remain unconfirmed and belong to conventional operation. Recovery usage: 2/20 actions, 2/50 explicit captures.
