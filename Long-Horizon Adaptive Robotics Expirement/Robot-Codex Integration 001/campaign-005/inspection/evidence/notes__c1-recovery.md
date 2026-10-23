# C1 placement recovery — invocation robot-session-e266dd3d57e04593

Public run RCI001-C05-final-001-block-001; authority epoch 3, order version 1. Current order was C1 -> C_pad. No prior recovery notes existed. This is historical evidence, never authority or a reusable target prescription.

## Outcome before handback

Fresh clear-view detections (sequence 3545, capture simulation time 356.596 s) place C1 at approximately (0.5111, -0.1295, 0.0173) m, zone C_pad, uncertainty 0.004 m. Against pad center (0.52,-0.13), half extents 0.053, an orientation-independent part radius sqrt(.021^2+.021^2+.018^2)=0.0347 m still leaves more than 0.005 m XY margin after reported uncertainty. Overhead image 3357 was actually inspected and shows C1 wholly on the pad. Arm TCP is (0.2782,0.2865,0.4674), jaws approximately 0.080 m, holding_visible_id null, station idle, no active command.

All requested physical commands were queried to terminal. Thirteen manual commands completed; clear-view skill 017 completed. Clear-view requests 014 and 016 were rejected before dispatch for stale observation. Host command verification fields still said unknown, including in unresolved_commands: that field must not be mistaken for an executing command or proof of grasp. Final completion assessment uses subsequent public observations. Handback request c1-handback-018 is planned; consult notes/c1-handback.json and any framework terminal receipt for its actual result.

## Recovery observations and limitations

- Use python3; python and rg were unavailable in this workspace. All robot operations used robot.py Client through the protected loopback gateway. No credentials are in these artifacts.
- C1 started near (0.3805,-0.2397,0.018). Open-jaw approach targets were staged at high clearance, then z=.10, .047 and .023. Cartesian actual TCP ran approximately 2-5 mm below/behind targets. Closing using the gripper wrapper caused additional measured-position servo sag. Do not assume target equals actual pose.
- Closing width approximately .04194 and retention through a .045 m test lift supported contact with a part of the declared .042 m width. C1 remained occluded during grasp/carry, so no grasp certificate was available. After release and clear-view, C1 was detected at the destination.
- Transport retained closing command, rose vertically to .18 m, translated above C_pad, descended through .06 to .027 m target. Release held the same Cartesian target while opening, avoiding additional measured-joint hold sag. Retracted vertically to .20 before native observe(clear_view=true).
- Partial tag occlusion biased a source detection x estimate by about .010 m (39 tag pixels vs 156 initially). Do not retarget from a partly visible centroid without reconciliation; missing tags mean unobserved.
- Two stale-observation rejections occurred at the clear-view stage. They were terminal and not replayed. A later fresh status (~.082 s age) supported a new request ID, which completed. Do not weaken the .35 s admission limit or automatically retry.
- Capture receipt for the final view returned sequence 3356, but requested_image_available event 3500 identified PNG sequence 3357. The image tool used the published sequence 3357. Inspect actual publication records rather than assuming receipt and image sequence always match.
- This route is one successful simulated placement, not a whole-arm collision or task robustness certificate. Source, obstacles, authority, equipment, geometry and every stage outcome require current revalidation for future jobs. No C high-level transport skill was installed.

## Artifacts

- programs/bounded_step.py: one explicitly chosen command; query to terminal; explicit subsequent capture; full evidence log. Caller must review evidence before another invocation. No automatic motion sequence, retries, grasp claims or handback. ClientError/unknown outcomes stop; query the original ID before continuing.
- notes/c1-evidence.jsonl: full status, dispatch, receipt and acquisition records from first motion onward.
- notes/c1-final-evidence.json: final public snapshot, containment calculation and inspected-image identity.
- notes/c1-handback.json: actual handback response when written. Query c1-handback-018 if missing or ambiguous.

## Explicitly chosen actions

```json
[
  {
    "request_id": "c1-approach-mid-001",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.36,
        0.03,
        0.4
      ],
      "duration_s": 2.0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-approach-over-002",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.3805,
        -0.2397,
        0.25
      ],
      "duration_s": 2.0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-descend-high-003",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.3805,
        -0.2397,
        0.1
      ],
      "duration_s": 2.0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-descend-near-004",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.3805,
        -0.2397,
        0.047
      ],
      "duration_s": 1.5
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-grasp-height-005",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.3805,
        -0.2397,
        0.023
      ],
      "duration_s": 1.5
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-close-006",
    "action": {
      "operation": "gripper",
      "state": "close",
      "duration_s": 1.0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-test-lift-007",
    "action": {
      "operation": "move_relative",
      "frame": "world",
      "delta": [
        0,
        0,
        0.045
      ],
      "duration_s": 1.5,
      "gripper": 0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-lift-clear-008",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.37,
        -0.23555,
        0.18
      ],
      "duration_s": 2.0,
      "gripper": 0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-transfer-009",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.52,
        -0.13,
        0.18
      ],
      "duration_s": 2.0,
      "gripper": 0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-place-approach-010",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.52,
        -0.13,
        0.06
      ],
      "duration_s": 2.0,
      "gripper": 0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-place-height-011",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.52,
        -0.13,
        0.027
      ],
      "duration_s": 1.5,
      "gripper": 0
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-release-012",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.52,
        -0.13,
        0.027
      ],
      "duration_s": 1.5,
      "gripper": 255
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-retract-013",
    "action": {
      "operation": "cartesian_target",
      "position": [
        0.52,
        -0.13,
        0.2
      ],
      "duration_s": 2.0,
      "gripper": 255
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-clear-view-014",
    "action": {
      "operation": "observe",
      "clear_view": true
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-clear-view-016",
    "action": {
      "operation": "observe",
      "clear_view": true
    },
    "authority_epoch": 3,
    "order_version": 1
  },
  {
    "request_id": "c1-clear-view-017",
    "action": {
      "operation": "observe",
      "clear_view": true
    },
    "authority_epoch": 3,
    "order_version": 1
  }
]
```

History was inspected in focused windows 1-50, 581-610, and 3491-3515, each without reported gaps. Later public high-water was 3689; intervening history was not exhaustively reviewed. Do not treat this as a contiguous processed history cursor.
