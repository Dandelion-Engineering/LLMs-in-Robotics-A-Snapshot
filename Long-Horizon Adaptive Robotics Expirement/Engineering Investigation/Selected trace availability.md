# Unavailable declared inspection slots

Implemented in source after production build/QA 003. **Production rebuild and browser QA are pending.** No canonical record, original evidence, evaluation declaration, Runtime source or production `index.html` was changed by this work.

[selected_trace.py](selected_trace.py) retains every explicit `--trace-selection` slot's original ID, path, reason and order. The limit remains 12; duplicate IDs/paths are refused before loading. Complete metadata, canonical records and supplied paired analysis remain independent inputs.

| Observed evidence | Presentation |
|---|---|
| Required manifest or event stream absent | Unavailable, with exact missing filenames; absent manifest/result stays null. |
| Event log contains no records | Unavailable, with no invented trajectory or sampling counts. |
| Event/motion stream ends with an incomplete final record | Unavailable; original source hashes remain linked; no partial playback is presented as complete. |
| Complete checked trace has failed or invalid outcome | Available for inspection with actual outcome/validity and current correction. |
| Wrong identity, malformed complete record, unsupported schema, payload hash mismatch or source mutation | Build refuses and leaves the previous page untouched. |

Unavailable rows retain `trace_availability`, `selection_entry`, any identity-checked manifest/result and source hashes. Empty event/motion arrays mean playback was withheld; `sampling` is null, not a zero-observation measurement. Hashes identify bytes rather than certify an incomplete stream. No replacement trace is searched for. Existing per-image missing states remain unchanged.

The timeline selector labels unavailable slots, then shows their reason, declaration, current canonical assessment, available terminal metadata and source links. Event controls are absent. Hero and analysis views count selected/loaded/unavailable separately. Switching to an unavailable slot clears a stale event ID from the URL. Legacy `--run-dir` stays strict because it supplies no missing run identity.

Verification: **81 bounded investigation tests passed in 1.749 seconds**; both changed JavaScript files passed `node --check`. Seven new temporary-file tests cover the unchanged 12-slot declaration with 11 unavailable traces and 14 independently retained metadata records, a failed/invalid playable trace, no replacement by unselected successes, truncation/empty logs, wrong identity, corrupt payload before a truncated tail, changing sources and duplicate identities. The existing Node DOM fixture checks unavailable presentation, absent event controls, missing result versus actual failure, unchanged declarations and separate counts. Fixtures never enter project evidence.

The next root-controlled queued build needs browser QA. The prior generated page remains the verified 60,041,396-byte build documented in [Rebuild and QA 003](Rebuild%20and%20QA%20003.md).
