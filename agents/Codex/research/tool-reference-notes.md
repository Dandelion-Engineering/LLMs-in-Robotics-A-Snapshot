# Literature structure and tool reference notes

Inspected **2026-09-18 PDT**. Both references were available locally and used
read-only. The recorded reference paths had no changes reported by `git status
--short -- <inspected paths>` when their hashes were captured. Whole-file hashes
identify the actual bytes used; the paper/search files were only sampled for
record structure, not imported or reviewed as this project's literature.

## Primary reference: Vision

Location: `C:/Users/cresp/Documents/Dandelion Engineering/Vision`.
Working title: Efficient Visual Processing for Physical AI.
Git HEAD: `64081f4b01785b3a0d4d9fab297c67d3d74970c4`.

Inspected README, Schema, literature-map playbook and validator; sampled the first
two paper records and first two search records. The user-requested shared 27-field
core, common meanings, review levels, identity semantics and search-log layout
derive from Vision schema 1.0. Vision's existing validator has numeric discovery
gates; these were not retained in the robotics profile.

| Reference file | SHA-256 |
|---|---|
| `literature/README.md` | `9737b16df409d3a38c2f2f997a8595a03299b9f7a5f5811ccea69e6f58be5109` |
| `literature/Schema.md` | `0612a1da23406c7f874d39927fa8b888eb4e296f6269eda2882158edffcf981a` |
| `Playbooks/Literature Map.md` | `b6f3bedfe04ae1791ec2690e9813ad00b5813e46e22dd4bfcff53e96dd778564` |
| `literature/papers.jsonl` (whole file; only first two records inspected) | `c2095a4fbc82c5027bf96500bbd72cca3273c3bcf6085b1442d64d92c0672acf` |
| `literature/searches.jsonl` (whole file; only first two records inspected) | `270bf868b573ee5838befad2135cdbcaddfe6f1dfcc701ea9d6a5adeea4f3200` |
| `literature/validate_corpus.py` | `4051e7fabbacb0f67b00718488ad27aad21e0cb9030ccc5027157301b60f01a5` |

## Portable tool reference: [private project name redacted]

Location: `[private path redacted]`.
Repository named by the assignment: `[private project link redacted]`.
Git HEAD: `773bde1e79bf7ce92be9a75be7cef58101d4e1fe`.

Inspected README, Schema, literature-map playbook, `corpus.py`,
`validate_corpus.py`, and `test_corpus.py`; sampled the first paper and first
search record. No unrelated laboratory data or analyses were accessed. Reused
the small standard-library CLI, identity normalization, generated-catalog/current
metrics pattern, structural/search checks and synthetic regression structure.
No papers, scientific statements, domain rules, historical events or count goals
were copied into the robotics corpus.

| Reference file | SHA-256 |
|---|---|
| `literature/README.md` | `a9602c8792291593f5ca654640659cf58183a3d1306da1b1c0490e04d1f678e4` |
| `literature/Schema.md` | `8ee71daad7d0f7df4b3d48332f8888060ff2c128aad70e5e5074ecf514a6de94` |
| `Playbooks/Literature Map.md` | `3fd4c4236b092b1b9d7f63da4d4b2510b3c225918702508e481219d9b5673663` |
| `literature/papers.jsonl` (whole file; only first record inspected) | `dcf60804fcb946510777bea06f6d58474c7e1aeac1f410b88230bb2d0ff5f41c` |
| `literature/searches.jsonl` (whole file; only first record inspected) | `5dcdf4f013512cdbb19da3d376dd2c88624678779a89f3105dee9fc663efe8a9` |
| `literature/corpus.py` | `198d6a412b82884ca1c828ec98cd2c8843e5d8e2f498dd05ccce2504ee573b24` |
| `literature/validate_corpus.py` | `8ab290788acdd58dd033ad84437230fc97d2066ac31a4d3cdd8397393cf8ab0a` |
| `literature/test_corpus.py` | `1a2b6ee41831004691fc7e1ea97215f3b46ae0b44c1d7d1aade7a4ac7c530f87` |

## Local adaptation and checks

The local profile is `llm-robotics-1.0`, derived from Vision core `1.0`.
It substitutes the 12 robotics seed categories, keeps the 27 exact top-level
paper fields, permits `efficiency_targets: []`, and defines the optional
`robotics_context` string/null members. Structural validity and editorial coverage
judgment are separate; there is no minimum paper count or per-category quota.

Additional maintenance checks reject duplicate JSON object keys, non-JSON numeric
constants, malformed/future dates, identifier/alias collisions, invalid search
references, unsafe/nonexistent material-use file paths and malformed marker
layouts. Arbitrary verified aliases and normalized DOI/arXiv forms support exact
lookup. Catalog links escape Markdown-sensitive title/URL characters. The view
generator preserves all bytes outside the current-metrics markers, including
existing line endings and manual/historical notes.

Working interfaces from the repository root:

```powershell
python -X utf8 -B literature/corpus.py lookup 'feedback' --limit 5 --json
python -X utf8 -B literature/corpus.py lookup --id 'a verified canonical ID or alias' --json
python -X utf8 -B literature/corpus.py lookup --category memory_continuity --tag persistent-memory --status abstract_reviewed --json
python -X utf8 -B literature/corpus.py build
python -X utf8 -B literature/validate_corpus.py --output literature/validation.json
python -X utf8 -B literature/test_corpus.py
```

Lookup uses literal case-insensitive substring text, exact category/tag/status,
and exact normalized identities; filters combine with AND. JSON output reports
total matches separately from returned records. No matches exits 1. The global
`--corpus <candidate path>` option precedes `lookup` or `build`; validator
`--searches` defaults to `searches.jsonl` beside the selected corpus.

Discovery Map requires exactly one ordered pair:

```text
<!-- BEGIN GENERATED CURRENT METRICS -->
<!-- END GENERATED CURRENT METRICS -->
```

On 2026-09-18, `python -X utf8 -B literature/test_corpus.py` passed **23**
synthetic regression tests. These exercise malformed types/JSON, dates, duplicate
identities/aliases, the robotics profile, sources, search references, material
uses, empty efficiency lists, quota-free coverage reporting, stale views, safe
marker replacement, repeated regeneration and CLI JSON lookup. All generated
test corpora/views live in temporary directories. No canonical corpus, search
log, Catalog, Discovery Map or validation report was written by the helper-test
work. These tests validate software contracts, not research accuracy or actual
source reading. Current-corpus integration and source sampling are separate
checks performed by the lead session.
