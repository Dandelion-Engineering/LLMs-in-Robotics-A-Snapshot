# LLMs in Robotics: discovery map

## Current use — 2026-09-22

Randy authorized experiment design after the initial discovery checkpoint. The [design package](../Long-Horizon%20Adaptive%20Robotics%20Expirement/Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/README.md) proposes small-batch machine tending in simulation, with an embodiment and architecture-neutral evaluation contract for review. Five existing records informed its measurements and controls; four now have selective full-text skims. Runtime model, LLM placement and competing architectures remain undecided. This update is bounded material use, not a reopened broad search or an adopted candidate architecture.

## Initial discovery orientation — 2026-09-18

The useful question is **what information changes which part of the robot's behavior?** An LLM can interpret a goal, choose an existing skill, write a program, specify a cost or constraint, help train a policy, or become part of a learned action model. Those choices impose different sensing, control, memory and compute requirements. At the initial checkpoint no first task, embodiment, runtime model or architecture had been selected. The current experiment-design proposal is linked above; this literature orientation does not select its architecture.

<!-- BEGIN GENERATED CURRENT METRICS -->
**Current corpus: 102 unique papers; 102 abstract-or-deeper reviewed.**

Review depth: discovered: 0; abstract_reviewed: 82; full_text_skimmed: 20; full_text_reviewed: 0; deep_read: 0.

Latest recorded paper-source access: 2026-09-22.

| Area | Papers (overlap allowed) |
|---|---:|
| Robotics stack architectures | 52 |
| Planning, reasoning and skills | 28 |
| Code generation and tools | 17 |
| Perception, state and grounding | 25 |
| Memory and continuity | 28 |
| Closed-loop adaptation | 33 |
| Learning and skill acquisition | 45 |
| Embodiment transfer | 22 |
| World models and prediction | 9 |
| Deployment, evaluation and safety | 30 |
| Human and laboratory assistance | 16 |
| Neuroscience and cognitive connections | 9 |

Canonical SHA-256: `96eb7bda47bb97628372b33c750eee171672ae52d240cf99491f02674b51aafb`.
<!-- END GENERATED CURRENT METRICS -->

These are record counts, not a reading assignment or a measure of scientific confidence. Most sources support triage. The [Catalog](Catalog.md) groups papers; the [README](README.md) provides focused lookup; [Use Checks](Use%20Checks.md) demonstrates what the saved records can answer. Full records identify source editions, access dates and limits.

## From an instruction to movement

Consider “put the mug away.” Something must locate the mug, decide where it belongs, determine a feasible approach, move the arm, and notice whether the mug was actually placed. A fluent plan supplies only some of those functions. The table is a **literature synthesis**, not a selected system or a ranking across tasks.

| Architectural route | What crosses the language-model boundary? | What moves the robot and closes the loop? | Evidence and important boundary |
|---|---|---|---|
| Select existing skills | Instruction/history → a skill choice, constrained by feasibility | Learned or scripted skills; subsequent state/feedback can inform another choice | [SayCan](https://arxiv.org/abs/2204.01691), [Inner Monologue](https://arxiv.org/abs/2207.05608). Motor competence comes from the skill repertoire; feedback quality remains consequential. |
| Generate an executable program | Instruction and API descriptions → code that reads observations and calls actions | The generated program can contain its own feedback loop; perception/control APIs supply capabilities | [Code as Policies](https://arxiv.org/abs/2209.07753). New program structure is possible, but perception and control interfaces still bound behavior. |
| Specify geometry or objectives | Instruction plus scene information → value maps, costs or keypoint constraints | Numerical optimization and a controller update motion from observations | [VoxPoser](https://arxiv.org/abs/2307.05973), [ReKep](https://arxiv.org/abs/2409.01652). A fast control loop need not query the LLM every tick; tracking and model assumptions remain. |
| Translate to a formal planning problem | Language → structured goals/constraints; checks feed corrections back | Symbolic/task-and-motion solvers search for feasible plans, then controllers execute them | [LLM+P](https://arxiv.org/abs/2304.11477), [AutoTAMP](https://arxiv.org/abs/2306.06531), [PDDLStream](https://arxiv.org/abs/1802.08705). A sound solver cannot repair an incorrectly specified world by itself. |
| Learn an action-producing model | Images, language and possibly robot state → action predictions | A trained policy emits actions/chunks; the deployment loop supplies fresh observations | [OpenVLA](https://arxiv.org/abs/2406.09246). Compare with [Diffusion Policy](https://arxiv.org/abs/2303.04137); task-specific imitation remains a serious alternative. Data, body interfaces and evaluation conditions matter. |
| Use the LLM while developing skills | Simulator code/task → reward or randomization configuration | Reinforcement learning produces the deployed policy | [Eureka](https://arxiv.org/abs/2310.12931), [DrEureka](https://arxiv.org/abs/2406.01967). No LLM weight update does not mean no policy training. |

Multimodal language models such as [PaLM-E](https://arxiv.org/abs/2303.03378) address how observations enter reasoning; this is a separate choice from what ultimately controls motion. A [behavior tree](https://arxiv.org/abs/1709.00084) offers modular reactive task switching without an LLM. These pieces can coexist, but this assignment adopts none of them.

## Memory and prediction are several different jobs

An execution history, a persistent user preference, a reusable code skill, a map, and updated model weights preserve different things. [TidyBot](https://arxiv.org/abs/2305.05658) generalizes preferences; [Voyager](https://arxiv.org/abs/2305.16291) stores executable skills in a game. Neither alone establishes months of reliable physical-world memory. Retrieve `memory_continuity` for spatial and episodic approaches and their access/edition qualifications.

[From Language to Action](https://arxiv.org/html/2603.03148v1) is useful counterevidence: its simplified simulated tasks show inconclusive memory effects, and the authors identify mistaken success reports as a possible contaminant of stored episodes. Memory needs evidence about what happened, not just persistence.

Prediction is similarly varied: a symbolic action model, a simulator, learned contact dynamics, a latent visual predictor, and an LLM predicting teaching interactions are not interchangeable. DrEureka uses simulator engineering; VoxPoser includes an optional dynamics-learning study; [LMPC](https://arxiv.org/abs/2402.11450) learns from human teaching interactions. Their evidence does not establish one general physical world model.

Cognitive and neuroscience entries supply mechanisms and alternative organizing ideas. Biological replay and complementary learning systems are evidence about biological/computational memory, not validation of a robot memory design. The distinction is preserved in each record.

## Nine optional ways into the original work

Choose whatever raises a useful question; this is not a curriculum. Section/figure suggestions below are limited to material actually inspected. Demonstrations linked from author pages remain author evidence; no robot was replicated here.

| Start with | Why open it? | Inspected entry point and limit |
|---|---|---|
| [SayCan](https://say-can.github.io/) | See language relevance and robot feasibility as different signals. | Author abstract/system explanation and dated update. PDF fetch exceeded the tool limit; no full-paper reading claimed. |
| [Code as Policies](https://arxiv.org/pdf/2209.07753v4) | See the concrete program between words and motion. | Sec.III/III-A and Fig.1 caption, then Sec.V limitations. The code still relies on supplied APIs. |
| [ReKep](https://arxiv.org/html/2409.01652v1) | Follow an instruction through keypoints, constraints and an optimizer. | Fig.2 caption and Sec.3.1–3.3, then Sec.4.3/5 on tracking failures and fixed stages. |
| [Voyager](https://arxiv.org/abs/2305.16291) | Examine what persistent procedural memory actually stores. | Primary abstract: curriculum, executable skill library and error-driven revision. Minecraft transfer is not physical body transfer. |
| [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427) | Organize memory, action and decision processes when thinking about an agent framework. | Primary-source reading basis is in its record. This is an architectural synthesis, not evidence of a deployed thinking robot. |
| [OpenVLA](https://arxiv.org/abs/2406.09246) | Explore learned image/language-to-action policies and where a simpler policy can win. | Selective methods/evaluation reading is recorded. Compare task scope before interpreting success differences. |
| [V-JEPA 2](https://arxiv.org/abs/2506.09985) | Ask what prediction learned from video contributes to physical planning. | Selected robot-control sections in the record; camera setup, inference time and goal format constrain interpretation. |
| [Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners](https://arxiv.org/abs/2307.01928) | Treat asking a person as an explicit decision with measurable burden. | Selected KnowNo methods/assumptions in the record. Guarantees depend on the stated grounding/action/help assumptions. |
| [PDDLStream](https://arxiv.org/abs/1802.08705) | Understand a conventional way to combine task structure and geometry. | Primary abstract reviewed; methods are a future reading target. No LLM is required by the method. |

## What could mislead us

**A plausible plan is not an executable plan.** [PlanBench](https://arxiv.org/abs/2206.10498) and the [critical planning investigation](https://arxiv.org/abs/2305.15771) challenge direct planning claims. Their historical model results should not be projected onto all current models, and their symbolic tasks are not physical deployments.

**Published claims can change.** The [2026 A-Lab correction](https://www.nature.com/articles/s41586-025-09992-y) narrowed novelty wording and revised product-identification claims. The original paper's record includes that correction; the headline is not treated as independent confirmation of an autonomous laboratory capability.

**Public code may implement a different input contract from the physical experiment.** The official [VoxPoser README](https://github.com/huangwl18/VoxPoser) uses simulator object masks; the pinned [ReKep README](https://github.com/huangwl18/ReKep/blob/63c43fdba60354980258beaeb8a7d48e088e1e3e/README.md) supplies tracking/mask/SDF information from simulation. Those releases omit parts of the physical perception pipeline. The corpus records the distinction and artifact revisions.

**Open access is not blanket commercial permission.** Resource checks cover a limited selection of code/model licenses. VoxPoser's pinned repository license is MIT, but this does not settle simulator, asset or model/API terms. ReKep reuse remains unresolved after the requested root LICENSE file returned404. Read the artifact-specific findings in `provenance_notes.resources` and `robotics_context.reuse_and_licensing`. No complete stack has been cleared for adoption or tested on this host.

## Coverage, recurrence and remaining questions

Discovery combined foundational name/phrase searches, mechanism searches, primary citation trails, selective methods reads, and a deliberate 2025–2026 pass. The exact query batches, source-access events, deferred candidates and failures are in [searches.jsonl](searches.jsonl). Access dates are actual local dates; first publication/preprint and inspected revisions are separate metadata. Unpinned indexed editions are explicitly qualified.

The inspected code/planning reference trails repeatedly led back to represented skill-selection, executable-program, scene-graph, geometric-cost and external-verifier families. Recent searches added small/onboard-model and newer evaluation/memory variations. This is bounded conceptual recurrence within our searches, not an exhaustive or systematic-review saturation claim. Useful coverage across the major areas is enough to stop broad discovery and let Randy explore.

The most consequential unresolved areas are:

- Long-term memory under stale observations, interrupted tasks, conflicting corrections and mistaken success reports; persistence alone is insufficient.
- Tactile/proprioceptive grounding and contact-rich interaction beyond the mainly visual/spatial examples; category coverage is not modality completeness.
- End-to-end local latency, memory use, maintenance effort and total cost on the actual host. Nothing was benchmarked or installed here.
- Cross-body reuse after calibration, reachability and action-interface changes; multi-robot training and new-body transfer are different claims.
- Complete artifact/dependency/data/asset terms suitable for commercial use, and affordable lab tasks with realistic user burden. Laboratory examples are adjacent evidence, not a [lab name redacted] request.
- Broader recent-literature coverage and deeper primary failure analysis. Very recent preprints, partial author lists, unverified final venues and selective reading remain visible limitations.

Useful later explanations could compare program feedback with LLM replanning, trace a failed action through memory repair, or show what transfers when a robot's body changes. Randy will choose which questions deserve deeper reports and which capability to engineer.

## Historical checkpoints

### 2026-09-18 — initial map

The initial discovery assignment established the reusable corpus, retrieval/validation tools, orientation and maintenance integration. Reference locations/revisions/hashes are recorded in [tool reference notes](../agents/Codex/research/tool-reference-notes.md). Current counts above are regenerated from canonical records; the initial session's fixed counts and checks are preserved in [HumanReport1](../agents/Codex/Session%20Summaries/HumanReport1.md).

**Stop boundary:** the initial discovery assignment is complete. Wait for Randy's discussion before additional broad searching, architecture selection, model/data downloads, training or implementation of a first robot task.
