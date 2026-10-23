# Task and Architecture Explorer

[Open the report](http://127.0.0.1:8778/Task%20and%20Architecture%20Explorer/index.html).

The three views explain the actual machine-tending task, the conventional robot stack and each LLM boundary, and four recorded C01 examples with synchronized model and checkpoint evidence. This is the visual report Randy requested in the project chat on September 26, 2026. It supplements [Investigation007](../Engineering%20Investigation%20007/README.md); it does not replace the batch analysis or create another evaluation.

## Open locally

The existing loopback server serves the experiment folder at port 8778. If it is stopped, run this from **the experiment folder**, then leave it running while using the report:

```powershell
& '..\venv\Scripts\python.exe' -X utf8 -B -m http.server 8778 --bind 127.0.0.1
```

The report loads local evidence on demand, so open the loopback link rather than double-clicking the HTML with `file://`. No CDN, external service, model server or network inference is needed. The page does not modify evidence or run physics.

## What to explore

- **The job:** a spatial workcell diagram, the two-A/one-B order and six linked processing stages. A1, A3 and B2 are example stock IDs, not names of additional required order types.
- **Inside the stack:** choose the conventional baseline, A1 action chooser, A2 guarded-program composer or A3 motion adviser. Blocks show conventional sensing, state handling, decisions, motion planning, joint control and device services. Branch labels expose paths that bypass the model. Select a block to inspect its actual connections.
- **Watch a run:** choose an entrant; play at 1×, 4× or 12×; scrub or jump between model exchanges. Switch among perspective, overhead, front and side reconstructions or the actual recorded overhead camera. Drag a reconstruction to orbit. Inspect exact request components, raw model output and the latest historical checkpoint.

The baseline has no LLM. A1 chooses an action; A2 emits a bounded guarded action list; A3 supplies bounded transport parameters to a conventional task sequencer. The framework creates and replaces `/work/candidate-state.json`. None of these models has direct filesystem tools or a Collaboration Station chat/work-claim workflow. The diagrams show the smaller mechanism that was actually implemented.

## Recorded examples and limits

The four C01 replicate-1 persistent slots come from the predeclared twelve-trace selection, declared September 23 before held-out seeds and scored outcomes. This report uses the same nominal case for all entrants and keeps its failures.

| Entrant | Accepted parts | Terminal outcome | Model calls |
|---|---:|---|---:|
| Baseline | 3/3 | Success | 0 |
| A1 | 2/3 | Partial at time cap | 32 |
| A2 | 1/3 | Partial at time cap | 9 |
| A3 | 3/3 | Success | 9 |

A1 and A2 had zero successes among 46 eligible persistent trials each in the completed batch. Their C01 examples still contain inspectable physical actions, model responses and saved state; no replacement success was fabricated or sought. No new simulation was needed. These four examples are not a new aggregate comparison or proof of why a mechanism succeeded or failed. Full denominators, exclusions, uncertainty, administrative interruption and timing diagnoses remain in [HumanReport4](../../agents/Codex/Session%20Summaries/HumanReport4.md) and Investigation007.

### Reconstruction versus observation

- Original RGB frames are actual recorded overhead imagery. This text model received structured detections and selected state, not camera pixels.
- Alternate viewpoints are simplified shaded geometry from recorded arm joint values (5 Hz retained motion) and privileged evaluator object/gripper snapshots (about 1 Hz). They are operator explanations, never candidate input. No physics is recomputed.
- Samples are held until the next recorded sample. Robot and object ages are displayed separately. Different sample ages can temporarily separate a held object from the pictured gripper. No intervening trajectory or collision-free path is inferred.
- Panda forward kinematics uses the frozen XML transforms. Shapes, table extent, part colors and zone/rack labels are schematic. Object orientations use the recorded freejoint quaternions. Finger openings use recorded snapshot joints.
- A settled recorded pose agrees with the XML-derived tool center within 0.487 micrometers. Across the A3 C01 raw motion stream, logged tool-center versus joint-derived positions differ by 0.258 mm on average and at most 1.881 mm; both are preserved, with a separate recorded tool-center marker. This check validates the coordinate reconstruction, not dynamics or controller quality.

### Model and file time boundaries

Requests are matched to responses by their original parent event IDs. Output appears only after its recorded response time. No streamed-token or hidden reasoning trace is inferred. Model proposals, gateway admission and physical outcomes remain separate.

Historical checkpoint content is taken from authenticated `context_write` events, never from the final on-disk file. File-operation times are the supervisor's receipt time for an enclosing reply; individual write times were not recorded. Changed fields are top-level state differences, not causal attribution to the LLM. C01 contains no runtime restart or `context_read`; the architecture view explains implemented restart behavior without presenting this run as a restart demonstration.

The physical endpoint is identified by the final-world event ID. Cleanup can share its simulation timestamp, so event ordering excludes later cleanup. Simulation time is kept separate from measured wall duration. Original late events remain in source data.

## Sources and reproduction

- [architectures.json](architectures.json): graph descriptions, implementation boundaries and source line references. Referenced Runtime004 files were checked against the frozen r4 code bundle. Later recovery administration is not presented as a new policy or model.
- [scene.js](scene.js): source-linked Panda transforms, renderer and geometry limitations. Panda XML SHA-256: `96ad67da03710f17f798c9478fd9e9efdf24a3bf8359f05e456dd9fb158ea273`.
- [data/index.json](data/index.json): exact episode hashes/sizes, selection declaration and original Investigation007 package identity.
- [build_data.py](build_data.py): reads the original authenticated Investigation007 codec packages and makes small display projections plus content-addressed exact payloads. It does not read all raw streams or import the simulator.
- [temporal.js](temporal.js): shared no-future-evidence and endpoint-selection helpers.
- [qa.json](qa.json): source-bound validation and browser checks for this report.

Run from the repository root with the retained local Investigation007 `site-r4-003` package available:

```powershell
& '.\venv\Scripts\python.exe' -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/build_data.py'
& '.\venv\Scripts\python.exe' -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/validate_report.py'
node 'Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/test_temporal.js'
node 'Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/test_scene.js'
node --check 'Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/app.js'
```

The four projected episode files total about 23 MB, with another 10.84 MB in 1,373 deduplicated exact payloads. Generated data remains local under `data/`; its compact index is versioned. Original frames are linked from retained evidence rather than copied. A Git clone alone does not contain those raw/generated assets. No old trace, frozen source, result, canonical map entry or original viewer was rewritten.
