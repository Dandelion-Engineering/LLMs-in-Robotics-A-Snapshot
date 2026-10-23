# Long-Horizon Adaptive Robotics Experiment

This folder holds the experimental arena and the record of architectures tested within it. The directory uses `Expirement`, matching Randy's requested folder name; document titles use the standard spelling.

| Start here | Purpose |
|---|---|
| [Experiment design](Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/README.md) | Task, environment, common contract, comparison methods, evidence requirements and feasibility limits |
| [Architecture Map](Architecture%20Map/README.md) | Searchable architecture descriptions, exact revisions, experiment runs/results and investigation notes |
| [Robot-Codex Integration 001](Robot-Codex%20Integration%20001/HANDOFF.md) | On-demand recovery setup, two physically checked exception families, and the unresolved native sandbox qualification gate |
| [Architecture Map playbook](../Playbooks/Architecture%20Map.md) | How to retrieve previous work and maintain reliable experimental history |
| [Batch 01](Batch%2001/README.md) | Three architectures, shared implementation, readiness and experiment progress |
| [Task & Architecture Explorer](http://127.0.0.1:8778/Task%20and%20Architecture%20Explorer/index.html) | Visual task tour, robot-stack and filesystem diagrams, four recorded examples with alternate views and synchronized LLM/file evidence |
| [Verified Investigation007](http://127.0.0.1:8778/Engineering%20Investigation%20007/site-r4-003/index.html#view=analysis) | Current local viewer: paired analysis, all264 dispositions and twelve fixed recorded timelines |
| [Session4 results](../agents/Codex/Session%20Summaries/HumanReport4.md) | Outcomes, denominators, uncertainty, retained failures and exact provenance |

The design package moved here on 2026-09-22 from the project root. Older chat messages and completed work records retain the original path as historical context. Current links and literature material-use pointers resolve to the new location.

**Current direction:** on 2026-09-22 Randy authorized three architectures and then clarified that this includes complete experiments and every required implementation step. Batch 01 supersedes the earlier design-only boundary. Proposed mechanisms, implementation readiness, development evidence and scored results remain distinct. The earlier primitive simulator probe is a feasibility check, not an architecture experiment.

On September 26 Randy requested a separate subscription-authenticated Robot-Codex recovery setup. Session 8 completed a bounded development attempt and two reference-recoverable exception fixtures. Model launch remains blocked at native Windows isolation qualification; no Robot-Codex pilot or scored campaign ran. See the integration handoff before treating its implementation as an available experimental condition.

This map is a record for Randy and the development agent. It does not prescribe the robot's own persistent filesystem and must not expose evaluator evidence or held-out information to a running candidate.

## Completed Batch01 and local viewer

All264 planned dispositions are accounted for:263 normal terminals and one administrative interruption with unknown physical outcome. Whole-block exclusions leave253 eligible records. Persistent task successes were baseline43/46, A1 0/46, A2 0/46 and A3 45/46. The baseline–A3 interval includes zero; this does not establish general superiority. See the results report for the full nine contrasts and limits.

The current presentation is `Engineering Investigation 007/site-r4-003/index.html`. It keeps Runtime004, Recovery001, Analysis005 and Investigation005/006 provenance distinct. Older viewers and failed build directories remain historical artifacts; avoid opening the785MB Investigation006 page.

The current server binds only127.0.0.1:8778. If it is no longer running, start it from this experiment folder with the project interpreter:

```powershell
& '..\venv\Scripts\python.exe' -X utf8 -B -m http.server 8778 --bind 127.0.0.1
```

Then open the linked Investigation007 viewer. Leave the server running while inspecting evidence. Use a375px or wider pane; a narrower header may scroll horizontally. Search includes provenance matches. Large raw evidence and generated packages stay intact locally and are excluded from Git; a fresh clone needs the retained local evidence to rebuild or inspect full trace payloads.

Production and browser verification are recorded in `Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation007-003-complete.json` and `investigation007-browser-qa-001-complete.json`. The former's browser-pending field records its earlier build-only checkpoint; the later QA record supplies the result. No new physical runs are needed for this completed batch.

## Visual task and architecture tour

Randy's September 26 report request is fulfilled in [Task and Architecture Explorer](Task%20and%20Architecture%20Explorer/README.md). It explains the actual workcell and all four stacks, then replays the predeclared C01 examples. The baseline and A3 finish; A1 and A2 remain honest incomplete examples. The reconstructed camera angles use recorded joint/object poses, and an additional camera mode shows original overhead imagery. Exact model inputs, outputs and historical checkpoint writes follow the selected time. No new simulations or architecture changes were made.

Use the same local server above. The original experiment chat remains active at Randy's request; the completed report is ready for discussion.
