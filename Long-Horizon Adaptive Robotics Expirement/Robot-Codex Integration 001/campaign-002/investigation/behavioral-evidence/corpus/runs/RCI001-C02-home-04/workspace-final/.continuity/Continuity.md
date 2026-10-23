# Recovery continuity
Run episode-d1f9382645d34f29; activation-001; invocation pilot-34c49d80fd4a; current acknowledged owner robot, epoch 3, order version 1; incarnation 3/restart generation 0.
Last reviewed event: 25 (history 1-25 inspected, no gaps). Later evidence below is from authoritative query/status; intervening history not reviewed.

Order: one family B part, recipe B, tray2, no rework. Conventional setup B was rejected three times as destination occupied (events 5,10,16). A1 was observed obstructing insert_home_A.

Resolved recovery:
- pilot34-clear-a1-v1 (request event 1002): native transport A1 to parking1, terminal completed sim 120.310 s; observed-effect sequence 1179. Fresh status 1346 confirmed placement and empty open gripper. Explicit acquisition pilot34-verify-clear-v1 completed with sequence 1469.
- pilot34-handback-v1 (request event 1786) was terminal rejected unsupported_resumption at sim 178.308 s: frozen conventional controller lacked supported next action. Ownership stayed robot/epoch3.
- pilot34-setup-b-v1 (request event 2048): native setup B, terminal completed sim 237.210 s; observed-effect support sequence 2347. Fresh status 2518 captured 254.332 s, age 0.122 s when read, confirms insert_B at fixture [0.5718,0,0.0083] m world; insert_A at insert_home_A [0.1875,-0.2493,0.0083]; A1 raw on parking1; B2 raw in raw area. Station reports insert B, idle/ready/unclamped/fault-free, no seated part. Jaws 0.080 m with no visible held object, idle arm, no active or unresolved commands. Two physical action requests used of 20. Structured evidence only; PNG pixels not inspected.

Next: submit protected handback pilot34-handback-v2 (planned, not yet submitted), for conventional loading B2 into compatible fixture, recipe B cycle, linked passing inspection and tray2 delivery. No processed/delivered count claimed. If response uncertain query ID before another request. If accepted authority changes: do not actuate under old epoch. If rejected inspect reason and retain actual ownership; no replay of resolved actions.
