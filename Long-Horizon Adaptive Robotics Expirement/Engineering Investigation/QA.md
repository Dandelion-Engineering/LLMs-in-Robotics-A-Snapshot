# Investigation workspace QA

**Historical QA record; corrected assessment:** The C0-002 success and completion-time statements below describe the then-current raw record, not the current conclusion. Canonical result `B01-dev-C0-002-result-correction-1` withdraws full completion: both inserts remained in the fixture and the old evaluator omitted their completion predicates. The current outcome is **partial**, validity **invalid**, and full-task completion time is unavailable. This is a retrospective correction, not a new physical run or full strict re-score. [Browser QA 002](Browser%20QA%20002.md) verifies the later nine-run page presents this correction before the historical raw claim.

Checked on 23 September 2026 using the project Python and Chrome against a temporary loopback server. These are interface and adapter checks, not scored robot-performance evidence.

## Source checks

- `test_workspace.py`: six passing checks covering empty canonical input, hostile HTML text, atomic failure preservation, attachment hash rejection, lossless evidence archive round-trip, and JavaScript correction/filter/link handling.
- `test_evidence_adapter.py`: six passing checks covering sampling with parent-linked capture retention, zero values, missing frames, explicit event-ID gaps, payload tampering, path escape rejection and checked artifact references.
- `node --check playback.js`: passed.

Test records exist only in temporary test directories and never enter the canonical map.

## Browser checks against canonical records

Verified architecture search and zero-match state, latest-status filters, exact revision selection, all three mechanism lenses, comparison, document/source disclosures, run scope and outcome filters, no-terminal-assessment state, note-history control and empty recorded-timeline state. Chrome reported no JavaScript errors during the tested interactions.

The initial narrow-layout check exposed overflow from the horizontal architecture picker. The source was corrected; at a 390 px viewport the document width was 375 px, including the comparison view and later the real timeline. Keyboard clearing of search and arrow-key timeline navigation were verified. The temporary viewport override was reset.

## Actual recorded evidence check

Loaded the completed `B01-dev-C0-001` bundle after the supervising agent reported queue job `e3ac498a` succeeded with exit status 0. The builder independently checked every event payload hash, source identities, ordering and local frame references. It checks source files again at the end and refuses a build if their hashes changed.

This local playback includes 8,962 of 9,069 event records and 1,501 of 30,000 motion samples. Most captured observations remain because actual candidate-input events parent-link them. All non-observation records are retained; the regular observation target is 2 Hz and motion display target is 5 Hz. The compressed HTML was about 2.9 MB when checked. No replacement motion samples or sensor images were created.

Verified in the rendered interface:

- Event 107 at 9.080 simulation seconds shows the exact attempted candidate-input packet from event 106 and actual RGB frame from observation event 102. The frame loaded as 640 × 480 pixels.
- The privileged toggle instead exposes the prior evaluator snapshot, event 97 at 8.502 seconds, with its 0.578-second age. It shows the recorded A1 position separately from candidate detections.
- The context disclosure exposes the actual `context_write` inside event 107, including the pending transport and recorded feedback. It does not invent a file read or model context: those are explicitly absent from the preceding logged events.
- The action chain connects request 6, admission 7 and physical service event 103. No model request or model output is fabricated for this conventional baseline.
- Event-type filtering, previous/next controls, arrow-key slider movement, stable event-ID URL restoration, source-frame display, privileged-state labels and missing-data states worked.
- The source image at the later help event was inspected visually. The interface does not assign a causal explanation to that image.
- Export produced a valid `investigation-compact-export-1.0` JSON file with the selected event, run identity, 8,962 retained events, 1,501 retained motion samples and hashes for all four source files. The browser automation download-event waiter timed out, but the actual downloaded file was found and parsed successfully; the UI showed no JavaScript error.

The interface accurately displays the recorded terminal assessment: completed execution, failure outcome, unknown validity. It does not convert program completion or the fact of this QA pass into a successful robot task or scored readiness.

## Second development run

Added the finalized `B01-dev-C0-002` bundle alongside the first. Both remain selectable. The combined generated HTML is 3,792,058 bytes. The 12 source checks passed again after the summary change.

Chrome verified that the second run explicitly shows completed execution, successful task outcome, **invalid** timing validity, 3 accepted parts, 142.906 wall seconds to completion, 4 of 142 complete wall windows outside real-time-factor tolerance, and zero false completion assertions. Timing failure has no automatically assigned candidate cause. The first run retains its separate failure outcome and unknown readiness validity.

At second-run event 122, the interface loads actual observation frame 116 (`frames/000099.png`) at 640 × 480, links exact attempted dispatch 120, and shows the real context write from reply 121. The privileged view identifies snapshot 108 and its 0.884-second age. Event-type filtering and event-ID restoration after reload worked; Chrome reported no JavaScript errors. No model output is shown for either baseline.

[Development comparison](Development%20comparison.md) records the observed detection/action difference and the limits of the jaw-return interpretation.

## Limits

This pass covers two real development conventional-baseline traces. No real model-call, candidate-restart, superseding-result or controlled paired experiment was available; corresponding data handling has source-level tests or generic rendering but still needs representative real logs. Paired timeline alignment and deterministic re-execution are not implemented. Exact attempted IPC dispatch is distinguishable from ingestion; the relevant reply is needed to support ingestion. The compact browser export references images and full raw logs rather than bundling every file. Export was exercised on the first run; the second run uses the same export handler.
