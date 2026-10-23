# Public live records

**Writer:** supervisor/public robot services. **Robot agent:** read-only.

These are public observations and execution records, not hidden evaluation answers. They are recorded during conventional operation as well as during agent assistance.

- `activation.json`: the current incident/request, trigger evidence, activation identity, and restart context. A detector's report is a symptom, not a root-cause oracle.
- `state.json`: an atomically published snapshot with a history high-water mark, task revision, control ownership, running/unresolved actions, and permitted observations. Individual sensor samples retain their acquisition times; writing a new snapshot does not make old samples fresh.
- `events.jsonl`: complete committed records of public task updates, action requests/receipts/outcomes, observations, failures, ownership changes, program execution, and restarts. Read only complete records; the history reader must expose gaps or an incomplete tail explicitly.
- `observations/`: permitted image/data artifacts referenced by stable observation IDs, with acquisition time, sensor identity, frame/calibration, modality, and quality limits.

The initial JSON files are unconfigured examples, not measured state. The host replaces them in a runtime copy. No endpoint/capability is checked in; no action is available until the host publishes an authorized activation. The event log and observation directory initially contain no measurements.

In this development binding, `activation.json` carries `activation_id`, `reason`, `trigger_event_id`, `authority_epoch`, `order_version` and simulation time. `authority_epoch` is the runtime generation and `order_version` is the task revision used by the client. The host's `state.json` uses the same shape as `/status`: root `owner`, `authority_epoch`, `order_version`, `observation_sequence`, `observation_age_s`, `packet`, `active_command`, `commands_recent` and `history_high_water`. The run ID is in the public packet/history. Read exact acquisition times rather than treating state publication as a new sensor sample.

`endpoint.json` uses schema `robot-codex-host-1.0` and supplies a loopback URL and capability. Keep that capability out of notes and output. It can change at an ownership boundary; old invocations must stop rather than adopt another generation. The client pins each invocation's activation identity and never refreshes it to retry a request.

Requested overhead images may be published as `observations/overhead-<sequence>.png`; the public `requested_image_available` event links their sequence. Inspect an actual image through a supported tool before claiming to have seen it. The capture API reports public RGB-D evidence and does not reveal hidden object state.

Bound events use integer `event_id`, `run_id`, `authority_epoch`, `owner`, `source`, `type`, `sim_time_s`, `wall_elapsed_s`, `wall_unix_s` and `payload`. Action/object/observation references are inside payloads. `/history` reports `high_water`, `gaps` and `incomplete_tail`. Command lifecycle and verification are separate fields. There is no dedicated program execution lifecycle in this version; do not infer one from the generic description above.

The supervisor does not automatically write the agent's diagnosis or recovery plan into these files. Its public state may contain existing conventional program status, labeled as such. Precise simulator-derived answers belong only in an explicitly labeled oracle experiment, not in an ordinary observation feed.
