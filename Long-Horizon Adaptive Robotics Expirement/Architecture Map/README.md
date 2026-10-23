# Architecture Map

Use this map to find earlier approaches, understand exactly how a system worked, and follow its runs, results and investigation notes. Start with the [experiment home](../README.md), [experiment design](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/README.md), or [maintenance playbook](../../Playbooks/Architecture%20Map.md).

**Batch 01 is underway.** Randy authorized three candidates and clarified that the assignment includes implementing prerequisites and running the experiments. Three proposed mechanism revisions are registered; implementation and calibration evidence remain separate from scored candidate outcomes. Start at the [batch entry point](../Batch%2001/README.md). The earlier simulator feasibility probe remains design evidence, not an architecture result.

## What lives here

| Canonical file | What it preserves |
|---|---|
| [architectures.jsonl](architectures.jsonl) | Stable identity, title and purpose of an approach |
| [revisions.jsonl](revisions.jsonl) | Exact design snapshots, lineage, mechanism explanations and optional versioned documents |
| [runs.jsonl](runs.jsonl) | One attempt's revision, experimental condition, scenario, pairing and reproducibility references |
| [results.jsonl](results.jsonl) | Outcomes, validity, measurements, evidence and subsequent corrections |
| [notes.jsonl](notes.jsonl) | Linked observations, interesting happenings, questions, explanations, decisions and general notes about an approach or its experiments |

[Catalog.md](Catalog.md) is a generated browsing aid. [Schema.md](Schema.md) defines the record fields. Canonical JSONL records and linked evidence are the durable record; the catalog is not a leaderboard or an assessment of experimental quality.

An architecture has a continuing identity; each materially changed design or configuration receives a new revision. Runs point to exact revisions. Results point to runs. Notes can connect any existing records, including several runs in a comparison. General project notes with no real map target belong in the [experiment home](../README.md), not in a fabricated architecture or run.

## Find previous work

Run these commands from the project root. The helper uses the project Python and only its standard library.

```powershell
$architectureMapFolder = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Architecture Map'
$architectureMapTool = Join-Path $architectureMapFolder 'map.py'
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool status --json
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool lookup 'restart' --json
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool lookup --kind revision --tag continuity --json
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool lookup --kind result --stage evaluation --validity invalid --json
```

Search is a case-insensitive substring match across each full JSON record, including descriptions and `details`. It does not search attachment contents automatically. Filters are exact, case-sensitive matches combined with AND. Search synonyms and mechanisms, then read the complete matching records and their documents. Tags do not imply an approach actually has the named capability.

Use `lookup --architecture <actual-id> --json`, `lookup --revision <actual-id> --json`, or `lookup --run <actual-id> --json` to retrieve linked records. `history <actual-id> --json` returns linked history and corrections without a result limit. Lookup defaults to 20 displayed records; `--limit` changes this, and `total` reports matches beyond the displayed subset. Both original and superseding results remain searchable; follow their correction chain before interpreting the current assessment.

Available exact filters are `--id`, `--architecture`, `--revision`, `--run`, `--tag`, `--stage`, `--condition`, `--validity`, `--outcome`, `--claim-type`, `--status`, `--execution-status`, `--protocol-id`, `--scenario-id`, `--paired-block-id` and `--replicate`. For result records, stage, condition, protocol, scenario, paired-block and replicate filters use the linked run. Other field filters apply to the record itself; they are not inherited by every note or revision.

An empty search means no matching record was found here. It does not establish that an idea has never been tried elsewhere.

## Explain the complete system

The revision's `mechanism` text, open `details` object, tags and optional attachments allow different kinds of architectures. Explain what the system is trying to achieve, which observations it receives, how information and control flow, what actually moves the robot, how feedback changes actions, and how it continues after interruption. Describe timing, concurrency, uncertainty, durable context, dependencies, resources, meaningful absences and unresolved limitations. Include concrete execution examples once real architectures exist.

These are explanation prompts, not required modules. No planner, model, memory layout, scene graph, agent count or code-generation mechanism is prescribed. Rich explanations can live in versioned Markdown inside this folder. Attach the file with its SHA-256; preserve that exact file after registration. A changed document gets a new path and revision. Keep a useful searchable summary in the canonical record because lookup does not index document bodies.

Record baseline/control roles and lineage explicitly in tags or `details`. Persistence conditions generally belong to runs of the same candidate revision; describe any adapter and its implications in `condition_details`. A status change also requires a new revision snapshot rather than editing an old one.

## Add records safely

Follow the [playbook](../../Playbooks/Architecture%20Map.md), check the human inbox and active work claims, and obtain the appropriate write scope before changing shared files. Never hand-edit canonical history.

1. Print an incomplete form with `template architecture`, `template revision`, `template run`, `template result` or `template note`. This prints JSON only; it does not add a record.
2. Save and complete one form as a separate UTF-8 JSON file without a BOM. Use actual facts and existing target IDs. Blank IDs/text and default explanations are drafting prompts, not registered examples. Add any immutable revision attachments first.
3. Read `status --json`, inspect the current records and retain its **overall `store_sha256`**. This digest covers all five canonical files, not just the collection being changed.
4. Append using that digest. If it is stale, review the changed store before obtaining a new digest and retrying.
5. Rebuild, validate and inspect representative lookup/history output.

For an authorized revision, the command sequence below prints its drafting form and later appends the completed file. Replace the input-path placeholder before running the append command; it is not a candidate example.

```powershell
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool template revision
# Complete and save the printed form separately, then inspect current records.
$architectureMapStatus = .\venv\Scripts\python.exe -X utf8 -B $architectureMapTool status --json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot read the architecture map.' }
$architectureRecordPath = '<absolute path to completed revision JSON>'
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool append revision --input $architectureRecordPath --expected-sha256 $architectureMapStatus.store_sha256
if ($LASTEXITCODE -ne 0) { throw 'Append failed; inspect the error before retrying.' }
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool build
if ($LASTEXITCODE -ne 0) { throw 'Catalog build failed.' }
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool validate --output validation.json
if ($LASTEXITCODE -ne 0) { throw 'Map validation failed.' }
```

Append validates the complete proposed store, preserves existing collection bytes, rejects duplicate IDs and broken relationships, checks the expected digest and writes the collection atomically. A temporary `.map-write.lock` coordinates cooperating writers. Do not remove another writer's active lock. Work claims remain necessary: the helper is not a secure database or protection from arbitrary external edits. Build and validation are separate operations; a successful append alone does not refresh the catalog.

## Results and investigation

Keep execution status, run validity and task outcome separate. A missing result is an unrecorded terminal assessment, not a success, failure or zero. Failed, invalid, cancelled and unstarted attempts remain visible. Reruns get new run IDs. Correct a result by appending a new result for the same run with `supersedes_result_id` pointing to its latest result; explain the correction in `details` and retain the original evidence.

Notes hold interesting events and ordinary experiment notes without requiring a separate event taxonomy. Link the actual architecture, revision, run or result; put event IDs or wall/simulation time ranges in `details` or evidence locators. Distinguish observations from interpretations and hypotheses. Record alternatives and unknowns. Correct a note with a new `correction` note and `supersedes_note_id`. History follows that correction link in both directions; the corrected note may also appear in `target_ids` but does not have to.

Comparison notes should identify the exact runs/results, exclusions, pairing, independent scenario denominator and analysis method. Preserve failures and superseded assessments; a memorable episode is not an aggregate result.

## Evidence and boundaries

This map is operator/development knowledge. It is separate from a candidate's own persistent filesystem. Never mount the map or entire project inside a scored candidate; evaluator truth, hidden seeds, held-out manifests, future disturbances and cumulative results must remain unavailable under the experiment contract. Access labels describe intended audiences, not enforced permissions.

Large logs, video, checkpoints and runtime snapshots belong in a deliberately selected external evidence root. Keep compact references and hashes here. An opaque evaluator-only manifest reference can identify protected evidence without disclosing its contents. `unknown` means the information is not established; `none` means an explicit absence with a reason. Neither means zero. A reference marked available is an assertion unless its bytes were actually checked; the helper verifies local revision attachments but does not fetch general evidence.

Validation checks structure, links, correction ordering, local attachment hashes and catalog freshness. Its report records canonical and catalog hashes. It does not authenticate an experiment, prove physical success, establish comparability or commercial permissions, or validate candidate isolation.

After ordinary additions, build and validate. When changing schema/helper behavior, run the standard-library regression tests, which use temporary synthetic records outside the canonical map:

```powershell
.\venv\Scripts\python.exe -X utf8 -B (Join-Path $architectureMapFolder 'test_map.py')
```

Passing those tests establishes helper behavior on the tested cases, not robotics performance.
