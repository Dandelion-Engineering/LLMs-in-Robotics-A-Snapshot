# Recovery continuity
Run episode-bdc6255ebbf04d98; activation activation-001; recovery invocation pilot-f0551b8dc129 was pinned to epoch 3/order v1. HANDBACK CONFIRMED: owner conventional, authority epoch 4. No further recovery actuation is authorized under this invocation's old epoch.
Last reviewed event: 5. Focused events 18-25 also reviewed. Initial history 1-35 response was truncated. Later command outcomes were inspected via authoritative query/status/handback receipts; these do not claim a complete event-log review.

Order v1: one family B part, recipe B, eligible cycle with linked passing inspection, tray2, max rework 0. Overall order completion remains unverified.
Incident: conventional setup B rejected destination occupied three times (latest c9d9ff6b-260b-4253-8c23-9a146a888b8e); assistance event 19. A1 was observed on insert_A's return pad.

Recovery outcomes:
- a001-clear-insert-home-a-v1, request event 933: terminal completed at sim 113.266 s; fresh sequence 1247 confirmed A1 on parking1 with open empty-appearing jaws.
- a001-handback-v1, event 1654: terminal rejected unsupported_resumption, conventional controller still lacked supported next action; ownership stayed robot.
- a001-setup-b-v1, event 1968: terminal completed sim 229.100 s, public outcome support sequence 2266. Explicit capture a001-after-setup-capture-v1, event 2389, completed sequence 2349.

Latest physical evidence inspected before final handback: authoritative sequence 2403, capture sim 242.768 s, returned age 0.068 s. Structured RGB-D: insert_B fixture [0.57194,0,0.00726] world metres; insert_A insert_home_A [0.18733,-0.24953,0.00726]; A1 parking1; B2 raw. Uncertainty 0.004 m. Station B installed, idle/ready/unclamped/no fault, no observed fixture part. Jaws 0.080 m, holding_visible_id null, arm inactive, negligible joint velocities, no unresolved requests. No PNG content was viewed.

Final handback a001-handback-v2, event 2778: TERMINAL COMPLETED at sim 275.710 s; dispatch observation 2731; supervisor confirmed public_resumption_conditions with next_operation transport, conventional ownership and epoch 4. This resolves the recovery activation. Two physical action requests and two explicit captures used.

Remaining normal work belongs to the conventional controller: load B2 into B fixture, recipe B process, linked passing inspection and tray2 delivery. Do not repeat prior commands or assume final delivery happened. Any future recovery requires a fresh acknowledged activation/epoch and current observations. No operator help requested.
