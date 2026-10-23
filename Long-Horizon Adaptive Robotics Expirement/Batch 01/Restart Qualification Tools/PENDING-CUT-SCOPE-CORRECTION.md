# Integrated cut-admission scope correction

Status: **integrated after root authorization on 2026-09-23**. Geometry job `20260923T084701866943Z-a8a35289` officially succeeded at 08:54:37.9165 UTC before the source hold was released. Its exact assessor dependency bytes are retained in [the hash-named source archive](source-archive/assess_validation.a91dab80916d6f3e7540200504c0257d6933ce2723b0ec3b00a6be2f884ff464.py). The archive SHA-256 is `a91dab80916d6f3e7540200504c0257d6933ce2723b0ec3b00a6be2f884ff464`; the integrated assessor SHA-256 is `300b32a136790802ce57781a7ee8b12e2cfe7923b8702d0d998e3c4f3e783192`.

Artifacts: [reviewed patch, retained under its original name](pending-cut-scope.patch), [synthetic regression and in-memory candidate builder](test_pending_cut_scope.py). Before application, the base hash and patch hash were checked, the generated unified diff was required to equal the reviewed patch bytes exactly, and the archived bytes were checked against the original. Only the reviewed assessor changes were applied. The regression file remains unchanged and writes no active dependency.

## Why this is a semantic bug

[Runtime `classify_restart`](../../Runtime/restart_state.py) applies **both `_grip` and `_route`** to the captured cut state in the `closed_grip_transfer` branch. The common classifier does not require the subsequent dispatch state to lie inside those calibrated cut-admission intervals. [CONSTRUCTION.md](CONSTRUCTION.md) distinguishes cut admission from the measured cut→hold→dispatch transition.

The prior assessor required both `numeric_membership.cut` and `numeric_membership.before_recovery` to pass the same cut envelope. That silently imposed a second admission condition. It could reject a valid measured transition or encourage widening cut bounds to admit unmeasured cut postures. Removing that second cut-envelope requirement corrects the time at which the predicate applies; it does not relax a declared physical success predicate or change envelope numbers.

## Narrow change

- Require cut numerical membership exactly as before, with unchanged archived `_grip` and `_route` formulas.
- Keep the entire pre-dispatch numerical comparison as **descriptive**, including all failures against cut jaw/force/relative-pose/velocity/joint/TCP bounds. Mark both report roles explicitly.
- Preserve required dispatch invariants already available from that comparison: complete supported capture/comparison, the same unique bilateral payload and mapped cell, matching kind/family, actual destination availability and exact destination-region identity, and corridors clear of the observed other movable bodies. Missing/invalid pose evidence stays unknown; a changed blocker stays failed. This does not claim bilateral force or pose was measured at every absence tick.
- Leave required class compatibility, recorded-tick contact/height checks, actual cut→accepted-dispatch clocks, normal accepted admission, all dense interval geometry, sampled other-body/contact checks, independent settled placement, host timing, and raw/source/receipt binding unchanged.
- Retain source event references and add explicit landmark simulation/wall clock pairs, including pre-dispatch and accepted admission.

## Synthetic verification

Before integration, two bounded tests passed in **2.486 s**. After integration, all **12 tests passed in 7.632 s**: the existing ten assessor tests plus those two regressions. The positive cases retain a cut inside its envelope while the later TCP/joint state, and separately its grip pose/force, lie outside that **cut** envelope. The synthetic dense geometry is updated consistently with the later payload position. The original assessor rejected those cases; the integrated version preserves the descriptive failures and passes the remaining checks. Hold/geometry reports and source references are unchanged; the pre-dispatch and admission clocks remain 6.0 s simulation / 6.09 and 6.10 s wall respectively.

Negative cases still reject lost contact, an invalid relative rotation, and a new corridor blocker. Existing out-of-cut-range, transient hold-loss and missing-trial counterexamples retain fail/fail/unknown. All outputs remain non-authorizing. No physical evidence, model, queue, held fixture or Runtime file was changed.

Patch SHA-256: `0f5a72a86d30ed44ace7c93c9a1f34160b109360a2faacb49d4ddd30067020e9`. Regression SHA-256: `be1c71330041e817c6bb4f12a152b881b8617895736082f274028423cb82a435`.
