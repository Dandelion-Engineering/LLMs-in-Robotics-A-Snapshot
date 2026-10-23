# Complete-snapshot compression rebuild

Completed: the rebuild officially succeeded with exit 0, and the generated page passed the bounded browser checks below. The prior verified nine-run `index.html` was 60,574,085 bytes, from successful queue job `20260923T052124760337Z-1721bc38`. No new outcome or scored analysis is introduced by this rebuild.

The source now gzip-compresses the complete exact safe-JSON snapshot. Native browser decompression, length checks and SHA-256 verification complete before panels become active. Unsupported or corrupt input stays visibly unavailable. All 74 bounded investigation tests passed in 1.584 seconds after resumption, including actual Node native decompression, integrity failures, correction precedence, missingness and hostile text. These tests use synthetic temporary fixtures and do not establish browser appearance or robot performance.

| Source | SHA-256 at handoff |
|---|---|
| `build_workspace.py` | `a30bf98969b20492b7a241d2e6b07e92814b8c876de884935784542deb33fca6` |
| `workspace.html` | `d4cc736b9154ab5354a87e18acbe6548a6659a8a44b074db3c1a91d55793c1ed` |

## Exact rebuild command

The root operator owns the serialized queue. Submit only after the previous owned worker and child have naturally ended. Keep all builder/template/adapter/JavaScript/CSS sources fixed while this job runs. This command preserves the same nine explicitly selected development bundles and all immediate raw-run metadata; it supplies no analysis file. Additional raw directories without manifests remain explicit missing-metadata entries rather than invented runs.

```powershell
$investigationRoot = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$investigationPython = Join-Path $investigationRoot 'venv\Scripts\python.exe'
$investigationQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$investigationBuilder = 'Long-Horizon Adaptive Robotics Expirement\Engineering Investigation\build_workspace.py'
$investigationRaw = 'Long-Horizon Adaptive Robotics Expirement\Evidence\raw'
$investigationArgs = @('submit', '--project', 'LLMs-in-Robotics', '--cwd', $investigationRoot, '--', $investigationPython, '-X', 'utf8', '-B', $investigationBuilder, '--metadata-root', $investigationRaw)
foreach ($investigationRun in @('B01-dev-A1-001', 'B01-dev-A1-002', 'B01-dev-A1-003', 'B01-dev-A2-001', 'B01-dev-A3-001', 'B01-dev-C0-001', 'B01-dev-C0-002', 'B01-dev-C0-003', 'B01-dev-C0-004')) {
    $investigationArgs += @('--run-dir', (Join-Path $investigationRaw $investigationRun))
}
& $investigationPython -X utf8 -B $investigationQueue @investigationArgs
```

Record the new job ID and require the official successful state with exit 0 after it ends before accepting the rebuilt file. Record output size/hash and the builder's actual counts; do not copy counts from this plan.

## Browser QA after successful rebuild

Use a fresh local static-server/browser session after the reboot. Verify the generated page, not the source template.

1. Observe loading finish; the workspace becomes interactive with the actual canonical counts. Inspect the mechanism, comparison, search/zero-match and exact revision selection.
2. Open Runs & evidence and choose C0-002. Its current assessment must be partial/invalid, the withdrawn completion reason visible, and its immutable raw success separately labelled historical. Do not present the old 142.906-second endpoint as valid full-task completion.
3. Select actual A1-003 timeline events. Verify the selected event, original RGB image, model request/response and separate context/action panes; preceding sample ages and privileged labels must remain visible. Verify event filtering and keyboard slider/previous-next behavior.
4. Inspect paired analysis: no supplied analysis means explicitly unavailable statistics in all nine slots. All nine independent manifest/result metadata entries remain inspectable; trace selection is not an analysis denominator.
5. Check a narrow viewport and keyboard navigation. Inspect browser console errors and failed local evidence loads. Export one compact snapshot and confirm its selected event/current canonical assessment and source identities remain intact.
6. Confirm the provenance view records the actual canonical store hash. Compression is a representation change only; it neither repairs past evidence nor changes scoring, timing, eligibility or missingness.

Document the actual results below only after performing them. Integrity-error behavior has synthetic source tests; do not corrupt the production page to create a browser demonstration.

## Completed build and browser checks

Queue job `20260923T061122155068Z-587e2b05` ran 2026-09-23 06:11:22–06:15:13 UTC and officially succeeded with exit 0. Its [receipt](../Evidence/queue-receipts/20260923T061122155068Z-587e2b05.json) binds the exact nine-bundle command. Generated `index.html` is **60,041,396 bytes**, SHA-256 `36779f35372c474b95631fc54beaf2b3da686fa0de428127beac03324a0df19a`. The size decrease from the previous representation is modest; no browser-memory saving is claimed.

Fresh Chrome QA through `127.0.0.1:8778` verified successful native decompression and integrity checks: the panels became active with **4 architectures, 9 manifests, 9 current assessments and 9 separately loaded traces**. The rendered provenance reports build time `2026-09-23T06:11:22+00:00` and canonical store SHA-256 `132652eb5202c0a9805a4e2778ebd06bbad92897ed8bc276adda46361e8c38fb`.

- C0-002 shows current canonical **partial/invalid** assessment `B01-dev-C0-002-result-correction-1`, the omitted insert predicates, both inserts remaining in the fixture, and unavailable valid full-task completion time. The superseded assessment remains separately accessible.
- A1-003's actual model-response events were selectable. A right-arrow key moved from event 31 at 2.410 simulation seconds to event 68 at 4.392 seconds. At event 68 the original frame from observation 45 loaded as **640 × 480** pixels, with exact attempted dispatch 46 and its 1.834-second capture age. The model request/response, recorded file write and supplied-context panes remained separate. The action lifecycle names request 36, admission 37 and physical service 39.
- Switching to privileged perspective showed actual snapshot 58 at 3.502 simulation seconds, explicitly labelled evaluator state and **0.890 seconds old** at event 68. Candidate observations were not relabelled as truth.
- Paired analysis explicitly reports no supplied analysis in **all nine protocol slots**. All nine independent manifest/result metadata records remain selectable. No estimate or scored denominator is inferred.
- Zero-match architecture search, keyboard clearing, exact initial-versus-development revision selection, comparison and provenance disclosure worked. Latest development revisions lack optional comparison-description fields; the interface correctly displays “Not recorded” there, while selecting initial design revision `B01-A1-r1` reveals its actual design explanation. No values were inherited or invented.
- The inspected desktop layout had no overlap. At the temporary **390 × 844** viewport, document width was **375 pixels**, with no horizontal page overflow. The override was reset. Chrome reported **no console errors or warnings** during the checks.

This pass did not repeat compact JSON download verification, which was exercised on the earlier real baseline build and remains covered by source tests. It did not corrupt the production artifact to exercise an error screen, inspect every retained event, re-run physics, or establish statistical validity. One attempted image lookup used the prior event's now-absent label after keyboard navigation; fresh DOM inspection found the new frame and verified it. An automation attempt to fill search with an empty string left text unchanged; normal keyboard clearing succeeded. Neither required a source change.
