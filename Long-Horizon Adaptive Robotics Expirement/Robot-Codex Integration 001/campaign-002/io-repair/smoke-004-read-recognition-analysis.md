# Smoke004 retained read-recognition diagnosis

Smoke004/dev023 remains **failed, invalid/unknown: 58 of 61 checks passed**. The [official queue receipt](../qualification/smoke-004-queue.json) was freshly matched to direct queue status: `20260928T025941819890Z-1ec8ce3e`, succeeded with integer exit status 0, ending 2026-09-28T03:13:01.585736Z. The [original assessment](../qualification/smoke-004-assessment.json) and [failed admission disposition](../qualification/final-qualification-006/smoke-004/disposition.json) are unchanged. The exact admission error is `Actual-model interruption/resume smoke qualification missing/failed`.

The three failed checks are `both_models_read_fixed_startup_and_initial_continuity_bytes`, `model_requested_live_source_reads_match_protected_episode_invocation_observations`, and `resume:all_45_model_canaries_saved`. Owner timing passed: maximum lag 5.7404 ms, maximum sample gap 6.7335 ms, and zero bad windows out of 796. Resource and both transport checks passed. Pilots003 were never launched. Passing timing does not erase failed evidence checks.

## Combined activation, state, and initial note read

Resume tool `exec-cd7ad8c0-5363-40c2-a345-4a2b125a9e21` completed at [client event line 108](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/client/events.jsonl) with the literal script:

```sh
cat /workspace/live/activation.json && cat /workspace/live/state.json && cat /workspace/Continuity.md
```

The complete trusted stdout and app aggregate are identical: **21,800 bytes**, SHA256 `51c64f00178a9aa6ffeaf492e29c8969b3cc7c5193c816f68da6a998729e5cd5`. The [executor capture](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/executor-2-capture.jsonl) binds request 66 / process 23980 at line 223, start response 226, stdout lines 228, 232, 234, 236, and 242, exit 238, and closure 244. Contiguous process sequence and unique send-completion receipts were checked, including output retained after the exit event and before closure. [Original request line 66](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/executor-2-requests.jsonl) matches the exact protected dispatch.

The byte intervals below are zero-based with exclusive ends; the two JSON boundaries were decoded from actual bytes:

| Read | Byte interval | SHA256 |
|---|---:|---|
| activation.json | 0–410 | `bf281f36c0a59408b29e091633462a329713a3738652092ebf28e68b8b481e81` |
| state.json | 410–18190 | `e430bdbfdc1e39b7da6ebf22f3166ec23ed9946876500b94c74215f3649f1ff0` |
| initial Continuity.md | 18190–21800 | `342e8b9fd07cba2ec6160519fea4984f0c7898e331802178715d766cb0e2e917` |

The final 3,610 bytes equal the [protected initial note](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/host/continuity-history/342e8b9fd07cba2ec6160519fea4984f0c7898e331802178715d766cb0e2e917.md), its [resume input hash](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/runtime-input-hashes.json), and [protected continuity commit 2744](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/host/public-history.jsonl). The decoded state has observation sequence 3088, epoch 5, invocation `resume-8764c9eb37d7`, and episode `episode-9e67fb24982b446f`. Its capture time and order match protected observation 3124; its invocation matches protected start event 2838. These are the declared semantic identity fields, not a claim that the entire packet equals the protected observation payload.

## Why the original readers rejected this form

All method statements refer to the immutable [dev023 source archive](../../../Architecture%20Map/releases/RCI001-C02-dev-023/code.zip), with exact entries/hashes in the [diagnosis JSON](smoke-004-read-recognition-analysis.json). The pure frozen read-only parsing helpers reproduced these limits; the full assessor was not rerun.

- `assessment/retained_reads.py:35–44` rejects `&&` in `exact_cat_paths`. `assessment/assess_smoke_v2.py:197–232` requires that whole-command matcher before admitting authenticated live reads.
- `assess_smoke_v2.py:52–67` rejects the entire concatenated stream when the two leading JSON objects are followed by Markdown.
- `readiness-session-10/assessment/assess_bootstrap.py:61–87` initializes expected bytes from final retained contents and conditionally supplies the fixed smoke-template note. The [final workspace snapshot](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/runtime-before-close.json) has only `.continuity/Continuity.md`, now 4,320 bytes with SHA256 `cb0c1e0930d7102abfc472992aa9f94129f84bc944134adc5cbfc9c0dc7f0c90`; it has no logical `Continuity.md` key. The fixed template differs from the resumed initial note. Thus the helper lacks the exact initial bytes for substring matching. It does not directly choose the mutated backing file under the logical key.

The backing note is model-writable. Protected initial bytes, the observed combined-read suffix, and final local bytes must stay distinct; final contents are not an immutable initial-input copy.

## Redirected canary and subsequent note read

Tool `exec-c6006f26-9a9f-4af6-9b77-93609ab59a14` completed at client line 308. Its sole script was:

```sh
python3 /canary.py > notes/resume-boundary-observation.json
```

Protected capture request 109 / process 62854 begins at line 523, acknowledges at 524, exits successfully at 526, and closes at 528. **Captured stdout is zero bytes**; the app aggregate is null. The redirected canary output was not independently captured.

The next completed command, `exec-08c66bad-751a-4d31-b974-c6c4c01e44b8` at client line 314, runs `cat notes/resume-boundary-observation.json` followed by the retained read-only Python history inspection. Capture request 111 / process 6524 starts at line 533, acknowledges at 534, emits stdout at 536, 538 and 540, exits at 542 and closes at 544. Complete captured stdout equals the app aggregate: **10,640 bytes**, SHA256 `95b29984206ad323bb37dc86ecb2af223e312d3a49cda903d03fc44168eb9bee`.

Its first 2,150 bytes exactly equal the saved note in both [before](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/runtime-before-close.json) and [after](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/runtime-after-close.json) snapshots: SHA256 `f2c168e3f944d954085f606e52cce5a6d3bca588da503a3df749410dc0428f07`. This JSON has `qualified: true` and exactly the [original canary's](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/orchestrator/resume/canary-stdout.json) 45 keys, all literal true. Those are verified content facts, not independent validation of the assertions.

Frozen `retained_reads.py:180–255` recognizes a redirected command only with the matching cat in the same two-line script, or its declared four-line stdout/stderr status-preserving form. It rejects this sole redirection and separate later tool call. Accepting the later saved JSON alone would not establish that it is the earlier protected canary output: the note is model-writable, and this diagnosis does not prove complete inter-command mutation or producer-file provenance.

## Evidence and prospective scope

The [structured diagnosis](smoke-004-read-recognition-analysis.json) records exact commands, line IDs, byte hashes, frozen source identities, and 21 input bindings. Both executor capture hash chains and process delivery sequences were verified; all bound source/evidence files were rehashed unchanged. Websocket send completion is not an app acknowledgment or evidence of model attention; app aggregates were compared separately. The [owner timing summary](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/host/timing-v2.json) and [separate supervisory timing](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-004/host/supervisory-diagnostics/timing-v2.json) remain distinct.

A source-bound semantic proof is under prospective design. Any correction needs its own settled source binding and fresh qualification; this document grants no historical pass and changes no original assessment, model instruction, policy, criterion, or timing threshold. No report build or model run was performed for this diagnosis.
