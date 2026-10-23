# Prospective after-release public dwell

**Applied and tested by root after the original source hold ended.** The staged originals, proposal and manifest remain unchanged. See `applied-001.json`, `validation-decision-001.json` and `physical-validation-001.json` for separate actual records. Queue `20260923T121322613458Z-dd45dfa8` passed all ten focused checks and 436 Runtime checks; C0-013 completed 3/3 and its fixed-dwell cut was recorded admissible under `20260923T121521761878Z-5a73938e`. Its canonical finish and one-run derivation also completed successfully, with zero derivation integrity findings. This is one prospective physical check, not a universal settling bound; original C0-010 failure remains unchanged. The commands and deferred wording below describe the preserved staging handoff, not unexecuted current work.

The official C0 diagnosis reported a phase-7 raw-to-fixture release with open jaws, no hand contact and approximately 0.82865 N support. Linear speed was approximately 0.0385 m/s, below the existing 0.05 m/s predicate, while angular speed was approximately 0.157 rad/s, above the existing 0.10 rad/s predicate, at the first width sample at or above 0.065 m. These are root-reported completed diagnostic observations motivating a prospective timing choice; this preparation did not read or reprocess raw evidence.

## Exact proposed behavior

`RestartOpportunity` configuration becomes `robot-restart-opportunity-1.2`. The supplied-seed domain, selected cut and transport ordinal do not change. For `after_release` only, start a timer at the first ordinary supervisor sample with the selected transport request active, segment phase 7 and public measured jaw width at least 0.065 m. Match only after those sampled conditions have remained eligible for at least **0.10 simulation seconds**. Departure from the selected request/transport operation, phase 7 or width condition resets the timer. A new qualifying sample starts a new interval; earlier open time is not accumulated.

The existing `observe` caller supplies `sim - base_sim`; wall time, hidden object pose, contact forces, angular velocity and classifier predicates do not gate this milestone. No extra physics step, pause, snapshot, frequency change or sleep is introduced. Duration is computed from the observed start and current simulation clock without a tolerance that permits an early cut. Floating-point rounding may conservatively defer a threshold-edge match to the next ordinary sample. The original 60-second fallback remains active even if the dwell is unfinished; as before, a matched milestone at that sample takes precedence over fallback. Closed-grip transfer and the other two cut families retain their trigger behavior.

Configuration and cut exposure both retain `after_release_open_dwell_s: 0.10` and `after_release_dwell_timebase: simulation_elapsed_s`. Exposure additionally retains `observed_after_release_open_duration_s`: the actual current eligible interval at the cut, zero if an after-release fallback has no eligible interval, and null for other cut families. This field is sampled public timing evidence, not a statement that the payload settled, remained supported or was recovered.

## Retained files and application

`original/Runtime/` contains exact base bytes for `initial_conditions.py` and `test_initial_conditions.py`; `proposed/Runtime/` contains the candidate. `after_release_milestone.patch` is the reviewable textual diff. `manifest.json` records all base/candidate byte hashes. The two existing all-cut/TCP-independence tests now wait for the explicit after-release dwell only; their other-cut assertions remain. The external `test_after_release_milestone.py` adds ten focused synthetic clock/state checks, including reset behavior, exact threshold, actual elapsed reporting, fallback and original-versus-proposed equivalence for the other cuts.

Root can apply after the active derivation/source hold ends and the patch is reviewed:

```powershell
& '.\Long-Horizon Adaptive Robotics Expirement\Batch 01\After Release Milestone Patch\apply_staged.ps1' -Apply
```

Without `-Apply`, that script checks exact retained and live base hashes only. Neither mode has been executed during preparation. It verifies **both** live base identities before writing either file and refuses a changed/already-applied base. It installs the exact candidate bytes, not a newly generated patch. Retain a separate application record; do not rewrite the historical staged manifest to claim tests or physical success.

## Deferred verification commands

From the project root, after the hold and under root's normal scheduling:

```powershell
.\venv\Scripts\python.exe -X utf8 -B '.\Long-Horizon Adaptive Robotics Expirement\Batch 01\After Release Milestone Patch\test_after_release_milestone.py'
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement\Runtime' -p 'test_initial_conditions.py' -v
```

The first command tests only retained staged stdlib modules and synthetic samples. The second is for the installed change and uses the existing Runtime fixtures; root then runs the required full Runtime suite. None of these checks or a new physical run has been executed by this staging task. Passing them would establish software behavior only; whether the fixed dwell changes physical cut admissibility requires new measured evidence.
