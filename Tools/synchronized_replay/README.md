# Synchronized replay tools

[Playbook](../../Playbooks/Synchronized%20Experiment%20Replay.md) · [Home01 adapter](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/investigation/replays/home01/build.py)

`core.py` supplies finite clock bracketing without extrapolation, anchor validation, unknown-aware unified diffs and safe JSON embedding. `viewer.js`, `viewer.css` and `template.html` consume a normalized `window.REPLAY_DATA` object and use one simulation cursor. No external dependencies, telemetry or network services are needed.

The `synchronized-experiment-replay-1` data contract has:

- `meta`: run identity, simulation limits, explicitly scoped final filesystem, limitations and links.
- `anchors`: measured `{wall, sim, id, line}` bridge records. Wall clocks are strictly increasing and simulation times nondecreasing within one declared segment.
- `events`: allowlisted observable `{id, lane, kind, title, wall, sim, at, timing, source, detail}` records. `timing` preserves brackets and IDs. `at` is a conservative navigation/reveal boundary, not an asserted exact event time. Untimed/post-stop records have `at: null` and appear only in a separately marked terminal view.
- `observations`: public captured detections/station/gripper with publication `sim`, capture time, source and line. These are held samples, never interpolated.
- `frames`: byte-identical RGB exports with capture time, first publication time, frame identity, source/hash and availability. All unavailable captures are retained separately as `availability` rows. The recorded camera is held at its last published frame and its age is shown.
- `files`: paths with an ordered `versions` list. Each version contains text or an explicit unknown-content reason, hash/bytes, `at`, timing, evidence class, source and a diff against the previous evidenced version when known. Final snapshots have `final_only: true`, no fabricated timestamp. A public symlink alias must name its target and evidence rather than masquerading as a separate retained regular file.
- `milestones`: semantic jumps bound to actual event IDs. No experiment-specific semantics are built into the viewer.

Adapters must authenticate experiment identity and frozen inputs. The Home01 verifier independently rereads the original sources and recomputes temporal joins and file identities; viewer tests exercise boundary behavior. Original source records remain the authority. `test_core.py` uses synthetic counterexamples only.

The scoped `.gitattributes` preserves exact implementation bytes across Windows checkouts. The existing root attributes already preserve the experiment subtree and derived candidates. Keep hash-bound exports and archived code outside automatic line-ending conversion; changing a hash-bound file requires a fresh derived candidate and verification.
