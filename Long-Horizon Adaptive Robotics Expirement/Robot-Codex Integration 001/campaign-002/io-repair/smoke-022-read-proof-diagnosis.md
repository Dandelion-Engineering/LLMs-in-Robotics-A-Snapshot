# Smoke022 startup-read diagnosis

Smoke022 remains failed qualification: the original assessment passed 61 of 62 checks. Only the fixed startup-document read criterion failed. Both initial Continuity reads passed; interruption started with an empty file, and resume started with the protected 3,080-byte file. The official queue succeeded with integer exit 0. This is a read-only diagnosis, not a new assessment or an upgrade of that verdict.

The [hash-bound diagnosis](smoke-022-read-proof-diagnosis.json) retains the exact commands, source identities, byte ranges, capture and delivery sequences, and original assessment identity. [Fresh official authentication](smoke-022-read-proof-diagnosis-queue.json) preceded this retained analysis. No model, native process, qualification assessor, or simulator was launched.

## What was actually retained

Both stages ran the literal command `cat Tasks.md Robot.md Tools.md`. Complete executor stdout was 20,767 bytes in interruption and 20,920 bytes in resume, exactly the ordered concatenation of each stage's initially hashed files. The displayed command aggregate was only the same last 4,837 bytes of Tools.md in both stages. That display projection really is partial and must remain marked partial.

The interruption prepared raw result is different: call `call_BAlcukoQqgOEelJtiZ4DQ4Lx`, client lines 123–130, contains a fulfilled indexed result whose decoded output exactly equals all 20,767 executor bytes. Its script uses two literal `tools.exec_command` calls inside `Promise.allSettled`, then emits each indexed result. All Tasks.md, Robot.md and Tools.md bytes are retained there.

The original reader first rejects an unrelated later unmatched call, `call_RChk9KZmsIxd8maR5oqBordu`, at line 418. That call begins after the selected pair ended at line 130 and was interrupted before producing an output. There are 14 raw call IDs in this stage. The reader's whole-log pair requirement causes `Duplicate/missing/reordered raw call/output` before it reaches the selected wrapper. Independently, its finite single-call grammar and exactly-one-process interval would also reject this two-call wrapper.

Resume has 19 complete raw pairs; it has no equivalent unmatched-pair failure. Its selected pair is `call_0Du7MpV5ANTLzJRbZTkVjSnf`, lines 121–128. Here the outer prepared output is genuinely truncated, and the original error is `Raw event redacted/truncated/failed`.

## Exact prefix boundaries

These ranges are zero-based UTF-8 byte offsets within the selected raw result's text content item 1. They describe serialized JSON string content, so their lengths differ from original file lengths.

| Stage | File | Original bytes | Complete serialized range | Entire file before cut |
|---|---|---:|---|---|
| Interrupt | Tasks.md | 2,002 | [143, 2156) | Yes |
| Interrupt | Robot.md | 5,736 | [2156, 7944) | Yes |
| Interrupt | Tools.md | 13,029 | [7944, 21084) | Yes |
| Resume | Tasks.md | 2,155 | [221, 2389) | Yes |
| Resume | Robot.md | 5,736 | [2389, 8177) | Yes |
| Resume | Tools.md | 13,029 | Only prefix [8177, 20079) | No |

Resume's text item consists of a 79-byte warning, a 20,000-byte retained head, the 27-byte marker `…1068 tokens truncated…`, and a 20,000-byte tail. Tools.md requires 13,140 serialized bytes; only its first 11,902 appear before the cut. The 1,238 serialized bytes missing from that head must not be invented or supplied from the unrelated tail. The later standalone `cat Tools.md`, tool `exec-9a959e01-5968-408d-9903-d013e831b6cd` at line 151, supplies all 13,029 bytes in both executor and displayed output. The original assessment already credits that separate read.

Both fixed-document literal proofs already passed their process/app chronology checks. Their displayed completion timestamps are 1790641842965 ms and 1790642101583 ms; the raw result timestamps are 1790641843021 ms and 1790642101642 ms. This failure is not another clock-order contradiction.

## Source support and the strongest counterexample

The new [native source packet](native-output-source-003/findings.md), pinned to `rust-v0.157.1`, establishes that all-text content items are joined with LF for the outer budget, whose default is 10,000 approximate tokens or 40,000 bytes. The implementation preserves exact UTF-8 head and tail slices and inserts the marker between them. The separate script-completion header is added afterward. The observed 79/20,000/27/20,000 layout agrees with that policy.

The retained resume output is itself a counterexample to parsing truncated JSON as original JSON: after removing the warning, it still parses as a valid `part:0` object with a 38,362-byte output. The original first command output had only 20,920 bytes. The spliced JSON combines the first record's head and the second record's tail; successful JSON parsing does not repair this lost boundary.

The protocol documents `text(nonstring)` as JSON serialization, but the host implementation of that helper was not exposed in the inspected Rust adapters. Pinned source is also not installed-binary equivalence attestation. Exact observed byte equality corroborates these particular representations; it does not justify an arbitrary JavaScript interpreter, generic substring matcher, model-attention claim, or exact-next-request claim.

## Narrow prospective correction

A finite recognizer could support bounded literal `Promise.allSettled` arrays and their indexed emission forms, while joining each unique command to its actual native item, successful captured process, options, thread/turn, and fulfilled result. Pair identity and overlap checks must remain strict; a later unrelated call can be outside the selected terminal interval without excusing duplicates or an earlier unresolved call.

A separate per-file rule could recognize complete, independently hashed files inside a source-defined unchanged prefix. It must parse forward from the known wrapper/string boundary, use the declared budget and UTF-8 cut, and stop before the marker. It must not parse spliced JSON as complete, search arbitrary substrings, merge head and tail, credit partial Tools.md, or reconstruct missing output. The original startup criterion already permits complete file bytes inside combined output; the proposed extension concerns authenticated representation and attribution, not relaxation of completeness.

Required regressions include the actual valid-spliced-JSON counterexample, partial-file cutoff, fabricated or mutated indexed results, duplicate and ambiguous commands, earlier unresolved/overlapping calls, marker text inside genuine files, nested truncation, mixed media, and UTF-8/JSON escape boundaries. No such production extension was implemented here. All original assessment bytes and verdicts remain unchanged.
