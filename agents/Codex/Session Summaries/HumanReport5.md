# Session 5 — Visual task and architecture explorer

September 26, 2026. Randy reopened the experiment chat and requested a new visual HTML report explaining the actual task, all architectures, their robot-stack and filesystem-framework schematics, and a watchable simulation with camera choices and current model/file activity. The report is complete.

[Open the explorer](http://127.0.0.1:8778/Task%20and%20Architecture%20Explorer/index.html). [Sources, reproduction and limits](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Task%20and%20Architecture%20Explorer/README.md) are in the report folder. The existing loopback server at port 8778 serves both this report and Investigation007; its restart command remains in the experiment README.

## What is usable

The job view establishes the small-batch machine-tending task with a spatial workcell, family/count order and six linked stages. The architecture view separates conventional perception, state reconciliation, task decisions, motion planning, joint control and device services. A1 selects actions; A2 generates bounded guarded programs; A3 supplies transport parameters while a conventional sequencer chooses job operations. The baseline has no model. Visible bypass routes preserve common recovery, program reuse and non-transport behavior.

The continuity schematic shows the actual checkpoint mechanism: candidate Python runtime reads and atomically replaces `/work/candidate-state.json`; it assembles selected fields into model context. The model has no file tools. This is not a copy of Collaboration Station chats/work claims or a semantic procedure library.

The replay uses the same four predeclared C01 replicate-1 persistent examples. Baseline and A3 accept 3/3 parts and finish; A1 accepts 2/3 and A2 1/3 at the 300-second cap. The full persistent batch remains A1 0/46 and A2 0/46. The report keeps those failures, with 32 A1, 9 A2 and 9 A3 model calls available for inspection. No new simulation, inference or scoring run was needed.

Controls include play/pause, speed, time scrubbing, call jumps, four reconstructed viewpoints, drag orbit and the original overhead camera. Exact request components and raw output are synchronized to recorded time. Historical checkpoint contents and changed fields show where host-managed writes occurred. The original Investigation007 remains the entry point for all twelve selected traces and statistical analysis.

## Verification and limits

- All 15 temporal regression tests pass, including backward seeking, future responses and same-time cleanup exclusion. Scene tests pass all four views at 375/640px canvas widths; settled forward-kinematic tool-center error is 0.487 micrometers.
- Data validation verifies the four episode hashes, 1,273 unique direct model/checkpoint/event payloads, source paths and 5,070 referenced RGB/depth assets. The extraction separately checked every selected model request/response and all 2,535 RGB frame paths. The output contains 1,373 unique lazy payload files; the validator count is its stated inspected subset, not a claim that every file is covered there.
- Browser checks at 375×900 and 1280×900 covered navigation, every task stage/architecture, all four examples, camera modes, playback, keyboard scrubbing, model components, payload and checkpoint disclosures, and backward seek clearing. No document overflow or console warning/error was observed. [qa.json](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Task%20and%20Architecture%20Explorer/qa.json) binds tested source hashes.
- Alternate cameras are simplified reconstructions using 5 Hz retained robot samples and about 1 Hz privileged object/gripper snapshots. Sample ages are visible; differing sample times can temporarily separate a held object and gripper. These are operator views, not candidate observations or newly rendered physics video.
- The file-event timestamp is supervisor receipt, not an individually measured write time. C01 has no restart or recorded checkpoint read. Stored state, supplied context and causal influence remain distinct.
- No causal explanation, revised architecture, additional scientific result or real-world reliability claim is introduced. Runtime004 source facts were checked against the frozen r4 bundle; recovery administration and previous analysis provenance remain intact.

## Retention and closeout

Report source, the compact generated-data index and QA are versioned under `Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/`. About 23 MB of episode projections and 10.84 MB of exact lazy payloads remain local under its ignored `data/` paths. They can be regenerated from the retained Investigation007 package with `build_data.py`; original frames remain linked. A clone alone lacks the full source evidence and generated assets. Frozen runtime files, canonical maps, outcomes, analysis and prior viewers were not changed.

The human's pre-existing Concluded→Active transcript change and removal of its old conclusion summary are preserved. The chat stays active as explicitly requested. Session claims are moved to `Work/Done` before final Git closeout. The final tool result establishes commit/push status; this pre-commit report does not assert publication. After successful closeout, only the newly owned session lock is removed.

This report assignment is complete. Continue with Randy's next direction in the active experiment chat; do not start another campaign simply because a new automated session begins.
