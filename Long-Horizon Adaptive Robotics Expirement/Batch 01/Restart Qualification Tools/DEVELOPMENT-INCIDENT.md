# C0-007 / B6 completed-development incident extraction

`extract_development_incident.py` is a narrow queue-only diagnostic for `B01-dev-C0-007`, target B6. It does not alter a run, candidate, map, Runtime file or frame image and does not evaluate the recovery qualification. Preparation inspected source and synthetic events only; no pending raw outputs were opened.

The entrypoint first verifies its own shared-queue ownership, the supplied saved official succeeded/exit-0 execution receipt against the installed queue record, and the unique terminal canonical **development** result binding that run to the same job. The canonical result must already bind the original events and result bytes. The raw manifest/result must agree on run/stage; the visibility projection is pinned to the inspected `candidates.py` hash. Changed candidate semantics require reviewing this narrow extractor.

It opens `events.jsonl` once, hashes every original line/file byte and verifies every event payload hash. The canonical event digest supplies the independent before expectation; the streamed digest supplies the after observation, and size/mtime/ctime must remain unchanged across that pass. Small manifest/result/method/receipt files are rehashed after processing; the canonical map digest must also remain unchanged. The extractor does not call the queue CLI or execute diagnostics/model/physics. Only `incident.json` is written into a fresh derived directory outside originals/map/Runtime/candidate state.

The output contains:

- Help and local/scheduler-rejection anchors with exact event ID, line, byte offset, original line/payload SHA-256 and nested candidate-event index.
- Up to 32 preceding candidate decisions since the last successful resolution/new public answer, including each actual step packet's capture/delivery sequence and time, B6 detection or explicit packet absence, fresh visible part summaries, order, station, gripper, feedback and delivered answers. Repeated decisions on one frame remain repeated decisions.
- Before/after event windows, first subsequent fresh B6 detection, associated existing frame paths/artifact hashes, correlated request/admission/help/answer events, and resulting checkpoint projections. B6 belief and all parts' cycle/inspection/inference summaries remain separate from current visibility; completed history alone does not establish current counts.
- Last B6 detection, last fresh B6 detection, final candidate step/checkpoint, and the full final protected world snapshot separately labeled. Absence from a camera packet does not prove B6 moved or was occluded; final world position alone does not establish earlier image visibility.

At most 16 incidents are retained (first eight and latest eight); middle omissions and truncated decision history counts are explicit. Original locators remain reviewable. Frame references are retained without opening, copying, editing or downloading images. This output identifies evidence for reviewing the fallback/halt hypothesis; it does not itself attribute a cause, upgrade physical success or amend a canonical result.

After the canonical completion records exist, submit this **inner command** through the ordinary shared queue:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/extract_development_incident.py' --receipt 'Long-Horizon Adaptive Robotics Expirement/Evidence/queue-receipts/20260923T064028897100Z-56d90aa6.json' --output-dir 'Long-Horizon Adaptive Robotics Expirement/Evidence/derived/C0-007-B6-incident-001'
```

Preparation: four synthetic tests passed in 0.018 s, including repeated same-frame observe decisions, missing versus stale detection, later fresh target evidence, exact Unicode checkpoint hashing, original/payload hash rejection and unchanged source bytes. No actual event extraction was executed during preparation.
