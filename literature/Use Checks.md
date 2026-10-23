# Using and checking the initial map

2026-09-18 checkpoint. These are bounded retrieval demonstrations and source checks, not a system evaluation. Start with the [README commands](README.md); the exact executed arguments, exit codes, match counts and returned IDs are saved in [retrieval-checks.json](../agents/Codex/research/retrieval-checks.json).

## Six practical questions

Use `lookup '<text>' --json` or `lookup --id '<stable ID>' --json` after the Python/script prefix documented in the README. Category filters retrieve a broader group; keywords are not exhaustive capability annotations.

| Question | Focused retrieval | What the saved evidence can support |
|---|---|---|
| When is the LLM used? | `--tag development-time-llm`; `--id arxiv:2209.07753`; `--id arxiv:2204.01691` | Eureka/DrEureka develop policies through training; SayCan selects skills during deployment. Code as Policies generates executable logic that can itself react to observations. Code generation and per-tick LLM inference are different. |
| What memory persists? | `--category memory_continuity`; `Voyager`; `RoboMemory` | Voyager stores executable skills in Minecraft. RoboMemory uses persistent stores with planner/critic and a trained action policy. Neither establishes arbitrary cross-body or multi-month physical continuity. |
| What observations reach reasoning? | `--id arxiv:2309.16650`; `privileged`; `--id arxiv:2603.03148` | ConceptGraphs converts RGB-D into object descriptions/geometry. From Language to Action reads simulator state. The pinned VoxPoser/ReKep demo resources also expose simulator information; inspect the specific interface before comparing systems. |
| How does feedback change behavior? | `--category closed_loop_adaptation`; `--id arxiv:2409.01652`; `--id arxiv:2306.15724` | ReKep updates optimized motions from tracked geometry. REFLECT turns histories into failure explanations/correction plans; its physical failure recordings came from teleoperation. A recovery plan is not automatically demonstrated autonomous recovery. |
| What transfers physically or across bodies? | `--category embodiment_transfer`; `CrossFormer`; `--id arxiv:2506.09985` | CrossFormer reports shared policies across multiple robot families. That differs from zero-training transfer to any new body. V-JEPA 2's two-lab Franka deployment retains camera, goal and action-interface constraints. |
| What prevents immediate reuse? | `licensing`; `--id arxiv:2406.09246`; `--id arxiv:2409.01652`; `SmolVLA` | OpenVLA code and weights have distinct terms. ReKep's requested root license was not found. SmolVLA's model-card declaration does not clear every dataset/dependency. No stack's fit, speed or commercial reuse was validated on this host. |

The lookup results are entry points to records and original sources. A matching word is not a positive experimental finding; an absent word is not negative evidence.

## Bounded source sample

In addition to the source reading recorded by the three research lanes, the integrating Codex agent independently revisited eight varied records. Actual URLs and inspection scopes are preserved in each record and the `integration-source-sample-01` search event.

| Record | Primary material checked | Consequence for the map |
|---|---|---|
| OpenVLA | v3 Section 5.2 / Figure 5 discussion | Keep narrow-task comparisons and differing observation/action interfaces visible. |
| V-JEPA 2 | v1 Sections 4.2–4.3 excerpts | Keep planning latency, manual camera placement and image-goal limitations; reported timing is not host performance. |
| KnowNo | v2 Sections 2 and 3.1–3.2 assumption excerpts | Help guarantees remain conditional on task calibration and the stated execution/help assumptions. |
| From Language to Action | v1 Section IV memory-result discussion | Preserve inconclusive task-success effect and authors' memory-contamination interpretation. |
| CoALA | Primary abstract and v3 header | Distinguish original 2023 preprint from 2024 camera-ready version; retain framework rather than deployment evidence. |
| A-Lab | Complete January 2026 publisher correction | Preserve changed novelty wording and revised identification claims in the original record. Main article remains abstract-reviewed. |
| Aggressively pruned VLAs | September 17, 2026 primary abstract/header (`arxiv:2609.19579`) | Verify very recent identity/date; retain abstract-only depth and unresolved reproduction costs. |
| Physical-reasoning position | Primary abstract/header (`arxiv:2606.30686`) | Treat the evaluation-identifiability claim as an argument, not a proof that all VLAs cannot reason. |

Earlier focused root inspections covered Code as Policies, VoxPoser, DrEureka, ReKep and PlanBench. Artifact checks covered selected pinned code/model declarations, not full dependency trees. Primary access failures, unpinned indexed editions, shortened author lists and unresolved final venues remain recorded. This sample did not authenticate every record or replicate any result.

## Mechanical verification

All 23 regression checks passed at the initial checkpoint. They cover malformed records, identity collisions, robotics vocabulary, filtering and preservation of editorial notes during regeneration. All 21 documented/example CLI retrieval invocations succeeded then, including text, stable ID, verified alias, category, tag and combined category/status lookup. [validation.json](validation.json) is regenerated on later corpus changes and binds structural and generated-view checks to canonical file hashes. Source checking and structural validation answer different questions; neither establishes exhaustive coverage or that a robot will work.

## Experiment-design use — 2026-09-22

Five existing records informed the [long-horizon experiment design](../Long-Horizon%20Adaptive%20Robotics%20Expirement/Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/README.md). CALVIN v4, DoReMi v2, DovSG v2 and OpenVLA-OFT v2 received bounded methods/evaluation skims and substantive evidence/limitation updates. Inner Monologue's author-page text was inspected; PDF access failed at the tool's size limit and its paper reading depth remains abstract-reviewed. Exact source locators, implications and limits are in the design source notes and canonical records. The new source-access event records actual local retrieval and original access, not a broad discovery search. No paper was fully reviewed or reproduced, and no implementation/model was selected from these papers.

Views and structural validation were regenerated after this material-use update. Helper/schema code did not change; historical regression results above are not presented as new experiment validation.

## 2026-09-22 experiment folder relocation

The design package moved under `Long-Horizon Adaptive Robotics Expirement/`. Five existing `project_artifact` pointers and current navigation links were updated to the relocated files. This is a path-maintenance change only: no new source reading, material use, architecture proposal, or experimental result is implied. The original access dates, reading depth and evidence remain unchanged.
