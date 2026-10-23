# Recovery continuity
Run episode-bdc6255ebbf04d98; activation activation-001; invocation pilot-f0551b8dc129. Owner robot, epoch 3, order v1, incarnation 3, restart generation 0, confirmed status 2403 at sim 242.836 s.
Last reviewed event: 5. Focused events 18-25 also reviewed. Initial history response 1-35 truncated; subsequent state reconciled via authoritative status/query, not full history sweep.

Order: one B part, recipe B, eligible cycle and linked passing inspection, tray2; max rework 0. No final order completion claimed.
Incident: conventional setup(B) repeatedly rejected destination occupied (latest c9d9ff6b-260b-4253-8c23-9a146a888b8e), assistance event 19. A1 was observed on insert_A's required home pad.

Resolved actions: a001-clear-insert-home-a-v1 (event 933) moved A1 to parking1, terminal completed sim 113.266 s, outcome confirmed by structured detection at sequence 1247. a001-handback-v1 (event 1654) was terminal rejected unsupported_resumption at sim 165.156 s; controller still lacked supported next action, ownership stayed robot. Therefore a001-setup-b-v1 (event 1968) performed native setup B, terminal completed sim 229.100 s, gateway public observation support sequence 2266. Explicit after-setup capture a001-after-setup-capture-v1 (event 2389) completed at sequence 2349. All requests are resolved.

Latest physical evidence read: status sequence 2403, capture sim 242.768 s, returned age 0.068 s. Structured RGB-D shows insert_B at fixture [0.57194,0,0.00726] world metres, insert_A at insert_home_A [0.18733,-0.24953,0.00726], A1 at parking1 and B2 still raw. Detection uncertainty 0.004 m. Station reports installed family B, ready/idle, unclamped, no fault and no observed part in fixture. Jaws approximately 0.080 m, holding_visible_id null, no active arm resource, negligible joint velocities. No active/unresolved commands. PNGs have not been viewed. Two of 20 action requests used; two explicit captures completed.

Assessment: obstruction removed and required insert exchange physically supported by observations. Conventional next step should be loading raw B2 into the now compatible fixture.
Next step: planned handback a001-handback-v2, not yet submitted. Cite changed setup state and observations; query ID before any retry after uncertain response. Success is supervisor-confirmed conventional ownership/new epoch. Remaining production: B2 load, recipe B processing, linked passing inspection, tray2 delivery; these remain conventional work after accepted handback.
