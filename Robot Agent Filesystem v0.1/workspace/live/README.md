# Public live records

**Writer:** supervisor/public robot services. **Robot agent:** read-only.

These are public observations and execution records, not hidden evaluation answers. They are recorded during conventional operation as well as during agent assistance.

- `activation.json`: the current incident/request, trigger evidence, activation identity, and restart context. A detector's report is a symptom, not a root-cause oracle.
- `state.json`: an atomically published snapshot with a history high-water mark, task revision, control ownership, running/unresolved actions, and permitted observations. Individual sensor samples retain their acquisition times; writing a new snapshot does not make old samples fresh.
- `events.jsonl`: complete committed records of public task updates, action requests/receipts/outcomes, observations, failures, ownership changes, program execution, and restarts. Read only complete records; the history reader must expose gaps or an incomplete tail explicitly.
- `observations/`: permitted image/data artifacts referenced by stable observation IDs, with acquisition time, sensor identity, frame/calibration, modality, and quality limits.

The initial JSON files are unconfigured examples of envelope structure. They contain no measured state; the event log and observation directory are intentionally empty. The builder documents the actual schema once bound.

Each event needs an ordered ID, run and generation, source, type, available wall/simulation times, related action/object/task IDs, and payload or artifact reference. Record reception time separately when acquisition time is unknown. Retain enough episode history to resolve outstanding actions without rereading raw video. History lookup must not expose another trial, hidden state, or future disturbances.

The supervisor does not automatically write the agent's diagnosis or recovery plan into these files. Its public state may contain existing conventional program status, labeled as such. Precise simulator-derived answers belong only in an explicitly labeled oracle experiment, not in an ordinary observation feed.
