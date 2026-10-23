# Runtime 004 A-only relocation qualification

Prepared source only. No command, test, compilation, physical trajectory, derivation or acceptance has been executed by this preparation. Original Runtime, r3, prior tools and evidence are unchanged. [copy-provenance.json](copy-provenance.json) identifies each copied source. The target is the sibling experiment directory **Runtime 004**, including its real absolute Panda asset path.

The exact old [13-row plan](Recovery%20Profile%20Qualification/plan-001.json) is copied unchanged. Root selected new physical runs on these **previously inspected development worlds**, not held-out validation: seven high-profile A1→fixture construction trials, three high-profile relocation checks and three conventional-profile transfer checks. All six later checks consume one unchanged provisional rule. The original three baseline failures remain in the original assessment and [Recovery Profile Results](../../Recovery%20Profile%20Results.md); neither successful relocation nor new results erase them.

Scope remains part:A near A1, parking1, the .25/1.0 high profile and .16/.8 baseline check, five requested simulation seconds, with the separately enforced **5 wall-second before_cancel→recover_held_admitted** bound. B, parking2, other starts and the low/slow corner remain unsupported. Fixed mass/friction domain, cut predicate, all-tick hold/geometry observations, caps, numerical predicates, unknown states, boundary exclusions and exact receipt checks remain unchanged. Descriptive path comparison does not waive the changed compiled class.

## Complete prospective inputs before construction

Root must review and complete these local artifacts before any physical run, then hold all files inventoried by the driver through validation:

1. Copy `Recovery Profile Assembly Tools/root-profile-choices.template.json` to `root-profile-choices-001.json` in that same directory. Set real `created_at`, `selected_by` and root-adopted status. The numerical policy remains byte-value identical to the original policy: 50 mm bins, 10 mm materialized padding, no extra sampling allowance, q ±.03 and qdot ±.10. The only measured centers/relative rotation come from the new `parking1-high-corner-A-5` cut; new corridors use every new construction interval. Do not substitute an old cut, fit validation, widen to baseline or assert that remeasured cells will be byte-identical.
2. Complete [relocation-declaration-001.json](Recovery%20Profile%20Qualification/relocation-declaration-001.json): real `declared_at_utc`, `declared_by`, status `root_adopted_before_execution`, and `prospective_choices_ref={"path":actual_absolute_choice_path,"sha256":actual_choice_file_SHA256}`. The pending null fields intentionally prevent a physical launch. The plan hash is the actual copied plan identity. Exact copied world values reside in that plan and are validated by the unchanged finite-plan function.
3. Record/hold the complete new tool and Runtime source identities. The driver archives real experiment-relative paths and checks before/after hashes. The choice file itself is in the original construction archive; materialization requires that original manifest's choice pin as well as its explicit `--choices-sha256`. Complete adoption before calculating final source inventories. No measured class/ref/outcome/acceptance placeholder is executable evidence.

The common numerical support library is copied as `assemble_provisional_rules.py` with its retired two-destination executable portion removed. Its unchanged old fixed allowance JSON remains an explicitly historical numerical reference, not measured support for Runtime 004. The versioned A-only materializer is the only provisional authoring CLI used here. SOURCE_KEYS and protected physical class rules are unchanged; only file-root and exact archive-member references are adapted.

## Queued payloads

Set these ordinary path variables from the project root. All commands below are **individual installed-queue submissions**. Wait for each job's natural completion and every retained owned PID to exit, retain its official receipt, and stop on any failure before the next submission. No nested submission/status call occurs in a helper. Use fresh output suffixes after any failed attempt; retain partial evidence.

```powershell
$Work = 'C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics'
$Py = Join-Path $Work 'venv/Scripts/python.exe'
$Queue = 'C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py'
$Exp = Join-Path $Work 'Long-Horizon Adaptive Robotics Expirement'
$Q = Join-Path $Exp 'Batch 01/Release Lifecycle Repair 001/qualification-tools'
$Profile = Join-Path $Q 'Recovery Profile Qualification'
$Tools = Join-Path $Q 'Restart Qualification Tools'
$Data = 'D:/CodexEvidence/LLMs-in-Robotics'
$Choices = Join-Path $Q 'Recovery Profile Assembly Tools/root-profile-choices-001.json'
$Rule = Join-Path $Exp 'Evidence/derived/runtime004-profile-provisional-001/provisional-rule.json'
```

Deferred checks use only synthetic records and source metadata; they do not compile/step a model. These are prepared tests, not passing results:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B -m unittest discover -s $Q -p test_versioned_bindings.py -v
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B -m unittest discover -s $Profile -p test_profile_screen.py -v
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B -m unittest discover -s (Join-Path $Q 'Recovery Profile Assembly Tools') -p test_materialize_profile_rule.py -v
```

After Runtime 004 and hardlinked asset contents are complete and stable, compile a single fixed public development scene in each isolated process. No renderer, Cell instance, physics step or scored manifest is used:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Q 'compiled_identity.py') --output "$Data/runtime004-compiled-identity-001"
```

`comparison.json` is `runtime-relocation-compiled-identity-1`, with its actual parent queue proof, input inventories before/after, source status, helper hashes, child result refs, source/assets/native/class/component comparisons and XML comparison. Each child retains exact XML, class spec, seal, normalized scene, registry and source/native identities. Actual XML and separately descriptive meshdir-normalized diffs are retained. Expected path-sensitive mismatches are observations, not compatibility grants. Failed child logs/partial outputs remain. This is a compilation diagnostic only and establishes no host timing or trajectory support.

Once the prospective declaration/choices are actually adopted, run seven construction trials:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Profile 'run_profile_screen.py') --plan (Join-Path $Profile 'plan-001.json') --destination parking1 --phase construction --output "$Data/runtime004-profile-construction-001"
```

Set `$ConstructionReceipt` to that actual official successful receipt, then extract:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Q 'Recovery Qualification/extract_screen.py') --screen "$Data/runtime004-profile-construction-001" --queue-receipt $ConstructionReceipt --output "$Data/runtime004-profile-construction-extraction-001"
```

After setting `$ConstructionExtractionReceipt` to its actual successful receipt, compact and then derive the dossier as separate jobs:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Q 'Engineering Investigation/compact_construction_corridors.py') --construction-extraction "$Data/runtime004-profile-construction-extraction-001/extraction.json" --screen-receipt $ConstructionReceipt --extraction-receipt $ConstructionExtractionReceipt --destination parking1 --output "$Data/runtime004-profile-compact-parking1-001"
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Tools 'bundle_construction.py') --construction-extraction "$Data/runtime004-profile-construction-extraction-001/extraction.json" --destination parking1 --output "$Data/runtime004-profile-construction-dossier-001"
```

Retain `$CompactReceipt` and `$DossierReceipt`. Set `$ChoicesSHA256` to the hash already pinned in the **pre-construction declaration**, not a newly chosen policy after viewing outcomes. Materialize all seven construction dispositions against that policy. Contradiction/unknown stops without a rule; boundary points confer no class support:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Q 'Recovery Profile Assembly Tools/materialize_profile_rule.py') --choices $Choices --choices-sha256 $ChoicesSHA256 --construction-extraction "$Data/runtime004-profile-construction-extraction-001/extraction.json" --screen-receipt $ConstructionReceipt --extraction-receipt $ConstructionExtractionReceipt --dossier "$Data/runtime004-profile-construction-dossier-001/construction-dossier.json" --dossier-receipt $DossierReceipt --compact "$Data/runtime004-profile-compact-parking1-001/compact-corridors.json" --compact-receipt $CompactReceipt --output (Join-Path $Exp 'Evidence/derived/runtime004-profile-provisional-001')
```

After successful materialization/receipt, preserve the complete rule bytes and launch all six later checks:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Profile 'run_profile_screen.py') --plan (Join-Path $Profile 'plan-001.json') --destination parking1 --phase validation --provisional-rule $Rule --output "$Data/runtime004-profile-validation-001"
```

After setting `$ValidationReceipt` to its official success:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Q 'Recovery Qualification/extract_screen.py') --screen "$Data/runtime004-profile-validation-001" --queue-receipt $ValidationReceipt --output "$Data/runtime004-profile-validation-extraction-001"
```

After setting `$ValidationExtractionReceipt`:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Tools 'assess_validation.py') --rule $Rule --validation-extraction "$Data/runtime004-profile-validation-extraction-001/extraction.json" --validation-receipt $ValidationReceipt --extraction-receipt $ValidationExtractionReceipt --output "$Data/runtime004-profile-assessment-001"
```

After setting `$AssessmentReceipt`, draft assembly creates a reviewable acceptance template with actual artifact refs. It grants nothing:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Tools 'assemble_qualification.py') --rule $Rule --assessment "$Data/runtime004-profile-assessment-001/assessment.json" --assessment-receipt $AssessmentReceipt --output (Join-Path $Exp 'Evidence/derived/runtime004-profile-assembly-draft-001')
```

Root reviews actual support, timing and all six outcomes, including every failed/unknown baseline row. If warranted, author a separate actual acceptance decision from that draft, explicitly naming the supported high-profile trial IDs; do not modify the provisional numerical cell. Set `$Acceptance` to that completed decision, then:

```powershell
& $Py $Queue submit --project LLMs-in-Robotics --cwd $Work -- $Py -X utf8 -B (Join-Path $Tools 'assemble_qualification.py') --rule $Rule --assessment "$Data/runtime004-profile-assessment-001/assessment.json" --assessment-receipt $AssessmentReceipt --acceptance $Acceptance --output (Join-Path $Exp 'Evidence/derived/runtime004-profile-qualification-001')
```

Successful accepted assembly uses the actual Runtime 004 loader and retains unchanged standard `assembly.json`, `qualification.json` and `development-freeze.json` schemas. Bind its exact successful receipt and file hashes before separately declared online A3 lifecycle checks. This procedure creates no scored release, scored seeds, universal carry coverage, held-out validation claim or readiness decision. Discrete native-state corridor/empirical transfer limitations remain; trajectory contact policy is not established by corridor containment.
