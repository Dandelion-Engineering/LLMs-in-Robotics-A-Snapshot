# C1 placement: order 7, authority epoch 9

Session robot-session-bf71cbeefa0d4c6b, public run RCI001-C05-final-001-block-001. Current status and focused history established robot ownership, epoch 9/order 7, C1 -> C_pad, idle equipment, open jaws and no active physical command. The prior order-4 framework record confirms handback and conventional resumption; it was historical context only. Current C1 was back at the raw source, so the previous placement was not treated as completion of this order.

## Observed outcome

Final reviewed public sequence 11474 places C1 at (0.51327213, -0.12940939, 0.01811779) m, zone C_pad, with 0.004 m reported position uncertainty. Declared half-extents (0.021,0.021,0.018) m give an orientation-independent radius 0.03472751 m. After including that radius and uncertainty, remaining XY margins are (0.00754462, 0.01368187) m. Overhead image 10880 was actually displayed and inspected; the whole C1 footprint is inside the pad.

TCP is approximately (0.27823,0.28646,0.46743) m, measured jaws approximately 0.080 m, holding_visible_id null. Arm and equipment are idle. All 14 physical requests and 15 observation requests have terminal/completed receipts. No issued request has a nonterminal or unknown transport outcome. Host per-command physical verification still says unknown; placement completion is supported by subsequent observations, geometry and the inspected image.

Handback c1-o7-handback-015 was requested through Client.handback. Its actual reply is saved in notes/c1-order7-handback.json. A preceding subprocess attempt failed locally before launching the client because sys.executable was empty, so it did not send a request. If missing or ambiguous, query this ID before any new action. A successful reply fences this epoch; separately authored framework evidence may subsequently confirm conventional resumption.

## Decisions and reusable knowledge

The initial full view, image 9685, showed C1 near (0.3805,-0.2398,0.018) m and an unoccupied C_pad. A1 was at inspection, B2 at parking2, A3 in the raw area, insert_A in fixture and insert_B at home. The previous staged route was reconsidered against these current detections, declared geometry, arm limits and host authority.

One physical command was issued per helper invocation, queried to terminal, followed by a requested capture and model review. The open-jaw route used (0.36,0.03,0.40), source XY at z=0.25,0.10,0.047,0.023. The 39-pixel partial source tag at z=0.25 shifted its estimated x by about 10 mm while the arm was well above contact; this was treated as a centroid/occlusion effect, and the full-view source estimate was retained. C1 then became occluded.

Closing while maintaining the Cartesian target z=0.023 yielded measured TCP z=0.01960 and jaw width 0.041924 m. A test lift to z=0.068 produced measured z=0.06467 with the same jaw width, supporting retention without a visible identity or private grasp certificate. The arm then lifted to z=0.18, transferred above C_pad, descended through z=0.06 to z=0.027, opened at the same target, retracted to z=0.20, and used native clear-view. That sequence restored a full C1 detection on C_pad. Actual TCP differed from targets by roughly 2-5 mm. Fixture/other tags also disappeared or shifted under arm occlusion, and reappeared in the final clear view.

This is another publicly supported C placement using the same single-command helper. These historical coordinates are not a reusable motion prescription: future invocations must revalidate source, destination occupancy, obstacles, authority, limits and outcomes. This does not establish whole-arm collision freedom or task robustness.

## Evidence map

- notes/c1-order7-initial-status.json: current activation, task, initial public detections and telemetry.
- notes/bounded-step-epoch-9.jsonl: full action intentions, protected replies, terminal receipts and before/after observations.
- notes/c1-order7-actions.json: 14 selected physical actions and all 29 terminal action/capture receipts.
- notes/c1-order7-final-evidence.json: final status, containment calculation and inspected-image publication identities.
- notes/c1-order7-handback.json: actual handback response, if sent and received.
- programs/bounded_step.py: reused unchanged after reading; no retries or automatic next physical motion, unknown outcomes require reconciliation.

Focused history windows were 9479-9503 (activation), 10036-10047 (initial image), and 11357-11368 (final image), with no reported gaps in those windows. Files are notes/c1-order7-history-activation.json, notes/c1-order7-history-initial-image.json and notes/c1-order7-history-final-image.json. Final status high-water was 11956; this is not a contiguous processed cursor.

Images 9685 and 10880 were displayed through robot_image, forwarding returned data URLs using functions image(...). Their publication events were 10039 and 11360. An image path or capture receipt alone was never treated as a viewed image.
