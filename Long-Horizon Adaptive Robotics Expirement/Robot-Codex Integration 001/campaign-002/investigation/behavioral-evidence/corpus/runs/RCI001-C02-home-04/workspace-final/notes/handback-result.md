# Activation result
Run episode-d1f9382645d34f29; activation-001; invocation pilot-34c49d80fd4a; order version 1.

Recovery completed: pilot34-clear-a1-v1 moved A1 from insert_home_A to parking1; pilot34-setup-b-v1 installed insert_B and returned insert_A home. Both queries were terminal completed and subsequent structured observation 2518 confirmed the placements, idle ready station and open empty gripper. See committed Continuity.md for detailed evidence and the first rejected handback.

Authoritative reply for pilot34-handback-v2: ok=true; command phase=terminal, status=completed; request_event_id=2840; requested_sim_time_s=282.34600000062005; terminal_sim_time_s=282.3520000006201; owner=conventional; authority_epoch=4; verification state=public_resumption_conditions, next_operation=transport. Request envelope used fresh observation_sequence=2797 under old epoch3/order1. No further physical action requested after handback.

After successful handback, read-only status and attempted continuity publication were denied by the service. The continuity attempt explicitly returned invocation_capability_denied. No retry or capability change was attempted. Thus Continuity.md remains the valid pre-handback note; notes/next-continuity.md contains the intended post-handback update but was NOT committed. This file preserves the received transition locally and does not grant authority.

Remaining uncertainty: conventional productive action and final order delivery were not observed after handback. One recipe-B part with cycle-linked passing inspection must still reach tray2. Recovery success and protected handback are established; final order completion is not claimed. No help or waiting request remains necessary for this resolved recovery activation.
