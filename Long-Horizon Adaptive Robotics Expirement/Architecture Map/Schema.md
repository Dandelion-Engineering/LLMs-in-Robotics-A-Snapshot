# Architecture Map schema

Schema version: `architecture-map-1.0`. Read the [map guide](README.md) for workflow and the [playbook](../../Playbooks/Architecture%20Map.md) for interpretation and authority boundaries.

The five canonical files are UTF-8 JSONL without a BOM: one JSON object per nonblank physical line, with a final newline. Empty files are valid and intentional at initialization. Duplicate JSON keys and nonfinite numbers are rejected. Each record has exactly the common fields plus its collection's fields below. Put extensions in `details`, not new top-level keys.

The map-local `.gitattributes` disables automatic Git newline conversion so canonical files and immutable attachments retain the exact bytes used by their hashes across checkout.

## Common fields

| Field | Meaning and validation |
|---|---|
| `schema_version` | Exactly `architecture-map-1.0` |
| `id` | Globally unique across all collections; begins with a letter or digit, followed by letters, digits, `_`, `.`, `:`, or `-` |
| `recorded_at` | ISO timestamp including `T` and a timezone; when this record was made, not event ordering authority |
| `author` | Nonempty attribution |
| `tags` | List of distinct nonempty strings; free vocabulary |
| `details` | Open JSON object for additional explanation, structured metadata and future mechanisms |

IDs are stable and records are append-only. No particular ID prefix is required. Use new IDs for revisions, attempts and corrections. All required text below is nonempty unless explicitly nullable; lists may be empty unless stated otherwise.

## Architecture and revision

`architectures.jsonl` adds `title` and `summary`: a stable identity and purpose. Descriptive changes can be captured by notes and later revision descriptions without rewriting the original record.

`revisions.jsonl` adds:

| Field | Meaning |
|---|---|
| `architecture_id` | Existing architecture ID |
| `parent_revision_id` | Earlier revision of this architecture, or `null` for a first snapshot |
| `status` | `proposed`, `implemented`, `frozen`, or `retired` |
| `title`, `summary` | Human-readable revision identity and changes |
| `mechanism` | Searchable explanation of how the complete system works |
| `attachments` | Reference list; each attachment must be an available file inside the map folder with a matching SHA-256 |

The snapshot is immutable, including attached bytes. A changed mechanism, configuration, attachment or status gets a new revision. `details` and attachments can express arbitrary components, interfaces, timing, continuity, resource assumptions, provenance and limitations. These are not compulsory architecture modules. Store additional cross-architecture lineage in `details` or a linked note; `parent_revision_id` stays within one architecture.

## Runs

`runs.jsonl` describes one attempt against one exact revision. It is an immutable manifest; it can be registered before execution with `started_at: null`. Subsequent actual timing or deviations can be preserved in the result's `details` and evidence rather than rewriting this manifest.

| Field | Meaning |
|---|---|
| `revision_id` | Existing exact revision |
| `stage` | `calibration`, `development`, `evaluation`, or `diagnostic` |
| `condition_id` | Named condition; persistence/control settings belong here rather than automatically creating a new architecture |
| `protocol_id` | Protocol/release identity |
| `scenario_id` | Independent scenario identity |
| `paired_block_id` | Pairing/block identity; use an explicit unpaired identifier and explain it if the protocol is unpaired |
| `replicate` | Positive integer; policy/noise replicate, distinct from scenario identity |
| `started_at` | Actual timezone-bearing ISO start timestamp, or `null` if not recorded in this manifest |
| `rerun_of_run_id` | Earlier attempt ID, or `null`; a rerun always has a new ID |
| `condition_details` | Open object for actual treatment, adapters, budgets, timing track, controls and deviations |
| `seeds` | Reference-state object identifying the seed manifest without exposing protected contents |
| `frozen_refs` | Object with `code`, `environment`, `models`, `protocol` and `scenario` reference-state objects; additional roles allowed |
| `evidence` | Reference list for supporting manifests or other run evidence |

Every recorded `frozen_refs` reference needs a SHA-256. An `evaluation` run requires a revision with `status: frozen`, recorded code/environment/protocol/scenario references, recorded seeds, and models either `recorded` or explicitly `none`. Development records can preserve incomplete knowledge with explicit reasons. The validator checks these declarations; it does not inspect protected manifests or prove that the runtime used their contents.

The same frozen candidate under different persistence conditions is the intended within-candidate comparison. Record compensating adapters explicitly. An improvement after inspecting scored results needs a new revision/release and fresh evaluation manifests under the design contract.

## Results

`results.jsonl` adds:

| Field | Meaning |
|---|---|
| `run_id` | Existing attempt |
| `supersedes_result_id` | `null` for its first result; otherwise the latest result for this same run |
| `execution_status` | `completed`, `failed`, `timed_out`, `aborted`, or `not_run` |
| `validity` | `valid`, `invalid`, or `unknown` |
| `validity_reason` | Basis for the validity label, including exclusions or uncertainty |
| `outcome` | `success`, `partial`, `failure`, `unknown`, or `not_assessed` |
| `ended_at` | Timezone-bearing ISO timestamp, or `null` only for `not_run` |
| `termination_reason` | Why execution stopped or did not start |
| `metrics` | Metric list defined below; metric names must be distinct within a result |
| `evidence` | Reference list; assessed success/partial/failure requires at least one reference, including an explicit missing-evidence reference when necessary |

`not_run` requires `validity: unknown`, `outcome: not_assessed`, `ended_at: null` and an empty `metrics` list. For attempted runs, `ended_at` cannot predate a recorded start. Completing execution does not imply successful task completion. A run with no result has no recorded terminal assessment.

Corrections append a new result and preserve the entire old record. Explain why the assessment changed in `details` (for example, a `correction_reason` entry); retain exclusion and rerun provenance. The validator enforces a single ordered correction chain per run, not the scientific correctness of the revision.

Each metric has exactly these fields:

| Field | Meaning |
|---|---|
| `name` | Distinct nonempty measurement name |
| `value` | Finite number, or `null` when missing |
| `unit` | Nonempty unit, including an explicit dimensionless/count unit when appropriate |
| `denominator` | Positive finite number or `null`; do not invent a denominator |
| `denominator_description` | What the denominator means, or why one is inapplicable/unavailable |
| `missing_reason` | Nonempty explanation when value is `null`; otherwise `null` |
| `evidence` | Reference list; a measured value requires at least one reference |

Put measurement definitions, filters, aggregation, sampling, uncertainty and extra context in `details` or linked evidence. Zero is a measurement, not shorthand for missing data. Scenario counts and replicate counts must remain distinguishable. Structural validity alone does not establish that a claimed value is measured.

## Notes, observations and corrections

`notes.jsonl` adds `target_ids`, `claim_type`, `body`, `supersedes_note_id` and `evidence`.

- `target_ids` is a nonempty list of distinct existing record IDs. A note cannot target itself; note-to-note targets must already exist earlier in the notes collection. Do not invent a target for a general project note.
- `claim_type` is one of `note`, `question`, `decision`, `observation`, `event`, `interpretation`, `hypothesis`, `source_report`, `correction` or `comparison`.
- `body` is nonempty text. Explain what happened or is proposed, its evidence and limitations. An `observation` or `event` label does not itself prove measurement; link the relevant data and keep interpretations distinct.
- `supersedes_note_id` is normally `null`. To correct an earlier note, set `claim_type: correction` and reference the latest note in that correction chain. History follows this link in both directions and association filters inherit the corrected note's subjects. Adding the corrected note to `target_ids` is optional; the new note must still have at least one real target.
- `evidence` is a reference list. Use `details` and evidence locators for event IDs, time intervals, mechanisms, alternatives and follow-up questions.

Comparison notes may link several architectures, revisions, runs or results. Record the actual comparison set, exclusion rules, pairing, denominators and analysis method. There is no compulsory taxonomy of interesting behavior.

## References and explicit unknowns

Every reference has exactly these fields:

| Field | Meaning |
|---|---|
| `label` | Nonempty human description |
| `uri` | Nonempty location/identifier string, or `null` |
| `sha256` | Lowercase 64-character SHA-256, or `null` |
| `state` | `available`, `missing`, or `unknown`; available requires a URI |
| `access` | `public`, `operator`, or `evaluator_only` |
| `locator` | Nonempty section/event/tick/time locator, or `null` |

Revision attachment URIs resolve relative to the map folder, must remain inside it and are checked against local bytes. Other references may identify an external evidence root, source or opaque protected manifest; their existence and contents are not automatically fetched or checked. A URI identifies location, a hash identifies bytes, state describes availability and access describes the intended audience. These are different properties. Access labels do not implement security.

Reference-state objects used by `seeds` and each `frozen_refs` role have exactly `state`, `refs` and `reason`:

| State | Required content |
|---|---|
| `recorded` | Nonempty reference list; reason may be nonempty text or `null` |
| `none` | Empty reference list and an explicit nonempty reason establishing absence |
| `unknown` | Empty reference list and an explicit nonempty reason explaining the knowledge gap |

`recorded` identifies recorded provenance; it does not assert that the referenced bytes are currently accessible. Keep evaluator-only contents out of candidate access. Large raw evidence belongs outside Git, with compact references here.

## Tool checks and limits

`status --json` reports counts, per-file hashes and `store_sha256`, the append precondition for the whole canonical store. `append` accepts one completed record and checks the resulting linked store before atomically appending it. `build` regenerates `Catalog.md`. `validate --output validation.json` checks the catalog and records a hash-bound report; the report is valid for those bytes, not an everlasting certificate.

Validation covers syntax, exact keys, field types, identities, relationships, correction ordering, evaluation provenance declarations and local revision attachment hashes. It does not verify external evidence, measure behavior, choose architectures, judge causal explanations or authorize runs. Use the [README commands](README.md#add-records-safely) for the complete workflow.
