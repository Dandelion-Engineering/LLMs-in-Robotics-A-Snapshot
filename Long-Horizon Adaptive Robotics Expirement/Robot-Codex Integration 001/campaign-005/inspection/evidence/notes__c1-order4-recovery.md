# C1 placement, order 4, epoch 6

Session robot-session-1b6d999793b246f6; run RCI001-C05-final-001-block-001. Current public order was C1 -> C_pad; authority was robot, epoch 6/order 4, with no active physical action. Historical epoch-3 motions were all terminal, though host verification remained unknown. History confirmed order 4 release and new recovery authority. No past note was treated as authority.

## Outcome before handback

Public snapshot sequence 7622 locates C1 at (0.51444,-0.12947,0.01752) m, zone C_pad, uncertainty 0.004 m. Declared half-extents (.021,.021,.018) give orientation-independent radius 0.03473 m; adding uncertainty still leaves XY containment margins (0.00871,0.01375) m inside C_pad. Actual overhead image 7375 was inspected and shows C1 entirely on the pad. TCP is approximately (0.27823,0.28646,0.46743) m; jaws approximately .080 m, holding_visible_id null. Equipment and arm resource are idle, no active command or nonterminal unresolved request.

Thirteen manual Cartesian actions and native clear-view action completed, each queried to terminal and followed by explicit capture. No rejected or unknown-outcome request occurred in this invocation. Host per-command physical verification still says unknown; the completion assessment comes from subsequent public observations, not receipts alone.

Handback c1-o4-handback-015 is planned. Its actual response will be saved in notes/c1-order4-handback.json. If absent or ambiguous, query that ID before another action. An accepted handback fences off this epoch; consult current status and any separately authored framework receipt for later conventional resumption.

## Recovery and reuse

Current source was observed near (.38047,-.23976,.018), with A1 at inspection and B2 at parking2. Initial overhead image 5809 showed source and clear C_pad. The prior staged route was reconciled against these detections and the changed A/B occupancy. Approach targets were (.36,.03,.40), then source XY at z=.25,.10,.047,.023. These are historical choices, not prescribed future targets.

Closing held the same Cartesian target at z=.023 while setting gripper 0, avoiding the measured-joint hold sag seen with the gripper wrapper in the previous invocation. Measured TCP was about (.37686,-.23834,.01960); width .041924 m. A test lift to the same XY at z=.068 measured z=.06467 with the same width, supporting retention. C1 remained occluded during grasp/carry, so no visible identity or grasp certificate was available. A partial source tag previously shifted estimated x by 10 mm with only 39 pixels; the full-view source estimate was retained rather than treating that centroid shift as physical motion.

The arm rose to source XY,z=.18, translated to (.52,-.13,.18), descended through z=.06 to .027, opened while holding that target, and retracted to z=.20. Native observe(clear_view=true) then cleared the camera. Final public observations support successful placement. Target and measured TCP differed by 2-5 mm throughout. This route is two successful public-evidence C placements across invocations, not task robustness or whole-arm collision qualification.

## Durable artifacts and interface details

- notes/c1-order4-initial.json: initial public status and current authority/order.
- notes/bounded-step-epoch-6.jsonl: full before/after observations, command intent, dispatch and terminal/capture receipts.
- notes/c1-order4-actions.json: compact action list and all terminal receipts, including captures.
- notes/c1-order4-final-evidence.json: final status, conservative footprint calculation and inspected-image identities.
- notes/c1-order4-handback.json: actual handback response, if sent and received.
- programs/bounded_step.py: improved to separate evidence by authority epoch and support capture-only calls. It still issues only one selected physical command, stops on unknown outcome, never retries, and requires caller review before the next motion. Status display omits terminal older-epoch entries, but full logs and command-admission precondition review retain them. Client-initialization errors use notes/bounded-step-client-errors.jsonl. First-invocation evidence stays in notes/c1-evidence.jsonl.

History was inspected in focused windows 5171-5195 (activation), 5991-6005 (initial image) and 7684-7698 (final image), all without reported gaps. High-water at final review was 7935; these are not a contiguous processed cursor. Full windows are notes/c1-order4-history-activation.json, notes/c1-order4-history-initial-image.json and notes/c1-order4-history-final-image.json.

Use python3. C1 and C_pad still require bounded manual controls. For images first reconcile requested_image_available; robot_image returns a metadata JSON line followed by a data:image/png;base64 URL string in this environment. Forward the URL via functions image(...) to actually inspect pixels. Merely printing base64 is not an image inspection. Both initial 5809 and final 7375 were displayed as images; metadata and PNG identity are recorded. Preserve the distinction between camera acquisition, image publication, terminal action receipt and observed outcome.
