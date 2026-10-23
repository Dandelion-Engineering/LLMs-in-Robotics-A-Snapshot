# Initial observation-posture screen

Prepared for the installed shared compute queue. This tool has not been launched. It is a finite common-arena calibration, not an architecture episode, training run or evaluation release. Runtime and the existing HOME remain unchanged by the tool.

The fixed grid contains 18 postures: q0 in `[-0.8, 0, 0.8]`, q1 in `[-0.5, -1.0, -1.5]`, q3 in `[-2.2, -2.6]`, with q2=q4=0, q5=1.7 and q6=0.7854. Enumeration follows that order; `posture-06` is the exact existing HOME `[0,-0.5,0,-2.2,0,1.7,0.7854]`. Every case constructs a fresh ten-part development world with world/layout seed 2 and sensor-noise seed 0. It temporarily overrides only the module HOME used during Cell construction, then restores it. It never writes object qpos or modifies object geometry, contacts or task truth.

Each case runs exactly 250 physics ticks for initial settling, holds the initial joint command, and renders one actual overhead RGB-D capture through the shared SensorWorker. This is static calibration: physics intentionally stops after the settling ticks while the copied frame is rendered. No task real-time-factor or inference-latency claim is made. The evidence keeps the initial qpos, scene XML, protected settled snapshot and initial validity, commanded and settled arm pose, joint limits, TCP public-workspace containment, final100ms maximum arm speed, finger speed/open width, and any meaningful active robot self/environment contacts during settling. A meaningful contact has penetration beyond1mm or normal force above0.1N. The tool performs no recovery or motion planning.

Predetermined eligibility requires every condition below:

- Existing protected initial-world checks pass, including stock/history, no disallowed initial workpiece overlaps and settled objects.
- Commanded and settled arm joints are inside their public allowed ranges; TCP is in the public workspace; final100ms arm speed is at most0.02rad/s; joint target error is at most0.02rad; finger speed at most0.01m/s; jaw width at least0.065m; no meaningful robot contact is observed.
- All12 registered objects are detected exactly once, with no unexpected IDs, all visible marks raw, and every independently compared center error at most4mm.
- Each declared fixed fixture/inspection/parking/tray/quarantine/insert-home footprint is fully in frame and at least98% of its depth pixels are free of foreground more than20mm above the public table plane. This test uses only public fixed-region geometry, camera calibration and image depth. It does not use object poses.

Among fully eligible cases, the recommendation uses least squared joint distance from the existing HOME, then the fixed grid ID. No outcome-driven threshold tuning or partial-score winner is allowed within this run. If none qualifies, the tool reports none. Protected pose comparisons are operator calibration evidence, never candidate inputs or an online policy oracle. Selecting a common HOME for a later revision remains a separate explicit source change and requires fresh physical manipulation/return-path/continuity calibration; this screen proves neither motion feasibility nor robust visibility across layouts.

The driver must prove installed queue ownership with the existing read-only authority helper. Each probe must prove the exact queue→driver→venv-launcher→interpreter chain and immutable parent-manifest hash. Before any physics, its actual interpreter joins a named Windows Job Object owned only by the driver. The driver applies a45-second wall cap per case (up to810seconds plus bounded setup/hash/finalization overhead for18cases); timeout terminates that owned job, including the actual interpreter. Kill-on-close also binds probe lifetime to the driver. The venv launcher is separately awaited/closed. No queue status/submission commands or unrelated process signals are used by this tool.

All Runtime Python, this folder's Python/Markdown, the reused authority helper, and every Panda asset are hashed and bundled before the first case. The manifest records the full grid, thresholds' source, fixed seeds, environment and source-bundle hash. Each child checks exact source identity before physics and afterward. The driver rechecks between cases and stops remaining cases on a source change. Fresh output directories are mandatory; every failed case retains logs/partial evidence, and no implicit retry occurs. The driver returns a summary/evidence index after all18 attempts; a successful queue exit does not mean any posture qualified. Official queue completion verification remains the root agent's responsibility.

Prepared command to submit through the existing queue (do not run directly):

```powershell
& 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\venv\Scripts\python.exe' -X utf8 -B 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Batch 01\Posture Calibration\posture_screen.py' --output 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Evidence\calibration\posture-screen-001' --seed 2
```

Freeze the covered sources/assets from queued launch through completion. Pure definition/admission/ranking tests can run without physics; actual process ownership, Job Object joining, rendering and selected-pose behavior require the queued execution. Failed physical-calibration-001 remains unchanged.
