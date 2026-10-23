# Prospective evidence-method host diagnostic 007

The fixed four-minute, no-model probe passed all eight original diagnostic checks on frozen `RCI001-C02-dev-024`. Direct official queue status was freshly authenticated and exactly matched the [retained receipt](../qualification/RCI001-C02-host-probe-007/official-status.json): `20260928T033202939413Z-3064d7e4`, succeeded with integer exit status 0, from 2026-09-28T03:32:03.207664Z to 03:36:05.308914Z. The [original independent assessment](../qualification/host-probe-007-assessment.json) and [registered result](../../../Architecture%20Map/releases/RCI001-C02-dev-024/result-RCI001-C02-host-probe-007/result-record.json) preserve valid/unknown diagnostic evidence. No model or recovery score is inferred.

The physics owner advanced 120,000 ticks and retained 240,003 timing samples. Maximum lag was 3.1715 ms; the maximum sample gap was 4.0637 ms. Zero of 240 complete windows failed the unchanged real-time-factor tolerance. All 26,383 published messages were drained: 24,000 motion samples and 2,383 captures, with 2,384 journal observations including the initial observation. Source/completeness, scheduling, memory, GC, and resource gates passed. No native recovery command was accepted.

The [owner timing summary](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-007/host/timing-v2.json) and [complete owner sample ledger](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-007/host/timing-samples.bin) measure physics advancement. The [supervisory timing summary](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-007/host/supervisory-diagnostics/timing-v2.json) and [separate supervisory samples](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-007/host/supervisory-diagnostics/timing-samples.bin) measure synchronous journal, atomic-state, registry and FULL SQLite persistence on the other thread. Passing owner timing does not establish that earlier storage stalls disappeared or qualify supervisory timings against physics gates.

The [checks-003 receipt](checks-003/repair-test-receipt.json) binds 93 passing harness tests and 173 passing assessment tests to dev024. Its input and output hashes were rechecked. The [prospective READ_EVIDENCE_V2 method](READ_EVIDENCE_V2.md) is in the frozen snapshot and archive, together with the ordered literal-read and canary successful-exit proof helpers. Static reads require trusted initial bytes; nonempty resumed Continuity comes from protected hash-addressed history. Ordered literal cat chains must consume exact byte segments, and live segments must match their frozen producer and protected identity. Empty composite Continuity remains unsupported.

The additional canary proof is explicitly limited to check values: a source-bound sole protected canary invocation, authenticated successful exit, fixed 45-check fixture, closed environment and exact retained note must agree. This prospective method does not prove variable errno/stderr details, exact emitted JSON bytes, original redirected-output identity, or model attention. It must keep `canary_output_captured: false` when stdout was redirected; a later model-writable note is not independently captured canary stdout. Source changes invalidate the reviewed successful-exit implication.

These tests and an idle diagnostic do not qualify fresh model-loaded behavior, command-grammar coverage or timing. [Smoke003](smoke-003-read-recognition-analysis.md) and [smoke004](smoke-004-read-recognition-analysis.md) remain failed/invalid under their original assessments. The [v7 readiness declaration](../qualification/final-qualification-007-readiness.json) requires five fresh stages: native006, boundary007, smoke005, pilot-stock004 and pilot-home004. Only native006 launch metadata is known at this analysis; no running outcome is consumed. There is no final qualification pass, scored launch or campaign terminal claim.

## Exact source and evidence identities

- Manifest: `6b0b4199ac30f31454af85281b07633c95c86951bd99cf0c36b186c898c2d3d9` (7,921 bytes).
- Source snapshot: `e09d0afc965619f1da46b30795fa5938429156bf9b34968300594b2f4d08e121` (169,355 bytes).
- Source archive: `95c3a151d9e5a639afd7332fc86f8d37fd81b1e2697588ac217d06d819e72439` (1,605,239 bytes).
- Method READ_EVIDENCE_V2: `709c98816d707aa8d932f8e15e42919831115df3da0c9d26b12c8d7efd26de73` (6,194 bytes).
- Official queue receipt: `3096506e23ad8509fa9ed7dee4ef0d0a1c7681272aeb4ab4b29d9d987857b829` (1,556 bytes).
- Original diagnostic assessment: `1e830b8eafdf89a60584aa4970be214016df19da72bfdb72dcc5fc32e5737786` (76,598 bytes).
- Checks003 test receipt: `69427468d01cf231ae84c2be5668ab3af0e6e651521bded482ff25dec3b0d8fd` (8,077 bytes).
- V7 readiness: `adcc9d3e85ad4052d7d14899ac8ab4eeb1be7be8ca0535fe8dce6941d2148b18` (3,040 bytes).
- Owner timing summary: `e00d5b184efa5c00999dde82c6a0c82985544f1f6a5db11c6ea8070e15b2e499` (68,533 bytes).
- Owner sample ledger: `e1f4951aa10e2cc85c7840be46cdc5109a30dd07f26c5812b3f0208015601830` (3,840,048 bytes).
- Supervisory timing summary: `9085c0187dc79bd872d613b4b70b0e756e62a55638373122fb2ed4e55f11102e` (126,462 bytes).
- Supervisory sample ledger: `6a89e59ee2c0de1ca6edaf9597f7f2044ba9991bcd73dc614d05149513a2114e` (32 bytes).

Frozen repaired assessment entries:

- `assess.py`: `36570e0cb9b5f41a92e35b0368dbc8e203f0a94476f24c551f19aa1a9175ce9b` (38,587 bytes).
- `assess_smoke_v2.py`: `f5fc1d7f0044c75b390be5a97b459924146634769c164223b065239d957e1b60` (37,433 bytes).
- `retained_reads.py`: `43c5489b1c0dd995bd3123ac8e6c66021ccaf4c6f7b0b45cbfa8a0904396326e` (15,086 bytes).
- `literal_read_segments.py`: `1a5e7624a709e18fed08c560eb86fab122390d1cae2e0e72e8a45b02e558d851` (17,148 bytes).
- `canary_exit_proof.py`: `a9a9c338b398b39c4fc38615c0abcebd4b72a829f24876691d3918fd2047ad9f` (13,895 bytes).
- `empty_startup_reads.py`: `104b3cf78274353de8b5cdc9ab73df7b37dfab46378ccc6d78c23b2af20c9b31` (16,009 bytes).
