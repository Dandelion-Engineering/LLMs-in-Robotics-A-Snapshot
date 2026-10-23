# Accessing and Updating the Literature Map

Read this when looking for papers, before external literature searches, when a paper materially informs work, or when maintaining corpus records. The map supports the engineering direction in [Project Details](../Project%20Details/Project%20Details.md); it does not adopt a task, robot body, runtime model, architecture or memory mechanism.

## Start locally

Use the [README](../literature/README.md) for working commands, the [Discovery Map](../literature/Discovery%20Map.md) for current coverage and uncertainty, and the [Catalog](../literature/Catalog.md) to browse. Retrieve focused records from [papers.jsonl](../literature/papers.jsonl) with `literature/corpus.py lookup`. Search mechanisms, interfaces, synonyms and body/task constraints as well as titles. Check [searches.jsonl](../literature/searches.jsonl) before repeating a discovery batch.

```powershell
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup 'VoxPoser' --json
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --id 'arxiv:2209.07753' --json
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --category memory_continuity --limit 8
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --tag development-time-llm --json
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --category code_generation_tools --status full_text_skimmed --limit 8
```

Filters combine with AND; exact IDs include verified aliases. Read the returned total as well as the displayed subset. Text lookup searches the full record, including limitations: a match for a capability can describe its absence. Follow the primary source whenever the existing basis cannot support the proposed use.

## Fill a real evidence gap

Return to primary methods, figures, experiments, corrections or resource documents when a distinction matters. Search externally for newer, missing or competing work. An abstract supports orientation; it does not reveal every controller, oracle, failure condition or license. A review's description of an experiment is not inspection of that primary experiment. Do not treat newer preprint upload dates as publication dates or older results as evaluations of current models.

Keep useful unconventional alternatives and counterevidence. A negative search does not prove an empty field. Record what the actual query/access accomplished, including relevant deferred candidates and failures. Do not invent yields, historical searches or reading events.

## Make canonical changes

Follow [work-claim mechanics](../Tools/work.md): check active claims and the human inbox before claiming the paths you will edit. Read-only lookup requires no claim. Use the current canonical files, never the initial research-lane inputs.

1. Resolve identity by stable ID, verified aliases, DOI/arXiv URLs, title and authors. Keep one record for a preprint and its verified final edition; keep a distinct follow-up study when the evidence differs. Similar titles alone do not establish equivalence. Preserve a stable ID when adding a verified alias or publication DOI.
2. Read [Schema](../literature/Schema.md), retain all 27 top-level fields and the reference types, and edit the relevant JSONL record. Preserve useful previous accesses and uncertainty. Empty efficiency targets are valid; safety, memory quality and task success are not efficiency measurements.
3. Record actual source URL, access date and inspected material. Increase reading depth only when that reading happened. Name the sections, figures or edition for selective skims. Correct overstated depth when its basis is unsupported; reading a new version's abstract does not transfer full-paper review from an old version.
4. Update substantive mechanism, evidence, limitations and relevance, not just the reading label. Optional `provenance_notes.robotics_context` should identify the LLM's role and the observation → decision → controller → action → feedback loop where supported. Distinguish runtime generation, development-time generation, weight updates, generated code and stored memories. Explicitly identify privileged simulator information and human help.
5. Link code, weights, data and demonstrations where located. Commercial reuse needs artifact-specific authoritative terms and an identifiable revision/hash; a paper license or repository badge does not settle downstream model/data/simulator licenses. Omit or qualify unknown details. Do not install or adopt a resource merely because it is discussed.
6. When a record materially informs a report, comparison, design or implementation, append a real `provenance_notes.material_uses` event with `date`, `agent`, `use`, `changes`, and optional existing repository-relative `project_artifact`. An ordinary lookup needs no event. This does not itself justify a depth increase.
7. Add meaningful query/source batches to `searches.jsonl` with its exact schema. Direct entries use null origin fields. Retained IDs go in `details.selected_paper_ids`; candidates outside the corpus remain deferred candidates. Update references after identity merges.

For consequential corrections, locate dependent artifacts through material-use links and text/ID lookup. Correct the active claim or design, record why it changed, and preserve the historical context needed to interpret older results. Do not silently carry the superseded conclusion into current work.

## Keep views and checks current

```powershell
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py build
.\venv\Scripts\python.exe -X utf8 -B literature/validate_corpus.py --output literature/validation.json
```

The builder generates the Catalog and replaces only the block between `<!-- BEGIN GENERATED CURRENT METRICS -->` and `<!-- END GENERATED CURRENT METRICS -->` in Discovery Map. Keep prose and historical checkpoints outside those markers. Update maintained coverage limitations and architectural orientation when records change; fresh numbers do not make old interpretation current.

Inspect `validation.json` for canonical/search hashes, core/profile versions, actual totals, errors and coverage limitations. Structural validity is separate from conceptual coverage. Fix malformed records and stale views instead of relaxing checks or padding the corpus.

After schema/helper changes run the regressions:

```powershell
.\venv\Scripts\python.exe -X utf8 -B literature/test_corpus.py
```

Exercise the normal lookup commands after substantive changes. For an important synthesis, inspect a bounded, varied sample of primary sources, particularly claims shaping the overview, and record scope/findings in [Use Checks](../literature/Use%20Checks.md). No model approval is required. For a later substantial explanation, use the [HTML Interactive Reports playbook](HTML%20Interactive%20Reports.md) when interaction teaches something useful; the catalog itself need not become an interface.

The 27-field core and search semantics remain compatible with Vision 1.0. Robotics categories and optional context are this project's adaptation; portability does not authorize edits to either reference project.
