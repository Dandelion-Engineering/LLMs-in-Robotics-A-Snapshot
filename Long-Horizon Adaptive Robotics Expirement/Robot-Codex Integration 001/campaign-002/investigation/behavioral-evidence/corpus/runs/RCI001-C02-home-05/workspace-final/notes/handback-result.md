# Recovery continuity

Run episode-5f510a500b414f74; activation-001; invocation pilot-c06112d19e32. Runtime incarnation 3 / restart generation 0. Handback acknowledged conventional ownership at epoch 4, order revision 1. This invocation remains pinned to old epoch 3 and must not actuate. Order: one family B part, recipe B, tray2, no rework.

Last reviewed event: 24 (events 1-24 inspected, no gaps). Later evidence below comes from authoritative command queries/status, not intervening history review. Startup history: notes/startup-history.json.

Incident: three conventional setup(B) admissions rejected destination occupied (events 5,10,16); A1 was on insert_home_A. Recovery transport pilot-c06112d19e32-clear-a1-v1 (request event 1143) completed sim 134.666 s. Capture pilot-c06112d19e32-after-clear-a1-v1 completed sequence 1371; status 1467 confirmed A1 on parking1 and idle/open gripper state.

First handback pilot-c06112d19e32-handback-v1 was terminal rejected (event 1843, sim 184.036 s), unsupported_resumption: frozen controller lacked a supported next action. Ownership stayed robot. Interpretation: exhausted setup attempts required completing setup in recovery.

Recovery setup pilot-c06112d19e32-setup-b-v1 (request event 2296; admission observation 2264) completed at sim 261.934 s; query verification reports public observation support 2594. Explicit capture pilot-c06112d19e32-after-setup-b-v1 completed sequence 2727 at sim 275.296 s.

Verified post-setup evidence: notes/after-setup-status.json, observation 2831, capture sim 285.610 s, age 0.102 s at read. insert_B is in fixture at world [0.57195,0,0.00718] m; insert_A is at insert_home_A [0.18732,-0.24955,0.00718] m. A1 remains parking1 and B2 raw. Station reports insert B, idle/ready, unclamped, no fixture part and no fault. Arm stationary; jaw width 0.080 m and holding_visible_id null. No active or unresolved commands. Structured RGB-D detections and telemetry only; no PNG content inspected.

HAND BACK COMPLETED: pilot-c06112d19e32-handback-v2, request event 3190, requested sim 316.930 s, terminal completed sim 316.936 s. Gateway returned owner conventional, authority_epoch 4 and verification state public_resumption_conditions with next_operation transport; admission used observation 3143. No further actuation is authorized for this old invocation. A subsequent read-only status request was rejected invocation_capability_denied (notes/handback-status.json); conventional execution and final order completion therefore remain unverified. Recovery resolved the obstruction and installed B with the above observed evidence. Recovery usage: 2/20 actions, 2/50 explicit captures. No help or waiting requested; control was returned to the supervisor/conventional controller.

Continuity publication: the final atomic continuity update was rejected with invocation_capability_denied after successful handback. The protected Continuity.md therefore retains the pre-handback plan; this notes/handback-result.md preserves the acknowledged outcome. Do not infer an unresolved handback from the older note or reuse old epoch 3. No further gateway requests are planned.
