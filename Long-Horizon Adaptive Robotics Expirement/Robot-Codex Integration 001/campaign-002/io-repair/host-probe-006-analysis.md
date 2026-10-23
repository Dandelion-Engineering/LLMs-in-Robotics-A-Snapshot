# Repaired-source host diagnostic 006

The fixed four-minute, no-model probe passed all eight original diagnostic checks on frozen `RCI001-C02-dev-020`. The official shared-queue status was independently refreshed: job `20260928T024505974537Z-a07e4a3a` succeeded with integer exit status 0 (02:45:06.230628Z to 02:49:08.309342Z on 2026-09-28). The [retained queue receipt](../qualification/RCI001-C02-host-probe-006/official-status.json), [independent assessment](../qualification/host-probe-006-assessment.json), and [registered result](../../../Architecture%20Map/releases/RCI001-C02-dev-020/result-RCI001-C02-host-probe-006/result-record.json) retain this bounded diagnostic as valid/unknown, with no model calls, recovery score, or campaign admission.

The owner advanced 120,000 ticks and retained 240,003 timing samples through 240 complete one-second windows. Maximum lag was 2.9960 ms, maximum sample gap 3.8975 ms, and zero windows failed the unchanged real-time-factor tolerance. All 26,383 published messages were drained: 24,000 motion samples and 2,383 captures, with 2,384 journal observations including the initial observation. Strict timing, source/completeness, scheduling, GC, memory, and resource checks passed. No native recovery command was accepted.

The [owner summary](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-006/host/timing-v2.json) and [complete owner samples](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-006/host/timing-samples.bin) establish physics timing. The [separate supervisory summary](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-006/host/supervisory-diagnostics/timing-v2.json) and [supervisory samples](../../local-evidence/campaign002/qualification/RCI001-C02-host-probe-006/host/supervisory-diagnostics/timing-samples.bin) retain synchronous journal, atomic state, registry, and FULL SQLite persistence timing on the other execution thread. This separation does not show that the earlier storage stalls disappeared or qualify supervisory timings against physics gates.

The [checks-002 repair receipt](checks-002/repair-test-receipt.json) binds 93 passing harness tests and 137 passing assessment tests to dev020. Its retained input and output hashes were rechecked. The source changes prospectively recognize a specific authenticated read-only Python empty-Continuity recipe and a status-preserving four-line canary command with stdout/stderr redirection. The [smoke003 diagnosis](smoke-003-read-recognition-analysis.md) remains separate from its original failed assessment: 59/61 checks, invalid/unknown, unchanged.

Known limit: recognition covers explicit command grammars and complete authenticated evidence, not arbitrary semantically equivalent shell/Python programs. The empty-read proof must establish the actual read-only recipe, trusted process and import boundary, output bytes, and protected chronology. Initial emptiness plus a compound cat/listing and absence of a protected commit is insufficient because `.continuity/Continuity.md` is model-writable. These bounded tests and an idle probe do not establish recognition coverage or model-loaded timing in fresh model runs.

The [v6 readiness declaration](../qualification/final-qualification-006-readiness.json) calls for five fresh stages: native005, boundary006, smoke004, pilot-stock003, and pilot-home003. At this analysis, only launch metadata for native005 is known; no running output or speculative result is consumed. No model instructions, policy, criteria, or timing thresholds were changed, and no historical assessment is promoted to a pass.

## Exact identities

- Manifest: `d5c1206c163d2ab13372f853b391b3ecb89cf2ebf7ff7bd3685a8c0e7216f8f3` (7,290 bytes).
- Source snapshot: `2d53ad11ecb68774ebd1af11b2bf4aee5631dde6902b21d8fec87b14cb527b31` (168,160 bytes).
- Source archive: `3b46735d36d828baf3faec26368820fde2250670d7539574841be7ce8e22ff33` (1,581,619 bytes).
- Official queue receipt: `63f1c36f930767c3d9f2a3e5cba4efacc4b6fd657224b3b4aaa53304f3fc467d` (1,557 bytes).
- Original diagnostic assessment: `bc4ed95d1f0a283be318ae7219659fb729114658704d147038419a4a23445fed` (76,604 bytes).
- Repair test receipt: `ae301fce7b0ca70ff12c7e40cce18d582c525d173761edf2691cb7a096b265d3` (7,419 bytes).
- Owner timing summary: `6c530b487f5b0b61d71f107c5f7fae72615f432adf776d7aab97b9c0d4cd27a3` (68,546 bytes).
- Owner sample ledger: `5f99808c6eee12778ea09c64a6934fd63d39e34089bfd56f7f43be5967698dc6` (3,840,048 bytes).
- Supervisory timing summary: `2fa4bad48b70632bd923cbea07e4566198fd2ebacca0664cffc1068235369ec2` (126,491 bytes).
- Supervisory sample ledger: `2912c0236a58c23fbcdb17beec7d6eb21704de1a06413cca03dc574d069f1053` (32 bytes).

Repaired source entries are preserved in the dev020 archive and source snapshot:

- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/retained_reads.py`: `d2c19a3c454038bfbd1787bcd6b969366379a39291d727c0b2f897dfdc6366a0` (14,754 bytes).
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/empty_startup_reads.py`: `104b3cf78274353de8b5cdc9ab73df7b37dfab46378ccc6d78c23b2af20c9b31` (16,009 bytes).
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/assess_smoke_v2.py`: `09b91ffdc89dac1689c9be421e47c1a4f49115e783799c693c509a0d63215f8c` (36,046 bytes).
