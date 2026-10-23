# LLMs in Robotics literature map

Start with the [Discovery Map](Discovery%20Map.md): architectural alternatives, a small set of original-paper entry points, current coverage and gaps. Browse the generated [Catalog](Catalog.md), then retrieve the records that answer your question. This is a discovery checkpoint; it does not choose a robot task, body, model or architecture.

Read [Accessing and Updating the Literature Map](../Playbooks/Literature%20Map.md) before research searches or substantive updates. [Schema](Schema.md) defines the shared Vision core 1.0 and the `llm-robotics-1.0` profile.

| File | Responsibility |
|---|---|
| [papers.jsonl](papers.jsonl) | Canonical paper records; one UTF-8 JSON object per physical line. Edit current records, preserving earlier source events. |
| [searches.jsonl](searches.jsonl) | Actual discovery, source-access, metadata and resource-check provenance. |
| [Catalog.md](Catalog.md) | Generated category index; category membership overlaps. |
| [Discovery Map.md](Discovery%20Map.md) | Generated current metrics plus maintained orientation, limitations and dated checkpoints. |
| [corpus.py](corpus.py) | Focused lookup, schema checks and generation of views. |
| [validate_corpus.py](validate_corpus.py) / [validation.json](validation.json) | Repeatable structural checks and results bound to canonical file hashes. |
| [test_corpus.py](test_corpus.py) | Small regression suite for schema, identity, lookup and view preservation. |
| [Use Checks.md](Use%20Checks.md) | Bounded source checks and demonstrations of the questions the saved map can answer. |

## Retrieve focused evidence

Run from the project root in PowerShell, using the existing project Python environment. These tools require only the Python standard library; no packages were installed for this map.

```powershell
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup 'VoxPoser' --json
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --id 'arxiv:2209.07753' --json
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --id 'doi:10.48550/arXiv.2306.17582' --json
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --category memory_continuity --limit 8
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --tag development-time-llm --json
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py lookup --category code_generation_tools --status full_text_skimmed --limit 8
```

Text search is a case-insensitive substring over each complete record. ID lookup includes verified aliases; category, tag and status filters are exact and combine with AND. The total match count and display limit are separate. Tags are descriptive, not a complete ontology: a negative keyword result does not establish absence of a capability. Use `--json` to inspect the full reading basis, sources and qualifications before relying on a summary.

## Regenerate and validate

```powershell
.\venv\Scripts\python.exe -X utf8 -B literature/corpus.py build
.\venv\Scripts\python.exe -X utf8 -B literature/validate_corpus.py --output literature/validation.json
.\venv\Scripts\python.exe -X utf8 -B literature/test_corpus.py
```

`build` regenerates the Catalog and only the marked current-metrics block in Discovery Map. Maintained explanatory prose and dated checkpoints stay outside that block. Validation checks both canonical structure and whether generated views match the records. It does not certify scientific truth, actual source reading, complete search coverage, replicated results or commercial usability.

Initial [research provenance](../agents/Codex/research/README.md) records reference locations/hashes and source-lane handoffs. Lane files are historical session inputs, not an alternative canonical corpus. Never regenerate current records from them.
