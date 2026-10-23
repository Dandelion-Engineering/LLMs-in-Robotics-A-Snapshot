# Accessing and Updating the Architecture Map

Read this before proposing, revising, implementing, running or comparing an architecture in the long-horizon experiment, or recording results, interesting behavior and general experiment notes. The [experiment home](../Long-Horizon%20Adaptive%20Robotics%20Expirement/README.md) links the [design contract](../Long-Horizon%20Adaptive%20Robotics%20Expirement/Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Contract.md) and [Architecture Map](../Long-Horizon%20Adaptive%20Robotics%20Expirement/Architecture%20Map/README.md). The map records what was considered and tried; it does not grant permission to start a new project phase.

## Retrieve before designing or repeating work

Run from the project root using the project Python. The map requires only the standard library.

```powershell
$architectureMapTool = 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool status --json
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool lookup 'restart' --json
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool lookup --kind revision --tag continuity --json
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool lookup --kind result --validity invalid --json
```

Use `history <actual-record-id> --json` to follow a matching architecture, revision or run through its linked history. Read full records and their attachments, including unsuccessful attempts, corrections and limitations. Search synonyms and mechanisms, not only names: a keyword match can describe a missing capability. Filters combine, and the returned total can exceed the displayed subset. An empty result does not establish that an idea has never been tried outside this map.

The generated Catalog is a navigation aid. Canonical JSONL records and linked evidence are authoritative. This map starts empty on purpose: no candidate architectures or architecture experiments were authorized when it was created. The primitive simulator probe belongs to design feasibility, not this map's experimental results.

## Record a complete approach without fixing its shape

Use a stable architecture ID for a continuing approach and a new revision ID whenever its mechanism, executable configuration or assumptions materially change. Explain lineage and differences; do not silently replace the implementation attached to an old result. A substantially different approach can receive a new architecture ID with a lineage note. Comparators and controls must be labeled so they are not confused with main candidates.

Describe the whole system in a versioned mechanism document and/or the revision's open description fields. Explain its goal, incoming observations, state estimates, decisions, actual actuator control, feedback and continuation after interruption. Record what each component receives and changes, timing/concurrency, uncertainty handling, tools and dependencies, and how durable context is reconciled with the world. Include concrete execution examples once an architecture exists. State known limitations and missing implementation explicitly.

These are explanation prompts, not compulsory modules. A design need not contain a planner, multiple agents, a particular model, a scene graph, a fixed memory layout or code generation. Document actual choices, including meaningful absence and unknowns. Free-form tags, descriptions, attachments and extension objects can express new mechanisms without replacing the core identity/evidence links. Extend the schema only when retrieval or reliable evidence demands it; retain compatibility or supply an explicit migration.

Record the actual code/configuration, model/weights/prompts where applicable, dependency/controller versions, commercial-use terms and unresolved resource limits. Link literature IDs and primary sources as useful; follow the [Literature Map playbook](Literature%20Map.md) when research materially informs a design. Map registration does not establish commercial permissions, deployment readiness or performance.

## Preserve runs and evidence

Before running, register the exact revision and immutable attempt manifest. Preserve the protocol/arena/evaluator release, frozen artifact references and hashes, condition, development/evaluation/diagnostic stage, scenario, paired block and replicate identity, seeds or protected manifest reference, timing track, resource limits and planned controls. Scenario and policy/noise replicate are different experimental units. Persistent, no-persistence and summary-only conditions normally reference the same candidate revision; identify any adapter and the limitations it adds to a causal claim.

After an attempt, append its result even when it failed, timed out, was cancelled or was infrastructure-invalid. Keep execution status, validity and task outcome separate. Absence of a result means no terminal result has been recorded; it is not evidence of a pass or failure. Never encode an unmeasured quantity as zero. Keep units, measurement definitions, sample counts/denominators and missing-value reasons with metrics. Link scoring output, intervention/resource records and compact evidence manifests. Preserve the connection between requested action, dispatch, feedback, observed outcome and independently verified completion where the evidence supports it.

Retain failed and invalid runs, exclusions and their reasons, contract violations and rerun links. Reruns receive new run IDs. Corrected results append a new record explicitly superseding the old result with a reason; retain the original. Improvements after inspecting evaluation results require new revisions/releases and fresh evaluation manifests under the experiment design. Do not present a comparison across different permissions, conditions, resources or protocols as a controlled effect without qualification.

Store large raw logs, video, state checkpoints and runtime filesystem snapshots in a deliberately selected evidence root, with compact manifests/references in the map. Reference location and artifact identity are separate: retain hash/size when available and explain missing, inaccessible or intentionally external evidence. Copying a path does not verify that a file exists or matches its hash. Preserve enough identity and provenance to recover or qualify the result when evidence moves.

## Capture interesting happenings and general notes

Append a linked note for surprising behavior, failure/recovery episodes, design questions, human feedback, decisions or general experiment observations. Connect it to the relevant architecture/revision/run/result IDs and event IDs or wall/simulation time ranges. Include what happened, why it may matter, the evidence, alternative explanations, uncertainty and useful next action. Label measured observation, source report, interpretation and hypothesis distinctly; a compelling replay is not an aggregate result.

Comparison notes should name the actual run/result set, exclusions, pairing, independent scenario denominator and analysis method. Preserve failures alongside successes and separate full-system comparisons from claims about an individual mechanism. Keep machine-readable comparison details in extensible fields when useful. Do not force general notes to invent a run that never occurred.

## Write safely and keep retrieval current

Read [Schema](../Long-Horizon%20Adaptive%20Robotics%20Expirement/Architecture%20Map/Schema.md) and use the map README for exact fields and append examples. Check the human inbox and active work claims, then claim only paths being edited. Compose one record in a separate JSON file; the `template` command provides an unregistered outline. Fill it from actual information, not placeholder guesses. Use `append` with the current overall canonical-store SHA-256 from `status`; it validates the proposed linked store and refuses duplicates, broken references, concurrent writers and stale input before replacing the collection atomically. Do not hand-edit old records or delete inconvenient results.

```powershell
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool build
.\venv\Scripts\python.exe -X utf8 -B $architectureMapTool validate --output validation.json
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/test_map.py'
```

Run regressions when schema/helper behavior changes; after ordinary record additions, rebuild and validate and inspect representative lookup/history results. Validation binds counts and derived views to canonical hashes and checks recorded structure and references. It does not authenticate experiments, establish secure isolation, read external evidence automatically, or decide whether a scientific comparison is justified.

The map is **operator/development knowledge**, separate from any candidate's own persistent filesystem. Never mount the whole project or map inside a scored candidate as a convenient memory source. Evaluator truth, concealed manifests, seeds, future disturbances and cumulative results must remain unavailable to candidates under the experiment contract. Compact hashes and opaque protected references can identify evidence without exposing it. No sustained experiment is launched by this map; use the shared compute queue and authority limits in Project Details.
