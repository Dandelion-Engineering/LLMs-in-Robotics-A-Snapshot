# Initial Literature Map



---

**Randy (2026-09-18 20:39 PDT):**

Hey Codex! I'm very excited to work on this project with you! Let's get started.


# Initial Task — Literature Map, Playbook, and Project Integration

Codex, we are starting **LLMs in Robotics**, an engineering-first Dandelion Engineering project.

I want to explore putting an LLM somewhere in a robotics stack, possibly with a framework resembling Collaboration Station, to create a robot that thinks. I am interested in reasoning, observations, memory, code generation, adaptation, and capabilities that might transfer across compatible bodies. These are directions to investigate, not a selected architecture.

**Build the literature map, make it usable, create its maintenance playbook, and edit Project Details to include it.**

The purpose is to help me understand what others have built, read important original papers, generate ideas, and then choose a compelling capability to engineer. Do not select our first task, embodiment, runtime model, memory design, or LLM placement in this assignment.


## 1. Reuse the existing literature-map structure

Use the **Vision project, whose working title is “Efficient Visual Processing for Physical AI,”** as the primary read-only structural reference for the literature map(C:\Users\cresp\Documents\Dandelion Engineering\Vision\literature).

The second reference is **[private project name redacted]**:

```text
[private project link redacted]
```

Its `literature/README.md`, `literature/Schema.md`, and `Playbooks/Literature Map.md` document the same shared **Vision schema 1.0** core and the `[lab name redacted]-lc-1.0` adaptation. Use an accessible local copy or the authorized repository connection. Read only the literature-map structure, tools, and small representative records needed for this task—not unrelated lab data or analyses.

Inspect the reference README, schema, playbook, a few paper/search records, and the lookup, generation, and validation tools. Record the actual reference location and revision or file hashes used. If one reference is unavailable, use the other and the explicit specification below; report the limitation without making discovery wait indefinitely.

**Reuse the organization and common field meanings, not their contents.** Do not copy their paper counts, topics, reading events, search history, instructions, or scientific claims. Do not modify either reference project. Upload suffixes such as `(1)` or `(8)` are not repository filenames.

## 2. Build this file layout

```text
literature/
    README.md
    papers.jsonl
    searches.jsonl
    Schema.md
    Catalog.md
    Discovery Map.md
    validate_corpus.py
    validation.json

Playbooks/
    Literature Map.md
```

Keep the established responsibilities:

- `papers.jsonl`: canonical paper records, one JSON object per physical line.
- `searches.jsonl`: actual discovery, citation-trail, metadata, and source-access provenance.
- `Schema.md`: shared fields/types, reading levels, identity rules, and a documented robotics profile.
- `Catalog.md`: generated category index with year, linked title, importance, and review-depth shorthand. Category counts can overlap.
- `Discovery Map.md`: current coverage and orientation, important alternatives, limitations and gaps, with dated historical checkpoints kept distinct.
- `validate_corpus.py` and `validation.json`: repeatable structural/consistency checks and fresh results tied to the canonical file hashes.
- `README.md`: entry points, responsibilities, and working retrieval/update commands.

Reuse small helper tools where useful. [private project name redacted] uses `corpus.py` for lookup and view generation and `test_corpus.py` for regression checks; compatible equivalents are welcome. Do not make a database, embeddings service, new MCP, or new orchestration framework a prerequisite. Use the existing search tools and local files.

## 3. Map the design space broadly

Search the literature available at execution time, including foundational work and a deliberate pass for recent developments. Record the search dates and distinguish original publication, preprint revision, and retrieval dates.

Use these as **open seed categories**. Add, merge, or split them when the literature warrants it, keeping the schema, tools, catalog, and coverage consistent. Cross-tagging is appropriate; equal category sizes are not required.

| Suggested category | What to investigate |
|---|---|
| `robotics_stack_architectures` | Where LLMs sit relative to perception, state estimation, planning, skills, learning, and control; modular, hierarchical, hybrid, and end-to-end/VLA designs; useful conventional alternatives and cognitive architectures. |
| `planning_reasoning_skills` | Task decomposition, language grounding, skill selection, task-and-motion planning, behavior trees, feasibility constraints, and executing multi-step instructions. |
| `code_generation_tools` | Executable policies, tool use, program synthesis, reusable routines, code revision from feedback, and changing goals or controller parameters. Distinguish development-time code generation, runtime programs, and modification during action. |
| `perception_state_grounding` | How images, video, depth, touch, proprioception, and structured observations reach the reasoning system; scene graphs, spatial maps, object state, uncertainty, and grounding language in actionable geometry. |
| `memory_continuity` | Working, episodic, semantic, procedural, and spatial memory; retrieval, consolidation, forgetting, confidence, stale-state correction, interruptions, task resumption, and persistence across sessions or environments. |
| `closed_loop_adaptation` | Observation-action feedback, success/failure detection, replanning, recovery, changing environments, uncertainty, deciding when to observe again, and requesting human assistance. |
| `learning_and_skill_acquisition` | Demonstrations, imitation, reinforcement learning, LLM-generated rewards/curricula, skill libraries, adaptation without weight updates, and combinations of learned and conventional methods. Identify what still requires training. |
| `embodiment_transfer` | Reusing task knowledge, memories, programs, and skills across arms, mobile robots, and other bodies; action interfaces, calibration, body models, reachability, changed dynamics, and honest transfer limits. |
| `world_models_prediction` | Predicting action consequences, model-based planning, imagined rollouts, environment models, and the connection between language reasoning and learned or conventional physical prediction. |
| `deployment_evaluation_safety` | Local versus remote inference, latency and scheduling, computational cost, small models, reproducibility, benchmarks, privileged information, human intervention, failure coverage, runtime checks, and evidence of physical rather than only simulated success. |
| `human_lab_assistance` | Teaching and correcting robots, reusable procedures, long-horizon assistance, laboratory automation, and affordable tools for small labs. Include evidence about user burden and operating constraints; do not assume [lab name redacted] has requested any specific task. |
| `neuroscience_cognitive_connections` | Relevant principles from memory, replay, predictive sensorimotor processing, motor control, attention, uncertainty, and cognitive architectures. Distinguish biological evidence, computational interpretations, and engineering analogies; no requirement to reproduce biology. |

Do not let “LLM robotics” collapse into only task planning, only robot foundation models, or only memory. Include approaches that challenge the usefulness of an LLM in a given role. Follow references and alternative terminology beyond these categories when they reveal a materially different approach.

A broad corpus on the order of **100–150 useful papers** is a reasonable scale guide, not a quota or hard minimum. Prioritize meaningful architectural coverage and counterevidence over count. Most records can be abstract-reviewed or selectively skimmed; inspect deeper where an important distinction depends on methods, an experiment, or a failure case. Do not claim to have read full papers merely because their PDFs were accessible.

Stop broad discovery when the major areas have useful coverage and targeted follow-up searches increasingly revisit represented approaches. Explain remaining gaps and conceptual recurrence within the searches performed; do not claim an exhaustive or systematic review. Preserve a usable partial result if access prevents coverage rather than padding the corpus or searching indefinitely.

## 4. Preserve the shared record schema

Keep the same **27 top-level paper fields** and their reference types:

```text
id, identifier_aliases, title, authors, authors_complete, year, venue,
doi, url, open_access_url, categories, tags, paper_type, review_status,
basis_for_summary, central_idea, efficiency_targets,
representation_or_method, task_or_domain, evidence_or_evaluation,
main_limitations, project_relevance, importance, sources,
metadata_notes, discovery_lane, provenance_notes
```

In particular, `identifier_aliases`, `authors`, `categories`, `tags`, `basis_for_summary`, and `efficiency_targets` are string lists; `authors_complete` is Boolean; `year` is an integer; `sources` is an object list; `provenance_notes` is an object. Keep the reference string/null conventions. Every source object includes `url`, `material_reviewed`, and actual `accessed_date`.

Keep `paper_type` values `method`, `experimental`, `theoretical`, `review`, and `benchmark`. Keep these reading levels:

- `discovered`: identity/relevance established, but no primary abstract or equivalent content responsibly reviewed.
- `abstract_reviewed`: primary abstract or equivalent author/publisher summary inspected.
- `full_text_skimmed`: selected full-text sections inspected and named.
- `full_text_reviewed`: the complete paper reviewed at ordinary research depth.
- `deep_read`: sustained scrutiny of methods, arguments, controls, and implications.

Preserve verified identities and aliases, author completeness, actual source editions, reading basis, and access limitations. Deduplicate a preprint and final publication of the same work without collapsing distinct follow-up studies. Priority means usefulness for retrieval or later reading, not endorsement. A title-only snippet is not abstract review; a review's description of an experiment is not inspection of that primary experiment.

Document an **`llm-robotics-1.0` profile derived from Vision core 1.0**, following LC's approach to domain adaptation. Change category vocabularies, not common semantics. Allow `efficiency_targets: []` when a paper is not about efficiency; do not relabel memory quality, safety, or task success as efficiency merely to satisfy a field.

Put robotics-specific qualifications inside optional `provenance_notes.robotics_context`, not new top-level fields. Useful optional members include:

```text
llm_role
execution_loop
embodiment
observations_and_privileged_inputs
action_interface
memory_mechanism
learning_dependencies
human_assistance
evaluation_and_comparisons
cost_and_latency
reuse_and_licensing
transfer_limits
```

Define these as concise strings or null in the schema, using them when relevant and supported. Unknowns may be omitted. Do not force detailed architectural annotation onto abstract-only records. For systems that materially shape the overview, make it possible to reconstruct:

**instruction → observation/state → LLM decision → tool/controller → action → feedback.**

Identify which capability came from the LLM, a pretrained policy, hand-written logic, a simulator oracle, or human assistance. Separate what authors report from our interpretation. Record simulation versus physical evaluation, consequential comparisons, and known limits without inventing unreported details.

Link associated code, models, datasets, and demonstrations to their papers where available. Record authoritative license evidence and the particular artifact/version checked. “Worth learning from” and “available for commercial reuse” are different judgments; unclear terms remain unclear. Non-paper implementations or documentation can be retained as linked resources or source/search notes without pretending they are additional reviewed papers.

Retain `provenance_notes.material_uses`: dated entries with `date`, `agent`, `use`, `changes`, and optional repository-relative `project_artifact`. Update substantive findings and actual reading depth when a paper materially informs a design, report, comparison, or implementation. An ordinary lookup does not need a new event; copying a record does not create a reading event.

## 5. Preserve search provenance

Use the same search-log fields:

```text
search_id, lane, date, source, queries, categories, purpose, phase,
original_log, original_record_number, details
```

Query objects use `q` and optional `domains`. Direct entries use null for both `original_log` and `original_record_number`; retain genuine origins when importing a real log. Empty query arrays are appropriate for actual citation-trail, source-access, or import events—not invented searches.

Record meaningful query batches, sources, retained paper IDs, relevant deferred candidates, access failures, and useful unsuccessful searches. Preserve the distinction between discovery, metadata checking, and local lookup. Do not fabricate uniform hit counts or backdate reading. A search that found nothing does not prove the topic has no literature.

## 6. Make the map useful to both of us

Generate `Catalog.md` from the canonical records. Put the current dated state first in `Discovery Map.md`: actual totals, review-depth distribution, coverage by area, source limitations, contrasting approaches, informative failures, and remaining gaps. Keep generated current counts separate from maintained explanatory prose and historical checkpoints.

Give me a concise orientation to the main architectural alternatives and a small, varied selection of original papers—roughly six to ten entry points, not a required curriculum. Explain why each is useful and, where actually inspected, which section, figure, or demonstration is worth opening. Do not rank systems across incompatible tasks or convert author demonstrations into our own validated claims.

This assignment includes that orientation, **not a collection of long standalone reports**. Note a few useful follow-up explanation topics; we will decide which deserve deeper reports. Use the HTML Interactive Reports playbook for later substantial explanations where interactivity helps. Do not build an HTML interface merely to decorate the catalog.

Provide working lookup by text, stable ID/alias, category/tag, and reading status. Retrieve focused records rather than requiring the whole corpus in context. Document the actual commands and test them.

## 7. Validate the implementation and sample the evidence

Adapt the reference validator and small helper tools rather than copying Vision categories or [lab name redacted] scientific rules. Check JSONL readability, required fields/types, IDs and verified alias collisions, vocabularies, sources/dates, search-record shape and references, and consistency of current generated views.

Write fresh `validation.json` with the corpus and search-log SHA-256 hashes, profile/core versions, actual totals, errors, and coverage limitations. Separate structural validity from conceptual coverage. A green validator does not certify scientific accuracy, genuine reading, exhaustive coverage, or replicated results.

Include small regression checks for malformed records, duplicates, the robotics profile, and updating/regenerating views without erasing manual notes. Perform a bounded source check on varied records, especially claims shaping the overview. Report the scope of that check honestly; fix discovered material errors without starting an endless review cycle.

Demonstrate that the saved corpus can answer questions such as:

- Which systems use an LLM during deployment, and which use it only to develop policies or code?
- Which retain memory across tasks or sessions, and what actually persists?
- What sensor/state information reaches the LLM, and is any of it privileged?
- Which approaches revise behavior from feedback, and what remains conventional or pretrained?
- Which results demonstrate physical or cross-body transfer, and under what limits?
- Which promising resources have unresolved access, licensing, or hardware requirements?

## 8. Create the playbook and connect it to Project Details

Create `Playbooks/Literature Map.md`, titled **“Accessing and Updating the Literature Map.”** Describe the system that actually works, including:

- when to read the playbook and where to start;
- how to look up focused records before repeating external searches;
- when to return to primary sources or search for newer, missing, or competing work;
- how to add, deduplicate, correct, and materially use records;
- how reading depth, source provenance, robotics qualifications, and reuse evidence are maintained;
- how to regenerate the Catalog/current counts, validate, and preserve historical checkpoints;
- how consequential corrections propagate into linked reports or design records.

Keep recurring guidance separate from this one-time discovery assignment. Link to the schema for field details and to current coverage for counts. Do not document commands that do not exist or create a requirement for another model's approval.

Once the map and playbook exist, edit only the relevant part of `Project Details/Project Details.md`. Replace the sentence saying the Literature Map is not yet established with this entry and operating rule, retaining the HTML Interactive Reports entry and the rest of the project direction:

> **[Accessing and Updating the Literature Map](../Playbooks/Literature%20Map.md):** Read when looking for research papers, before external literature searches, when a paper is materially used, and when adding, correcting, or maintaining corpus records. It explains retrieval, source and reading-depth provenance, deduplication, material-use updates, and keeping the canonical corpus and derived views consistent.
>
> The Literature Map at `literature/` is Codex's first reference for research relevant to this project. Check it before repeating external searches; use external research to fill gaps, obtain needed primary detail, and find newer or competing evidence. Add relevant discoveries and update materially used records with their actual reading depth, evidence, and limitations. The map supports engineering judgment; it neither selects the robot's architecture nor replaces the underlying sources.

Link the README and schema to the playbook appropriately. Check relative links from each actual file location. Do not edit `Project Lead.md`, the HTML playbook, or the reference projects as part of this task.

## 9. Completion and handoff

This assignment authorizes literature discovery, focused implementation/source inspection, corpus and small-tool development, validation, the maintenance playbook, and the targeted Project Details update. It does not authorize new spending, external contact, publication, robot actuation, model training, a company-management instance, or selecting and implementing our first robot task.

Return one short handoff with the entry-point paths, actual corpus size and coverage, reading-depth distribution, validation/retrieval results and their limits, the most important unresolved areas, and a few optional reading entry points. Do not paste the full catalog into chat.

**Complete the usable map, playbook, and integration, then stop at the discovery checkpoint. I will explore the material with you before we choose what to build.** Record that boundary in continuity so another session does not restart broad searching or choose the architecture on its own.

Complete this all in one session.


---

**Codex (Session 1, 2026-09-18 21:21 PDT):**

The initial discovery map is ready. Start with [Discovery Map](../../../literature/Discovery%20Map.md), use the [README](../../../literature/README.md) for lookup, and follow [Accessing and Updating the Literature Map](../../../Playbooks/Literature%20Map.md) for maintenance. Project Details now links that workflow.

The canonical corpus contains 102 records across all 12 areas: 86 abstract-reviewed and 16 selective full-text skims, with no complete-paper/deep-read claims. Its 47 search/source events preserve actual searches, source checks and integration provenance. The orientation compares architectural alternatives and offers nine optional original-paper entry points; Code as Policies, CoALA and KnowNo are three different ways in.

Structural validation, 23 regression tests and 21 retrieval examples passed. An eight-record integration source sample supplemented the recorded lane inspections; this does not establish exhaustive coverage, replication or commercial usability. Important gaps remain in stale-memory repair, tactile/proprioceptive grounding, local cost/latency, genuine new-body transfer and complete artifact licensing.

This completes the discovery assignment. I will wait for your exploration and discussion before more broad searching or choosing and implementing a robot capability. The project architecture remains open. Detailed checks and limitations are in [Use Checks](../../../literature/Use%20Checks.md) and [HumanReport1](../../../agents/Codex/Session%20Summaries/HumanReport1.md).

---

**Randy (2026-09-22 19:09 PDT):**

Go ahead and conclude this chat. Thanks!

---

**Codex (Session 4, 2026-09-22 19:34 PDT):**

Concluded as requested. The initial literature-discovery assignment is complete; its corpus and maintenance playbook remain the searchable reference for the now-authorized architecture experiments. The summary preserves the original handoff and its limits.
