# Stock024 retirement inventory diagnosis

The original Stock024 assessment remains **invalid / task unknown**: 36 of 38 checks passed; `all_namespace_retirements_observed` and `qualified_lifecycle_end_observed` failed. The queue succeeded with integer exit 0. This packet is an additive infrastructure diagnosis, not a new qualification or task assessment.

The frozen pilot adapter delegates to legacy `inspect_stage`, whose `*-retirement.json` inventory finds only the two executor receipts. It omits the actual `codehost-owner-retirement-v3.json`. The current smoke adapter already explicitly includes that exact filename. All three actual receipts satisfy every unchanged `check_retirement` field predicate. The v3 bridge binds the omitted receipt exactly (SHA256 `e3fccebaa0ad81f3362939113d2a62c5bcd796d089a01e1fdc228abd713fad36`, 2,693 bytes), reports qualified true/no failures, and the original independent transport proof passed.

The inherited false namespace flag then blocks the existing successful-terminal-host-closure branch. Its other guard fields are already retained: one invocation start (event 32), clean host exit 0, protected episode stop event 2162 after ownership transfer event 1784, and the original assessor's corresponding outcome/transfer fields. These are inspected only to explain the lifecycle branch; no new task result is asserted.

Protected episode stop occurred at wall 1790655470.5351577. Client finishing was recorded at 1790655484.6389372 (client line 537); namespace finished at 1790655484.6860933, namespace output closed at 1790655485.0023773, retirement started at 1790655485.0060728, and qualified bridge closure at 1790655485.257911 (ledger 234–238). The launcher makes its late operator retirement/status requests after Runtime.model returns. Both encountered connection refusal. Those missing explicit-retirement and late HTTP403 receipts remain missing; their exact request times were not retained. The existing terminal-host branch explicitly preserves this limitation and needs no changed criterion.

Each of the three final retirement observations reports the identified outer process absent and the identified namespace empty, with evidence available and Windows wrapper exit 0. No retained evidence here indicates a live leaked namespace. This was not a present-time global process/namespace census, and no cleanup action was performed.

The supported prospective repair is to include the exact v3 receipt filename in the pilot adapter, retain the unchanged retirement predicate and source/integrity gates, and exercise missing/malformed/unqualified receipts through the actual pilot entry point. A new declared source and qualification lineage are required. Do not broaden the glob, manufacture HTTP403, or promote this historical result.

## Source and evidence

- [Full hash-bound diagnosis](diagnosis.json), [fresh official status](official-status.json), [authentication receipt](authentication.json).
- [Pilot adapter](../../assessment/assess.py):25–35,71–103; [legacy inventory](../../../readiness-session-10/assessment/assess_smoke.py):134,152; [unchanged retirement predicate](../../../readiness-session-10/assessment/assess_bootstrap.py):90–96.
- [Existing smoke adapter](../../assessment/assess_smoke_v2.py):148–152; [read proof upgrade](../../assessment/retained_reads.py):273 onward (does not replace retirements); [launcher](../../harness/physical.py):68–88.
- The JSON binds original assessment, admission disposition, all three retirement receipts, bridge/ledger, client lifecycle files, host chronology, and dev086 snapshot/archive. Every listed source matches the frozen snapshot, archived bytes, and current bytes at collection. Original input hashes were checked again after writing this packet.
