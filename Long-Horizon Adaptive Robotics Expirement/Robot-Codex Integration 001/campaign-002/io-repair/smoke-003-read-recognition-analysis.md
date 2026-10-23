# Smoke003 retained-read recognition diagnosis

The original dev019 smoke and final admission remain **failed/invalid, task outcome unknown**. The assessment passed 59 of 61 checks. Its two failures were the fixed-startup/initial-continuity read check and `resume:all_45_model_canaries_saved`. Timing passed at 4.1413 ms maximum lag with zero of 726 full windows outside RTF tolerance. This read-only diagnosis preserves that outcome.

## Interrupted invocation: distinguish the two reads

`exec-c70f9ee5-229d-4847-9a8f-bc62d244a65d` successfully ran:

```sh
cat /workspace/Continuity.md && ls -la /workspace/notes /workspace/programs /workspace/live
```

The complete trusted stdout and retained app aggregate both contain 896 bytes, SHA-256 `fd12953808b25b2111c03f462ee62b765f92ab1df3d357c24f41950df6a7a816`. Completion was 1790561490.911. The executor request is capture line 263 (request 73, process 48594); output/exit/close are lines 288/290/292 with send completions 289/291/293. The app completion is line 119.

That stream includes directory output. Its success and the initially empty protected revision do **not** establish immutable bytes for this earlier cat: the frozen runtime explicitly permits writes to `.continuity/Continuity.md` (runtime.py line 371), and absence of a protected commit does not exclude direct local mutation.

A later successful command, `exec-5d839001-7e2c-4e81-bdd2-ccab1236ed72`, contains the literal read:

```python
print('Continuity contents:', repr(Path('Continuity.md').read_text()))
```

Its trusted stdout line 42 is exactly `Continuity contents: ''`. The complete 19,648-byte trusted output equals the retained app aggregate, SHA-256 `c4dce29bc49425162ffa0ba103ee39dac64550032a77ec6415664c3de2ba470d`. Completion was 1790561532.086 (app line 181; executor request line 363, process 41807; outputs 366/368/370/372, exit 374, close 376). This is stronger direct zero-content evidence **at that later read**, not proof about the earlier cat's bytes.

The first protected `continuity_committed` record is host history line/event 2410 at 1790561696.0606253, with the empty digest as its previous revision. Its successful broker response is interrupt broker line 13 at 1790561696.0633953. These are distinct timestamps; both reads precede both. The frozen reader recognizes a restricted standalone-cat form and a separate zero-byte-wc fallback, rather than either observed form.

## Resumed invocation: actual canary execution and retained bytes

`exec-6285da93-0634-4da8-8cfa-df3e63bec517` ran this four-line script:

```sh
python3 /canary.py > notes/resume-boundary-observation.json 2> notes/resume-boundary-stderr.txt
canary_status=$?
cat notes/resume-boundary-observation.json
exit "$canary_status"
```

The trusted request is resume capture line 567 (request 109, process 56673); output/exit/close are 570/572/574, each with a retained send-completion receipt. App completion is line 327. The 2,150-byte output has SHA-256 `f2c168e3f944d954085f606e52cce5a6d3bca588da503a3df749410dc0428f07`. It equals the complete retained note bytes in both before-close and after-close workspace snapshots, and equals the app aggregate. Its JSON has exactly the same 45 check keys as the invocation's initial protected canary result, all literally true; qualified is true. The separately retained stderr note is empty. These joins rely on actual protected-script dispatch, complete authenticated process output and retained bytes, not assertions in a model-authored note.

The archived `retained_reads.py` canary matcher permits a direct one-line invocation or a specific two-line stdout redirection followed by cat. Its line-count and suffix gates reject this four-line form before examining the JSON. Isolated evaluation of those archived pure grammar functions reproduces both recognition gaps; no whole assessment was rerun or relabeled.

## Prospective correction and boundaries

Bounded recognizer corrections are under development. They must preserve trusted-source joins and reject fabricated notes, truncation and ambiguous command forms. A new source anchor and all five fresh qualifiers—native, boundary, actual-model smoke and both family pilots—are planned. Instructions, policy, criteria and timing thresholds are unchanged. This artifact grants no historical pass, qualification, release or campaign admission. Send completion does not prove app acknowledgment or model attention; the retained app aggregate is a separate observed projection.

## Exact retained sources

- [Original failed smoke assessment](<../qualification/smoke-003-assessment.json>)
- [Original failed admission](<../qualification/final-qualification-005/smoke-003/disposition.json>)
- [Authenticated official queue receipt](<../qualification/smoke-003-queue.json>)
- [Original dev019 methods archive](<../../../Architecture Map/releases/RCI001-C02-dev-019/code.zip>)
- [Original dev019 source snapshot](<../../../Architecture Map/releases/RCI001-C02-dev-019/snapshot.json>)
- [Interrupt app events: lines 119 and 181](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/interrupt/client/events.jsonl>)
- [Interrupt trusted executor capture](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/interrupt/executor-2-capture.jsonl>)
- [Protected host history: line 2410](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/host/public-history.jsonl>)
- [Interrupt broker acknowledgment: line 13](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/interrupt/broker-events.jsonl>)
- [Resume app events: line 327](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/resume/client/events.jsonl>)
- [Resume trusted executor capture](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/resume/executor-2-capture.jsonl>)
- [Retained resume workspace before close](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/resume/runtime-before-close.json>)
- [Retained resume workspace after close](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/resume/runtime-after-close.json>)
- [Initial protected resumed-invocation canary result](<../../local-evidence/campaign002/qualification/RCI001-C02-smoke-003/orchestrator/resume/canary-stdout.json>)

The [small machine-readable diagnosis](<smoke-003-read-recognition-analysis.json>) records exact input hashes, byte counts, line identities, archived function ranges and the limitations above. It contains no raw trace bodies or base64.
