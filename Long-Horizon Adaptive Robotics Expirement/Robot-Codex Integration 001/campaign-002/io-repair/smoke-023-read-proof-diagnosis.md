# Smoke023 resumed fixed-file read diagnosis

This is infrastructure diagnosis of the unchanged failed qualification, not a new assessment or a qualification claim. Official job `20260929T014234165833Z-cba1e8b0` was freshly authenticated as `succeeded` with integer exit `0` before output reads. The retained assessment SHA-256 is `aa0b4ceb104e4cefd6d8bac1d0fca424ae555401e7d8a3dcd2846ab0b745c733`. Its resumed Tasks.md and Robot.md startup evidence remains false.

[Machine-readable diagnosis](smoke-023-read-proof-diagnosis.json) · [fresh official receipt](smoke-023-read-proof-diagnosis-records-001/official-replay-status.json) · [diagnostic command receipt](smoke-023-read-proof-diagnosis-records-001/diagnostic-001-receipt.json) · [bounded diagnostic script](smoke-023-read-proof-diagnosis-records-001/diagnose.py)

The resumed native event journal contains one completed outer call, `call_UIJ8m3sRj49LsaZl7vt308Ya`, at physical lines 118–125. Its exact code makes two literal `tools.exec_command` calls through `Promise.allSettled`, then prints them with:

```javascript
for (let i=0;i<results.length;i++) text({i,...results[i]});
```

The first command is `cat Tasks.md Robot.md Tools.md` in `/workspace`, with `max_output_tokens:15000`. Native command `exec-c1826839-35f5-46e8-a223-bfc7571da1fb` starts/completes at lines 120/122. The second literal live/Continuity command starts/completes at 123/124. Both have unique signatures, complete authenticated executor streams and matching thread/turn identities inside the outer interval; there is no additional process in that interval. These are finite interval/command joins, not an asserted native parent-call ID.

The executor captured all **20,920 bytes** of the first command, SHA-256 `ee124639b1f782ab3c12139b5f8616641105cb9df5529a4f38fdb45a52e72234`. The displayed app aggregate contains only the final **4,837 bytes**, SHA-256 `2ab73a92fe9d4586154e2b8eeae2e41f40a90b5907fd41af3be36135c30dcea3`. The original `app_projection_equals_executor:false` therefore remains correct.

The separate raw prepared result has **40,153 bytes**, SHA-256 `f2cb7cc5d941e61af1d36b80f2fffac18aff2e051ffed2ea8c49eefcf6c90925`. It has the declared 10,000-token outer formatting budget: a 20,000-byte head, one 27-byte omission marker, and a 20,000-byte suffix. Only the observed head is decoded. It contains **19,698 bytes** of the first command's exact stdout prefix:

| File | Complete executor byte interval | Actual prepared-body encoded interval | Complete before omission |
|---|---:|---:|---|
| Tasks.md | `[0, 2155)` | `[265, 2433)` | Yes |
| Robot.md | `[2155, 7891)` | `[2433, 8221)` | Yes |
| Tools.md | `[7891, 20920)` | — | No |

The complete Tasks/Robot slices match the original fixed-file hashes and the authenticated stdout exactly. No omitted bytes, suffix bytes, fabricated JSON closure or reconstructed output were credited. Tools.md remains incomplete in this prefix; the original assessment already proves its separate later complete read.

The source-supported rejection is narrow: frozen `prepared_result_segments.py:105` accepts explicit index properties `index:` or `part:`. It rejects the actual ES object shorthand `i` with **`Unknown index property`**. The older single-command raw recognizer separately rejects the truncated outer result. The unchanged decoder can parse this observed body using an explicitly analyst-specified recipe with index key `i`; that diagnostic byte observation is not an accepted grammar proof or a changed assessment.

A prospective correction could recognize only shorthand whose property identifier is exactly the declared loop counter, preserving the finite counted-loop grammar, distinct bindings, exact child bijection, native/capture interval checks, initial-file hashes, UTF-8/JSON boundaries, truncation budgets, and every other gate. Relevant negatives are a different shorthand variable, renamed counter mismatch, duplicate/colliding property, extra property/spread, altered output index, foreign/overlapping child, and any file extending past the retained head. No runtime, prompt, file contents, output limits, source gate or historical verdict should change for this correction.

All imported assessment sources were checked against dev078's snapshot and archive before diagnostic use. Exact source/input identities, executor sequences and raw event identities are in the JSON. The diagnosis makes no claim about model attention, canary validity, transport qualification or task outcome.
