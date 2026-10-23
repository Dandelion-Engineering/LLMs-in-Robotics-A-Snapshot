# Integrated route validation reuse

Status: **integrated with root authorization at 2026-09-23 09:55:15 UTC**, after official kernel benchmark `20260923T095356285201Z-932e67e1` succeeded/0. Root reported exact paired output agreement and an approximately 25 ms → 5 ms blocker-kernel reduction for the repeated A1 n10 cases. That measurement concerns the kernel only, not the complete classifier or qualification. Earlier five-test verification passed in 0.664 s; after integration, the same five tests plus an installed-source guard passed, **six total in 0.646 s**. No physics, full test suite or queue submission was performed by this implementation task.

The exact base SHA-256 is `324504b47198f46e1b33298708035ae6266f68f5a4a4eab655d81cf8ae43bb30`; its bytes are archived at [restart_state.324504b47198f46e1b33298708035ae6266f68f5a4a4eab655d81cf8ae43bb30.py](source-archive/restart_state.324504b47198f46e1b33298708035ae6266f68f5a4a4eab655d81cf8ae43bb30.py). The installed candidate SHA-256 is **`d5f354c60af83c6f9d32f6b43a893c19486ddcb1f8d2f85c78f526fe48d0273c`**; the same installed bytes are retained in [the corresponding archive](source-archive/restart_state.d5f354c60af83c6f9d32f6b43a893c19486ddcb1f8d2f85c78f526fe48d0273c.py). Application verified the exact base and generated-candidate hashes, archived both byte sequences, checked the still-current base before writing, and verified the installed bytes. Only the narrow blocker replacement was made.

[The guarded proposal builder](pending_route_validation.py) remains under its original name and has no Runtime write path. The initial pre-integration test setup rejected an LF-only replacement anchor against unchanged CRLF source before running any test. Its correction preserves exact original line endings as well as the complete base hash. That failed setup attempt remains recorded; the authorized integration and post-integration tests had no failed attempt.

`_route` already validates each corridor once in its existing malformed-envelope gate. Its blocker expression then calls `overlaps(object_bounds, corridor)` for each possible pair; `overlaps` validates both boxes again. For N other objects and M corridors without an early overlap, this adds 2NM box validations to the M corridor validations, besides constant route/TCP checks. For the ordinary n10 scene's 11 other movable bodies, the corridor-related total is 23M, plus constant checks.

The proposed replacement leaves that original envelope/calibration gate untouched. Only after it passes, iterate the objects in their existing order, exclude the held object's ID exactly as before, fetch and validate each object's bounds once, then evaluate the exact original arithmetic:

```python
all(min(bounds['max'][i], box['max'][i])
    - max(bounds['min'][i], box['min'][i]) > 1e-6
    for i in range(3))
```

The original `any` corridor short-circuit and final sorted blocker IDs remain. No coordinate coercion, rounding, padding, tolerance change, NumPy import, spatial approximation or persistent cache is introduced. Validation reuse exists only inside one valid route evaluation; every new call reads the supplied snapshot anew. The existing `overlaps` helper stays unchanged for all other callers. The arithmetic is inlined in `_route`, avoiding a new helper dependency in the archived-source numerical assessor adapter.

Malformed corridor/type/nonfinite cases still reach the unchanged envelope gate. Invalid other-object bounds keep the original `overlaps` behavior (false), while missing object keys and numeric conversion errors retain their original exception behavior; this proposal does not invent a new handling rule. Payload-ID exclusion precedes bounds access, as before. The main classifier's independent snapshot validity predicates remain unchanged. This reasoning concerns ordinary stable JSON-like captured values, not stateful custom Python mapping getters.

The new validation count for an all-clear valid route is M+N, plus the same constant checks; NM strict intersection comparisons remain. This operation count is separate from the completed kernel measurement referenced above. Whole-bundle hashes and repeated route metadata checks remain outside this change. A fresh source-bound construction and subsequent untouched validation are still required; the earlier construction cannot establish the new source identity's physical/timing qualification.

[Five bounded differential tests](test_pending_route_validation.py) compare full old/new route results or exception type/message with AST-only pure functions; cover strict 1e-6 equality and adjacent floating values on each axis, sorting/duplicate IDs, excluded held-body malformed bounds, malformed/nonfinite/type inputs, prior calibration/route/same-cell gates, within-call validation counts, and snapshot changes across calls. They now read the archived original and verify the installed exact candidate with a sixth guard. All six passed in 0.646 s. The tests establish only this narrow equivalence and source integration, not physical or complete-system performance.

After source hold release, the bounded test command is:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement\Batch 01\Restart Qualification Tools' -p 'test_pending_route_validation.py' -v
```
