# Assemble an accepted qualification without refitting it

`assemble_qualification.py` consumes a **completed** immutable provisional rule, its completed assessor artifact and the assessor's official successful receipt. It creates no physics, seeds or readiness decision. All current implementation tests use synthetic files only; no real qualification has been assembled by this work.

The CLI is queue-only. After the active worker has naturally exited, submit one invocation through the existing shared queue:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/assemble_qualification.py' --rule '<actual provisional-rule.json>' --assessment '<completed assessment.json>' --assessment-receipt '<retained successful assessor receipt.json>' --acceptance '<root-authored acceptance.json>' --output '<fresh operator output directory>'
```

The command above is the **queued child command**, not permission to run substantial hashing outside the queue. Apply the existing queue limitation: submit only after the preceding worker exits; retain the assembler's official successful receipt after natural completion. The helper independently compares the assessor receipt to installed queue state, its recorded job/entrypoint/output directory and completion time. It rehashes every consumed evidence file and actual assessor dependency before and after assembly. Assessor source hashes/check names are not hardcoded to today's semantic version.

Without `--acceptance`, output is `qualification.draft.json`, `development-freeze.draft.json`, `acceptance.draft.json` and `assembly.json`. Draft status and missing freeze time make these unusable by the actual Runtime loader. `assembly.json` lists absent provisional loader metadata. The draft acceptance supplies identities only; it invents no decision, scope, timestamp or support. Root can also write the acceptance directly using the schema below and use a single queued invocation.

With explicit acceptance, output is `qualification.json`, `development-freeze.json` and completion marker `assembly.json`. The actual current Runtime loader must validate the retained output before the marker is written. A refused/failed partial output stays intact and requires a fresh output directory. Neither the marker nor loader validation proves physical qualification; the root-authored acceptance is the decision. A development freeze has no evaluation authorization, scored readiness or concealed seeds.

## Concrete root acceptance input

This is a schema example, **not an acceptance**. Fill the exact hashes, times, cell IDs, trial scope, evidence references and reasons from the actual completed record:

```json
{
  "schema_version": "operator-restart-qualification-acceptance-1",
  "decision": "accept_unchanged_provisional_rule",
  "operator": "<actual responsible operator>",
  "accepted_at_utc": "<actual timezone-qualified time after official assessor completion>",
  "rule_sha256": "<exact provisional file-byte hash>",
  "assessment_sha256": "<exact assessment file-byte hash>",
  "root_note": "<concrete evidence and limited empirical transfer decision>",
  "validation_review_note": "<all retained validation outcomes, failed actual cuts, outside and unknown states, and resulting limits>",
  "cells": {
    "<unchanged mapped cell ID>": {
      "provisional_cell_sha256": "<canonical digest of exact provisional cell>",
      "root_note": "<specific coupled payload/start/route support and limitations>",
      "validation_scope": {
        "trial_ids": ["<retained selected validation trial supporting this cell>"],
        "note": "<why these observations support this cell; other rows remain visible>"
      },
      "support_refs": [{
        "artifact_id": "<stable actual artifact ID>",
        "path": "<actual file in the assessor consumed_files inventory>",
        "sha256": "<exact file-byte hash>",
        "recorded_at_utc": "<actual evidence record time no later than acceptance>",
        "supports": ["<one or more supported categories below>"],
        "reason": "<which concrete observations support those facts>"
      }]
    }
  }
}
```

Include exactly the rule's mapped cell IDs. Each mapped cell's explicit support decisions must collectively cover the loader's existing categories: `carry_state`, `absence_survival`, `whole_arm_payload_route`, `settled_placement`, `development_validation`. One reference may support several facts only when root explains that actual support; multiple references may be used. There is no mandatory new trial count. Root's `validation_scope` names retained selected trials for that cell; it does not require outside states to pass or erase them. Do not dismiss an in-scope failed actual cut simply because it failed. The helper retains the full assessment unchanged and never converts a failed/unknown row to a pass or infers support from an aggregate pass.

## Exact preservation and limits

Every provisional cell field is copied unchanged. Only physical evidence-reference metadata is appended, preserving any original prefix. Existing references must independently resolve to explicitly supplied support artifacts too; embedded `bytes_verified_by_operator` flags are not authority. New flags are emitted only after hash verification. Root's acceptance pins each original canonical cell, rule and assessment. Class specification, numerical envelopes, correlated scope text, measured points, geometry/absence values, deterministic mapping and untested combinations are preserved. Missing loader fields (`envelope_basis`, `maximum_qualified_absence_s`, clock/endpoint, or numerical fields) are not invented. A changed scope/rule needs its own prospective evidence sequence.

The bundle retains exact file-byte and canonical references to the entire provisional rule and assessment, plus the original cell digests, a compact complete trial-status index, acceptance and actual assembly implementation identities. All construction/validation/outside/fail/unknown rows and detailed observations remain in the immutable referenced originals. Full reports and numerical cells are not duplicated inside the bundle, because Runtime hashes the bundle at a cut. `artifact_files` includes those original files and every reverified consumed input; the loader will rehash them too, so this can be substantial startup work. Absolute D references are supported without moving originals. Protected output should be a fresh operator evidence directory, separate from all input directories and candidate state.

`qualification_granted_by_assembler` and `scored_ready_claimed` remain false. An accepted bundle's `status: measured_development` records root's explicit decision; it is not a helper-derived finding. Actual cuts still pass the existing source/class, grip/route and absence predicates. No cell, bound, validation seed or physical evidence was selected or created during implementation.
