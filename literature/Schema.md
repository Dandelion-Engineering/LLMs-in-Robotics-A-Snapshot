# Corpus schema and reading rules

Shared core: **Vision schema 1.0**. Domain profile: **llm-robotics-1.0**.
Vision is the primary structural reference; [private project name redacted] supplies the portable
lookup, generation and validation pattern. Reference locations, revisions and
file hashes are recorded in [tool reference notes](../agents/Codex/research/tool-reference-notes.md).
Only organization, common field meanings and tool structure were reused. Neither
reference's papers, counts, searches, reading events or domain rules were imported.

`papers.jsonl` is canonical: exactly 27 top-level keys per record, one JSON object
per physical line, UTF-8 without BOM, with a final newline. Embedded newlines must
be JSON escapes. Duplicate object keys and non-JSON numeric values are rejected.
An empty file can represent an honest empty corpus; it is not a completed map.

## Fields and types

| Field | Type and meaning |
|---|---|
| `id` | Nonempty string; stable verified DOI, arXiv, PMID or persistent publisher identity. |
| `identifier_aliases` | String list of other verified identifiers for the same work; `[]` when none established. |
| `title` | Nonempty string; source title, allowing harmless spacing/punctuation normalization. |
| `authors` | Nonempty ordered string list; source initials are acceptable. |
| `authors_complete` | Boolean; false if shortened or completeness is unverified. |
| `year` | Integer publication/edition year; distinguish original publication, preprint revision and retrieval dates in metadata. |
| `venue` | Nonempty string or null when unverified. |
| `doi` | Bare DOI string such as `10.1234/example`, or null when unverified/unavailable here. |
| `url` | Persistent HTTP(S) primary publication, author manuscript or indexed bibliographic URL. |
| `open_access_url` | Located freely accessible manuscript/full-text HTTP(S) URL, or null; availability does not imply reading. |
| `categories` | Nonempty string list from the profile category vocabulary below; membership overlaps. |
| `tags` | Nonempty descriptive string list for mechanisms, inputs, evidence and retrieval. |
| `paper_type` | `method`, `experimental`, `theoretical`, `review`, or `benchmark`; an organizing label, not an evidence grade. |
| `review_status` | One of the five reading levels below. |
| `basis_for_summary` | Nonempty string list naming the actual inspected materials, source edition, sections/pages and access restrictions. |
| `central_idea` | Nonempty string; concise mechanism-first paraphrase qualified to the available evidence. |
| `efficiency_targets` | String list of actual costs or resource quantities addressed; **may be `[]`**. |
| `representation_or_method` | Nonempty string describing the mechanism, model, procedure or intervention. |
| `task_or_domain` | Nonempty string describing the studied setting; distinguish physical robots, simulation, nonrobotic agents and biological evidence. |
| `evidence_or_evaluation` | Nonempty string describing evidence visible at the stated reading depth, including relevant comparisons and conditions. |
| `main_limitations` | Nonempty string distinguishing author-reported limits, agent inferences and unresolved details. Abstract silence does not prove a missing control. |
| `project_relevance` | Nonempty string explaining the paper's specific relevance; a retrieval judgment that does not select an architecture. |
| `importance` | `high`, `medium`, or `low`; usefulness for later reading/retrieval, not endorsement. |
| `sources` | Nonempty object list. Each object has HTTP(S) `url`, nonempty `material_reviewed`, and actual ISO `accessed_date`; additional locators/edition details may be retained. |
| `metadata_notes` | Nonempty string or null; edition, publication dates, corrections, author or source-access qualifications. |
| `discovery_lane` | Nonempty string naming the real discovery origin; bookkeeping rather than scientific classification. |
| `provenance_notes` | Object for extra qualifications; `{}` when absent. Optional robotics context and material-use events are defined below. |

The four nullable top-level fields are `venue`, `doi`, `open_access_url` and
`metadata_notes`. Missing optional facts remain null or are explicitly described
as unknown; they are not converted into negative findings. Only
`identifier_aliases` and `efficiency_targets` may be empty among the top-level
string lists. Year validation uses execution year plus one for a documented
forthcoming edition. Access/search/use dates use `YYYY-MM-DD`, must be real dates,
and cannot be future dates. An online revision is not automatically the work's
original publication year. Put revision identifiers and dates in source details
or metadata notes without changing the actual retrieval date.

## Reading depth

| Value | What was actually done | Catalog |
|---|---|---|
| `discovered` | Identity/relevance established, but no primary abstract or equivalent content responsibly reviewed. | D |
| `abstract_reviewed` | Primary abstract or equivalent author/publisher summary inspected; a title-only snippet does not count. | A |
| `full_text_skimmed` | Selected full-text sections/excerpts inspected and named in the basis. | S |
| `full_text_reviewed` | The complete paper reviewed at ordinary research depth. | F |
| `deep_read` | Sustained scrutiny of methods, arguments, controls and implications. | R |

Indexed primary abstracts count when the provenance is explicit. Inspecting a
reference list does not establish reading of the cited paper. A review's account
of an experiment remains a secondary account until its primary source is read.
An accessible or downloaded PDF does not establish full reading. Preserve the
deepest supported prior depth, correcting overstated labels when necessary;
reading an earlier version does not establish review of all later revisions.

## Robotics category vocabulary

The open seed categories are:

- `robotics_stack_architectures`
- `planning_reasoning_skills`
- `code_generation_tools`
- `perception_state_grounding`
- `memory_continuity`
- `closed_loop_adaptation`
- `learning_and_skill_acquisition`
- `embodiment_transfer`
- `world_models_prediction`
- `deployment_evaluation_safety`
- `human_lab_assistance`
- `neuroscience_cognitive_connections`

The keys and display labels live in `corpus.py`. Cross-tagging is useful, so
category counts are nonexclusive. A supported category change updates that
configuration, this schema, canonical classifications and the coverage discussion
together, then regenerates the views. Equal category sizes are not required.

The profile preserves Vision's common semantics. `efficiency_targets: []` is valid
when a paper does not address efficiency. Memory quality, safety and task success
are not relabeled as efficiency. Latency, energy, compute, model size, sensor bytes,
training data and total system cost are different quantities; the corpus does not
combine them into a numerical ranking.

## Optional robotics context

`provenance_notes.robotics_context` is an optional object. The following optional
members are **concise nonempty strings or null**. Unknowns can be omitted. Do not
force detailed architecture claims onto an abstract-only record.

| Member | Scope |
|---|---|
| `llm_role` | The model's actual role, including development-time, runtime, evaluation-only or no-LLM baseline. |
| `execution_loop` | Instruction → observation/state → LLM decision → tool/controller → action → feedback; what triggers replanning or observation. |
| `embodiment` | Robot/body, simulator or nonrobotic setting and reported physical evaluation. |
| `observations_and_privileged_inputs` | Sensors, derived state and what actually reaches the LLM, including ground-truth/oracle input. |
| `action_interface` | Programs, skill calls, goals, controller parameters, trajectories or low-level actions; identify conventional/pretrained execution. |
| `memory_mechanism` | What persists, its representation, retention scope, retrieval/update process and stale-state handling when known. |
| `learning_dependencies` | Pretraining, demonstrations, finetuning, reinforcement learning, adaptation without weight updates and unreported requirements. |
| `human_assistance` | Teaching, corrections, resets, selection, annotations or supervision and reported burden. |
| `evaluation_and_comparisons` | Consequential baselines, evaluation conditions, reported outcomes and evidence limits. |
| `cost_and_latency` | Reported inference location, scheduling, timing, compute/cost and missing measurements. |
| `reuse_and_licensing` | Artifact/version and authoritative licensing evidence; distinguish paper availability, code, weights, datasets and demos. |
| `transfer_limits` | Exactly what transferred across tasks, environments or bodies and required calibration/training/interfaces. |

Separate author reports from engineering interpretations. Name the contribution
of the LLM, pretrained policy, hand-written logic, simulator oracle and human
assistance where the evidence supports it. Link code, models, datasets and
demonstrations in source objects or other provenance notes with their actual
inspection scope. A permissive code license does not establish rights for weights
or datasets. Unclear terms stay unclear. Non-paper resources may be linked without
being counted as additional reviewed papers. Biological evidence, computational
interpretations and engineering analogies remain distinct.

`provenance_notes.material_uses` is an optional list of actual dated events. Every
entry has `date`, `agent`, `use` and `changes`; each is a nonempty string and `date`
has the date format above. Optional `project_artifact` is a repository-relative
path to an existing file (no absolute path or traversal). The validator checks
these fields, dates and artifact paths. An ordinary lookup needs no event;
copying a record creates no reading event. A material-use event accompanies
substantive updates where justified and does not itself upgrade reading depth.
Other provenance keys may preserve edition relationships, artifact links and
source qualifications without changing the top-level schema.

## Identity and deduplication

Keep stable IDs when bibliographic metadata changes. Add aliases only after
verifying that they identify the same work. A preprint and final publication are
normally one record; genuinely distinct follow-up studies stay separate. Keep
the inspected editions, access dates, useful qualifications and real material-use
events when merging. Correct affected search references and linked project claims.

The validator flags normalized-title collisions and identities across IDs,
aliases, DOI values and publication/open-access URLs. DOI/PMID/PMCID/arXiv forms
are normalized, including versioned arXiv links. Other stable IDs/aliases are
matched case-insensitively as exact values, with surrounding whitespace/trailing
slashes removed. The helper cannot decide all changed-title or extension
relationships, authenticate an alias, or replace source-based deduplication.

## Search-log schema

Every `searches.jsonl` object has exactly these 11 keys:
`search_id`, `lane`, `date`, `source`, `queries`, `categories`, `purpose`, `phase`,
`original_log`, `original_record_number`, `details`.

`search_id`, `lane`, `source` and `purpose` are nonempty strings. Search IDs are
unique. `date` is the actual ISO event date. `categories` is a string list of
current category keys and can be empty for a general metadata/source event.
`queries` is a list of objects containing nonempty `q` and optional `domains`
(a nonempty string list). An empty query list is appropriate for a real
citation-trail, source-access or import event, not an invented search.
`phase` is a nonempty string or null. `original_log` and `original_record_number`
are both null for a direct entry, or a paired nonempty source-log string and
positive integer for a real imported origin. `details` is an object.

Use `details.selected_paper_ids` for retained canonical IDs and optional
`origin_paper_ids` for canonical citation-trail origins. These string lists are
checked against canonical IDs, not aliases. Deferred titles/URLs belong in
`deferred_candidates` or descriptive notes. Record meaningful query batches,
sources, actual access failures, useful unsuccessful searches and distinctions
between discovery and metadata checking. Local lookup requires no fabricated
external event. Do not invent uniform hit counts or historical search dates.

## Generated views, checks and limits

The [README](README.md) documents commands. `corpus.py build` validates canonical
structure, generates the category Catalog, and replaces only the single block
between `<!-- BEGIN GENERATED CURRENT METRICS -->` and
`<!-- END GENERATED CURRENT METRICS -->` in Discovery Map. Outside editorial text
and historical checkpoints are preserved. Catalog order is importance, year,
then title within each category. Current metrics include the latest recorded
paper-source access date, not an invented publication or reading date.

`validation.json` binds its result to current corpus and search-log SHA-256
hashes, profile/core versions, actual totals, duplicate collisions, errors and
generated-view consistency. Malformed structure fails validation. Coverage
reports unrepresented areas and reviewed counts **without a numeric completion
gate**. The scale guide is not a quota, and a small honest corpus can be
structurally valid while conceptually incomplete. Counts in a failed report use
structurally usable records and do not resolve detected duplicates.

Green validation cannot certify scientific accuracy, source reading, complete
authors, source rights, replication, all edition equivalences or exhaustive
coverage. Current gaps, competing approaches and conceptual recurrence belong
in [Discovery Map](Discovery%20Map.md). See [Accessing and Updating the Literature
Map](../Playbooks/Literature%20Map.md) for retrieval, maintenance and propagation
of consequential corrections. The map supports engineering judgment and does
not select the project's first task, embodiment, model, memory or LLM placement.
