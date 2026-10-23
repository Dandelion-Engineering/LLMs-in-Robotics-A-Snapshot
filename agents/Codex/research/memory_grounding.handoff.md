# Memory, grounding and cognitive connections lane handoff

Completed 2026-09-18 (America/Los_Angeles). Parent owns integration, workflow and lock.

- `memory_grounding.papers.jsonl`: **34 records**, each with exactly 27 top-level fields; 27 abstract-reviewed and 7 full-text-skimmed. No complete-paper reads claimed.
- `memory_grounding.searches.jsonl`: **22 actual query/source/synthesis events**. Queries, unsuccessful lookups, alternate access, selected IDs and deferred candidates are recorded.
- PowerShell JSON parsing: 34/22 records readable, no duplicate IDs, no wrong field counts, no dangling selected-paper references. Parent's canonical validator remains necessary.

## Orientation and important qualifications

**CoALA (arxiv:2309.02427)** provides the most direct framework vocabulary: memory components, internal/external actions and a decision process. Current arXiv v3 is TMLR camera-ready (2024); abstract and author companion overview reviewed. This classifies choices without selecting our framework.

**ConceptGraphs (arxiv:2309.16650)** is the clearest grounded interface: posed RGB-D becomes objects/captions/bounds; GPT-4 chooses targets; navigation/grasping machinery executes; camera observations can trigger search elsewhere. Author PDF II-A/C/D, III-A/C/D/E/F/H and A6 inspected. Caption errors, missed small objects and API costs are real qualifications. Compare dense VLMaps/ConceptFusion, implicit CLIP-Fields, hierarchical HOV-SG/Hydra, dynamic DovSG and task-selective Clio.

**KnowNo (arxiv:2307.01928)**: Sections 2, 3.1-3.2 and 6 are useful. Conformal help requests have conditional assumptions: calibrated task distribution, fully grounded text, executable successful low-level actions, and faithful human clarification. The completion guarantee is not a general safety guarantee.

**REFLECT (arxiv:2306.15724)**: Sections 3-5 distinguish history summarization, explanation and correction planning. Simulation has oracle object/state detection; physical failure records were teleoperated UR5e demonstrations. Do not present the dataset as autonomous physical recovery coverage.

**RoboMemory (arxiv:2508.01415)** changed title in v7 to “Interactive Environmental Learning” (2026-03-24). I first skimmed v1, then resolved current v7 methods/evaluation. It combines persistent stores with planner/critic, LoRA-finetuned pi0 and SLAM. v7 III-D, IV-F, Algorithm 1 and Appendix E4 expose dependencies: 15 physical tasks each repeated, first action skips critic to avoid loops, low-level training is still needed. Brain-region labels are engineering analogies. Article banner is CC BY-NC-SA 4.0; no inference made about code licenses.

**From Language to Action (arxiv:2603.03148)** supplies valuable counterevidence. III-A/C and IV-A/E describe oracle textual perception, simplified attach/detach grasping, fixed layouts and inconclusive memory effects on task success. Hallucinated success can enter episodic memory. Model latency findings are configuration-specific.

Recent memory coverage includes **MEMORA v2** (2026-08-31, author-stated EMNLP acceptance) and **MessyMem v2** (2026-09-15, author-stated CoRL acceptance). Both remain abstract-reviewed. MessyMem's headline figure is simulation task progress, not a physical success percentage.

**A-Lab (doi:10.1038/s41586-023-06734-w)** must use its corrected title “inorganic materials” and current 36/57 abstract. The complete 2026-01-19 correction was inspected: novelty wording revised, four identifications inconclusive, one training-data overlap removed. The correction is attached to the original record, not counted separately. Coscientist's original full artifacts remain withheld in the inspected publisher statement; its public implementation is simplified. ChemCrow's public implementation contains only 12 of 18 reported tools. These are adjacent lab evidence, not proposed [lab name redacted] tasks.

Non-LLM/biological contrasts include KnowRob, Soar, ACT-R, complementary learning systems, hippocampal prospective sequences, optimal feedback control and a mobile robotic chemist. Computational interpretations, biological evidence and engineering analogies are explicitly separated.

## Gaps and integration notes

Broad discovery stopped after distinct alternatives and recurring families were represented. Gaps remain in tactile/proprioceptive state fusion, uncertain/stale memories, interruption/crash recovery, forgetting, multi-day physical persistence, independent equal-cost comparisons, user burden, small-lab affordability and commercial artifact licensing. No exhaustive/saturation claim beyond searches performed.

Direct Nature opens failed on publisher identity redirects; indexed primary text and author/institutional copies supplied content. PubMed direct opens sometimes returned no text; targeted indexed abstracts were recovered. CLS author PDF and a KnowRob PDF follow-up timed out; neither is claimed full-text-read.

All source access dates are actual local 2026-09-18. A few stable IDs use verified DOI/arXiv identities; `knowrob-2009` uses an author-verified title identity with DOI left unresolved. Material-use arrays are initially empty: add actual events for claims used in the final Discovery Map, rather than treating corpus import as a reading event. Do not copy this handoff as a standalone report.

