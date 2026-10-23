# Prospective loopback fixture logging correction

Declared before source copies, edits or tests: 2026-09-29T05:37:54.198777+00:00. Original development-001 execution remains failed/incomplete, receipt SHA `4f4718e83f6d381ec73c90d0f096dfa80558fbd95bcd8ddaec840793aa53be6a`; no result is promoted.

The original `Recorder.emit(kind, **fields)` is called as `emit("receive_terminal", case=name, **value)` where `value` already contains `kind`. Python rejects this duplicate argument with TypeError. The `case_error` logging path repeats the collision via `**observation`, obscuring the first failure.

Copy the unchanged 001 fixture and launcher into this fresh directory. Change only those two call sites to `observation=value` / `observation=observation`, preserving the outer event kind and nested observation kind. Add literal TypeError to the existing finite safe exception-class mapping for accurate diagnostic classification. Include this declaration in the launcher's source manifest. Fixed four cases, payload, deadlines, limits, socket operations, result/cleanup criteria, native adapter imports and launch guards stay unchanged. HERE naturally binds execution-001 inside this new directory.

First retain a deterministic no-socket regression against exact 001 source, then verify the corrected source and every emit caller. No fixture main, launcher main, real sockets, native process, model, queue job or qualification is executed by this correction task. Root may separately review and authorize the new one-shot loopback execution. All original001 files are immutable; exact before/after preservation and source delta will be retained.
