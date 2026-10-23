# Learning, transfer and evaluation research handoff

2026-09-18 local access date. Bounded Codex helper; root owns integration and closeout.

Delivered **36 paper records** and **11 search/source-access events** in the neighboring JSONL files. Depth: **32 abstract-reviewed; 4 full-text-skimmed**; no full-paper/deep-read claims. All records have 27 top-level fields, unique stable arXiv IDs and dated source entries. A local parse/count smoke check passed; root's complete validator remains the integration check.

Coverage overlaps: learning 33, deployment/evaluation 18, embodiment transfer 15, architectures 20, world models 4. This lane complements the other agents; it is intentionally strongest on manipulation. CrossFormer adds navigation, locomotion and aviation evidence without pretending those fields received deep coverage.

## Useful orientation and cautions

- Direct VLAs: RT-2 → OpenVLA / pi family / SmolVLA / GR00T. Action tokens, flow/diffusion heads and deployment scheduling are different engineering choices; a VLM backbone does not itself identify where control competence originates.
- Conventional learned alternatives: ACT, Diffusion Policy, DP3, BC-Z; flexible generalist initialization: Octo/HPT/CrossFormer. Target demonstrations, action interfaces and embodiment adaptation remain important.
- Predictive alternatives: DreamerV3, UniPi, UniSim and V-JEPA2. Predicting videos/features, selecting actions and executing with feedback are separate mechanisms.
- Evaluation: CALVIN/LIBERO/RoboCasa365 (simulation), SIMPLER (paired sim/real correlation), VLA-REPLICA (physical reproducibility), and the 2026 physical-reasoning position paper (an argument about identifiability, not a replicated negative result).

Selected original-paper entry points:

1. [ACT](https://arxiv.org/abs/2304.13705): abstract-reviewed conventional low-cost imitation baseline.
2. [OpenVLA](https://arxiv.org/html/2406.09246v3): inspected Section 5.2 and Figure 5 for the narrow-task versus multi-instruction comparison; Section 6 for original model limitations.
3. [SmolVLA](https://arxiv.org/html/2506.01844v1): Section 3.3 / Algorithm 1 for scheduling; Section 4.3 separates single-GPU trainability from reported project training and synchronous main physical evaluation.
4. [V-JEPA2](https://arxiv.org/html/2506.09985v1): Sections 3.2 and 4.3 connect predictive planning with practical limitations. Camera placement was manually explored; goal images/subgoals and planning latency matter.
5. [SIMPLER](https://arxiv.org/html/2405.05941v1): Section III-A explicitly targets relative policy performance, with scoped limitations in Section VII.

The detailed summaries are deliberately compact. Root should preserve source word budgets when adding overview prose: do not repeat numeric aggregates or turn abstract reports into project-validated results. No test established model fit, speed, simulation compatibility or training feasibility on the user's host.

## Reuse evidence

Artifact-specific checks are recorded in paper sources/context with pinned revisions:

- OpenVLA code declares MIT; official README explicitly says weights inherit Llama2 Community License. No blanket commercial approval for weights/data.
- SmolVLA base model-card revision declares Apache-2.0. This check does not establish community dataset or hardware terms.
- V-JEPA2 code declares MIT with specified Apache-2.0 exceptions. Weights/data not separately audited.
- LIBERO code declares MIT. Dataset/third-party assets not separately audited.

Links to associated author resources are retained under provenance_notes.linked_resources. A hyperlink is not a reading or license-verification event.

## Remaining gaps and stopping rule

Recent discovery includes 2026 continual VLA fine-tuning, physical benchmarking, evaluation criticism, RoboCasa365 and a September 17, 2026 compact-VLA distillation preprint. The latter is very recent and abstract-only. The pi0.6/RECAP searches returned third-party forks/notes without resolving an authoritative primary paper; it was left deferred. Other explicit deferrals: VLA-Arena, ForesightSafety-VLA, V-JEPA2.1 and the original RoboCasa paper. No title-only candidates were promoted to abstract-reviewed records.

Current arXiv revisions were verified. Most year fields intentionally use first-preprint year, with later version dates in metadata; pi0 uses verified RSS2025 publication year while retaining 2024 origin and 2026 revision. Diffusion Policy v5 explicitly describes itself as the extended journal version of the RSS2023 work. Final-publication metadata remains incomplete elsewhere.

Stop this lane at this discovery checkpoint. Recurrent VLA/data/action-representation themes were encountered within the recorded searches; this is neither exhaustive nor systematic saturation. No architecture, robot task, runtime or hardware purchase was selected. No training, model/data download, robot actuation, external contact or publication occurred.

