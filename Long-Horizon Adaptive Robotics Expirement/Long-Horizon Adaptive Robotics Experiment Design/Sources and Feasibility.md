# Sources, feasibility and unresolved boundaries

Evidence inspected on **2026-09-22**. Commercial and literature source checks were bounded Codex subtasks, integrated here. This document distinguishes source reports, engineering choices and actual local observations. It contains no architecture recommendation.

## Commercial evidence

The central playbook was read before using the map. The central map and its playbook were **read only**; no records, views or maintenance outputs were changed. The current local input is [CP-003 in problems.jsonl](</C:/Users/cresp/Documents/Dandelion Engineering/Dandelion Engineering/Commercial Physical AI/problems.jsonl:3>) and [A-006/A-007 in sources.jsonl](</C:/Users/cresp/Documents/Dandelion Engineering/Dandelion Engineering/Commercial Physical AI/sources.jsonl:6>). Central HEAD was `948961472193c39fa92c4ea6f3f9e3c80f28b183`. File hashes below identify inspected bytes independently of Git state.

| Input | SHA-256 |
|---|---|
| `problems.jsonl` | `362eea13ba5b1b99971ce9fd7b85827aec514e76a35a15040aad6746f9a18a78` |
| `sources.jsonl` | `ca937703c3aa386cfa72918fe78b7a12ed6c01adc8e479788b67ccc7eae13310` |
| `searches.jsonl` | `4df9f41d1c28a92902ffae4b152a284bec1e6452b43b5b2d8856a9a8108a53f3` |

These hashes matched before and after the commercial-source inspection; scoped central Git status was clean. No consequential map error needing central follow-up was found. Future proposed corrections belong in this package for the central Dandelion agent, never as edits from this project.

| Source | Actually inspected and what it supports | Limit / use here |
|---|---|---|
| **CP-003 / A-006**, [Universal Robots: WST Fab](https://www.universal-robots.com/case-stories/wst-fab/) | Undated vendor-hosted customer account; “In short,” “How they did it,” “Complete package,” “3D printed grippers.” Installed tending, job adaptation and integrated handling are described. | Testimony, not independent reliability/cost evidence. Grounds an existing physical workflow and a strong conventional incumbent. |
| **CP-003 / A-007**, [Intrinsic, 24 June 2025](https://www.intrinsic.ai/blog/posts/unveiling-next-generation-solutions-built-with-intrinsic) | “Bringing AI to the CNC markets”: stock perception and grasp/motion planning in an Automatica demonstration. | Demonstration and vendor capability claims, not production uptime or proof of LLM value. Grounds job-change flexibility as relevant. |
| **CP-005 / A-012**, [FamilyMart, 10 August 2022, p.1](https://www.family.co.jp/content/dam/family/company/news_releases/2022/20220810_newsrelease_1.pdf) | Customer announcement of beverage-replenishment rollout intent. | Historical plans are not a current installed-base count. Retail is a credible alternative, but shelf-capacity dependencies would need stronger modeling. |
| **CP-004 / A-009**, [NIST assembly task boards](https://www.nist.gov/el/intelligent-systems-division-73500/robotic-grasping-and-manipulation-assembly/assembly) | Landing-page descriptions of routing, cable reacquisition and harness completion; linked CAD/protocols not inspected. | Demonstrated competencies/task definitions are not autonomous factory deployment. Cable physics would dominate an early continuity experiment. |
| **CP-019 / D-001**, [Opentrons Northwestern interview](https://opentrons.com/archives/customer-stories/opentrons-user-interview-with-northwestern-university) | Vendor-hosted researcher account of manual tracking ambiguity and existing liquid-handling automation. | Relevant history dependence; sample contamination and recovery would be materially simplified in rigid-body simulation. |

Choosing CP-003 over these alternatives is **engineering judgment** about experimental tractability and dependent work. It is not a company-strategy change or proof of a superior commercial opportunity. Quarantine/rework and particular order amendments in the arena are our constructed scenarios. The map's commercial evidence, physical-intelligence interpretation and Dandelion feasibility remain separate.

## Selective literature use

Local corpus lookup preceded external reading. Five existing records were materially used; no new paper discovery batch or architecture selection was needed. The canonical records retain source locators and material-use entries for this package. Four records advance from abstract review to selective full-text skim; Inner Monologue retains abstract-reviewed paper depth. None was completely reviewed or replicated.

| Record and original | Reading scope | Consequence for this design |
|---|---|---|
| **CALVIN**, `arxiv:2112.03227`, [v4 PDF](https://arxiv.org/pdf/2112.03227v4) | III-A/C, task criteria, Figures 6/8. Feasible five-task chains, 1,000 evaluation chains, neutral initialization and sensor-based policies with independent state-based predicates. | Feasible start states, full-chain and partial outcomes, split environments. Finite chains do not establish persistent-world process restart or unpaused wall time. We do not provide automatic evaluator-selected next subtasks. |
| **DoReMi**, `arxiv:2307.00329`, [v2](https://arxiv.org/html/2307.00329v2) | 4.1–4.4 and 5.1, Table 2/failures. Disturbance injection, explicit detector cadence and execution-time/success evaluation. | Separate event, detection, response and physical recovery; count misses/false alarms and timeouts. This reading does not establish full network/model delays advancing alongside physics. |
| **DovSG**, `arxiv:2410.11989`, [v2](https://arxiv.org/html/2410.11989v2) | IV-A–E, Tables I–III and conclusion. Two consecutive tasks; manual scene changes made observable during the first; human evaluation. | Test visible versus out-of-view changes and stale records separately. Two-task continuity is not runtime restart; grasping differences confound attributing all gains to memory. |
| **OpenVLA-OFT**, `arxiv:2502.19645`, [v2](https://arxiv.org/html/2502.19645v2) | IV-B, V-A/C and Table II, VI-A–D and Table III, appendix tables. Action/chunk generation latency and throughput differ from the 25 Hz ALOHA execution loop using 25-action chunks. | Separate observation age, inference time, action horizon and end-to-end response. A100 query timings are not this desktop's measurements. Table units are used where prose units conflict. No model adoption follows. |
| **Inner Monologue**, `arxiv:2207.05608`, [author page](https://innermonologue.github.io/) | Approach/Results/Emergent Capabilities text, not videos. PDF access failed at the tool's size limit. | Label feedback as sensed, inferred, human-provided or evaluator-derived. Detailed paper counts and oracle boundaries remain unverified by this pass. |

Lookup nonmatches for BEHAVIOR, LoHoRavens, real-time action chunking and VIMA do not establish absence of relevant literature. No benchmark is adopted wholesale. These papers informed evaluation distinctions, not the set of future architectures.

## Simulator and embodiment alternatives

| Choice | Verified basis | Decision |
|---|---|---|
| **MuJoCo 3.14.0** | [Official release](https://github.com/google-deepmind/mujoco/releases/tag/3.14.0), [Python API](https://mujoco.readthedocs.io/en/stable/python.html), native CPython 3.12 Windows wheel and local probe below | Selected CPU-first physics; harness must provide timing, isolation, observations and task semantics. New release means exact pin and narrow validation matter. |
| **PyBullet 3.2.7** | [PyPI metadata](https://pypi.org/pypi/pybullet/json), [official quickstart](https://github.com/bulletphysics/bullet3/blob/master/docs/pybullet_quickstart_guide/PyBulletQuickstartGuide.md.html) | Capable fallback, but current release metadata had no Windows wheel or CPython 3.12 wheel; source/older-runtime setup adds friction. DIRECT mode does not acquire real-time behavior merely from the realtime flag. |
| **Webots R2025a** | [Robot synchronization](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/robot.md), [Supervisor](https://github.com/cyberbotics/webots/blob/R2025a/docs/reference/supervisor.md) | Fuller Windows application alternative; more setup and explicit synchronous/asynchronous timing choices for one cell. |
| **Isaac Sim** | [5.0 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.0.0/installation/requirements.html) | Screened out initially: published minimum includes 32 GB RAM, 16 GB VRAM and RTX 4080-class GPU. This shared host differs; not a claim Isaac cannot run. Rich rendering is not the first bottleneck. |

Panda model: [Menagerie pinned README](https://github.com/google-deepmind/mujoco_menagerie/blob/822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7/franka_emika_panda/README.md), [XML](https://github.com/google-deepmind/mujoco_menagerie/blob/822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7/franka_emika_panda/panda.xml), [model-specific license](https://github.com/google-deepmind/mujoco_menagerie/blob/822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7/franka_emika_panda/LICENSE). Commit `822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7` was inspected; the simplified model has seven arm actuators and coupled finger actuation. License file SHA-256: `a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9`. No Panda assets were installed or tested in the bounded probe. It supplies a plausible simulation starting point, not a validated complete robot model or affordable physical bill of materials.

## Host and actual bounded check

Live snapshot: Windows 11 Home build 26200; Ryzen 7 8700F, 8 cores/16 logical processors; approximately 31.67 GiB visible RAM and 15.83 GiB free; RTX 5060 Ti with 16,311 MiB VRAM and 1,115 MiB in use; approximately 577.8 GiB free on C:, 262 GiB on D: and 220 GiB on E:. Project Python is 3.12.10 x64. These are instantaneous observations, not reserved resources; future work must check capacity again.

The previously minimal project venv now contains `mujoco==3.14.0` and its resolved dependencies, pinned in [requirements.txt](../../requirements.txt). The CPython 3.12 Windows MuJoCo wheel listed SHA-256 `d1777cd426f9155bed514d2362c74d6456df784bb84b00759bc253b64564e92c` in official package metadata. The actual probe ran locally for seconds, not as sustained workload, and used a self-authored falling box only.

Reproduce from the project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Long-Horizon Adaptive Robotics Experiment Design/probe/simulator_probe.py'
```

The [saved result](probe/result.json) records **passed** contact, RGB/depth render, deterministic integration-state restoration (maximum absolute difference 0.0 in this exact test) and physics advancement during a mock two-second unavailable inference worker (1,003 ticks, 2.006 simulated seconds in approximately 2.006 wall seconds). The [rendered frame](probe/probe-frame.png) was visually inspected. This is not an arm/grasp test, full-cell benchmark, model call, timing guarantee or sandbox test. The mock wait is explicitly synthetic. The script and model hash make the check reproducible.

[MuJoCo state documentation](https://mujoco.readthedocs.io/en/latest/programming/simulation.html) informs checkpointing: integration state does not include our machine ledger, RNG, event scheduler, IPC, filesystem or mutable model edits. Application snapshots and model/assets hashes are required for the later replay harness.

Sustained simulations and inference must use the shared queue, for example:

```powershell
.\venv\Scripts\python.exe -B 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py' submit --project 'LLMs in Robotics' --cwd 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics' -- <executable> <arguments>
```

This is a command template, not a launched job. Record job IDs, require queue success/exit 0 and validate run identities, manifests and outputs separately. Schedule one candidate at a time. No training, architecture comparison, paid APIs, new accounts or hardware purchases occurred.

## Reuse terms for the resources actually considered

MuJoCo core and the pinned Panda model carry Apache-2.0 terms. Installed-version license inspection supports the present local simulation work; it does not clear a future redistributed product. Preserve package notices and pins. The installed MuJoCo core license hashes to `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`; its third-party notice hashes to `aec5167579b94d6926340175b4f764b5159f4933657556d89bbfb8238d3b3eb8` under `venv/Lib/site-packages/mujoco-3.14.0.dist-info/licenses/`.

The inspected dependency terms are Apache-2.0 (absl-py/etils), BSD-3-Clause (fsspec/websockets), MIT (Python glfw/zipp), PSF terms (typing_extensions), NumPy BSD core with bundled notices, and PyOpenGL BSD-style core with separately licensed libraries. Native GLFW 3.4 uses [zlib terms](https://github.com/glfw/glfw/blob/3.4/LICENSE.md), not its Python wrapper's MIT license.

Material future-distribution issues: MuJoCo includes Eigen MPL-2.0, Qhull notices and OFL fonts; NumPy bundles OpenBLAS/LAPACK and GCC runtime under GPL with GCC runtime exception; PyOpenGL includes FreeGLUT and GLE with distinct terms. PyOpenGL's installed wheel omits its full top-level license; the exact [3.1.10 source archive](https://files.pythonhosted.org/packages/6f/16/912b7225d56284859cd9a672827f18be43f8012f8b7b932bc4bd959a298e/pyopengl-3.1.10.tar.gz) license was inspected in memory (license SHA-256 `d37ec6e00a4f88bf80ec0b7b3b9dbea88534c1c66c2f529dc64c7c02e07a6a1b`). Bundled Microsoft runtime redistribution requires a separate [rights check](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170). These details do not prohibit the current local probe, but cannot be erased by a generic “open source” label. No future models, training data, perception package or robot hardware terms are covered by this check.

## Unresolved questions and next gates

| Question / confound | What resolves it, and when |
|---|---|
| Does this job capture the ambition Randy wants? | Review the concrete episode and dependencies now. Task choice is proposed for review, not a market commitment. |
| Is the actual Panda workcell reachable and contact-stable? | Later common-arena implementation: load pinned model, verify safe trajectories/fixtures, ordinary grasp/drop/reseat behavior and nominal baseline completion. Minimal box probe does not settle this. |
| Can image-derived tag poses meet the shared sensing contract? | Prototype/calibrate the shared perception service before scoring; retain sensor-only success claims. A simulator-derived fallback must be a separate labeled track. |
| Can full physics/cameras/inference maintain wall time on shared hardware? | Queue a combined load pilot after model choices; freeze honest rates and quotas before comparative tuning. |
| Can evaluator state be protected from candidate/generated code on Windows Home? | Validate an isolation backend and attempted boundary violations before protected evaluation. Same-user native processes are insufficient. |
| Are exact action adapters comparable? | Calibrate torque/position/trajectory semantics and limits on identical body; publish common services and report matched-executor diagnostics where attribution requires them. |
| Are failures attributable to continuity rather than recognition or poor grasping? | Use paired persistence controls, sensor/exec traces and matched component diagnostics; report full-system gains separately. |
| Are timing/caps/storage practical? | Shared development pilot determines final constants and compressed log rates. Revise before freeze, never after seeing a desired winner. |
| Does the processing proxy predict factory throughput, quality or safe operation? | It cannot establish those claims. Future physical access, designed hardware and real process evidence are required and separately authorized. |
| Which local model or architecture fits? | Deliberately unresolved. Architecture design follows Randy's review; no candidate set or LLM placement is proposed here. |

The design is ready for that review. These are implementation/calibration gates for a later phase, not evidence that experiments have already been built or run.
