# Smoke024 retained startup-read diagnosis

The original assessment remains **failed, 61/62 checks**. The only missing startup proofs are resumed `Tasks.md` and `Robot.md`. Every interrupt startup proof and both Continuity proofs passed. Official job `20260929T030751715764Z-8ed12f73` was freshly authenticated as succeeded with integer exit 0 before these reads; qualification is a separate result.

Resume client events line 123 records `call_HCyumpn5yxTtD80RZnaUZCeO`, a two-child `Promise.allSettled` call ending with `for (let i=0;i<results.length;i++)text({source:i,...results[i]});`. The first child, `exec-76195979-2b0a-4a23-9758-34055dc23f0f`, runs `cat /workspace/Tasks.md /workspace/Robot.md /workspace/Tools.md`. Its complete protected executor stdout is 20,920 bytes, SHA256 `ee124639b1f782ab3c12139b5f8616641105cb9df5529a4f38fdb45a52e72234`. The app completion at line 127 retains only its final 4,837 bytes, SHA256 `2ab73a92fe9d4586154e2b8eeae2e41f40a90b5907fd41af3be36135c30dcea3`. That aggregate alone does not contain either missing file.

The prepared native result at line 130 separately retains a source-bound truncated result: 79-byte warning, unchanged 20,000-byte head, 27-byte omission marker, and 20,000-byte suffix. The 47-byte native status header is a separate first content item. The following offsets are within the second content item's UTF-8 bytes; each interval is half-open:

| File | Complete initial bytes | Escaped interval in unchanged head | Complete here |
|---|---:|---|---|
| Tasks.md | 2,155 | [223, 2391) | yes |
| Robot.md | 5,736 | [2391, 8179) | yes |
| Tools.md | 13,029 | observed [8179, 20079), 11,900 of 13,140 escaped bytes | no |

The head exactly matches the authenticated stdout's JSON-string encoding, including both complete initial fixed files. Their raw bytes also match the trusted initial runtime hashes and retained runtime bytes. No suffix or omitted gap is used. Tools.md already passed through a later independent complete read; this diagnosis gives no partial-file credit.

The original proof records `prepared_tool_result_error = Raw event redacted/truncated/failed` and `prepared_startup_segments_error = Unknown index property`. Frozen `prepared_result_segments.py:107` permits explicit `index` or `part`, whereas this call uses explicit `source`. Its exact unmodified parser reproduces that rejection. The lower result parser already requires the recipe-exact label followed by an integer matching the ordered child index. The observed loss of ordinary app projection is real; the reason this separate prepared prefix gets no startup credit is the declared finite grammar boundary. This does not establish why the native aggregate became suffix-only.

A prospective correction can specify a bounded ordinary literal identifier label, retain the exact bound-counter value and sole original result spread, exclude collisions/prototype-related keys, and preserve every call/process/source/index/truncation/full-file gate. It requires declared source changes and a fresh qualification lineage. The historical verdict is not upgraded.

[Machine-readable analysis](analysis.json) binds the official authentication, original assessment, dev082 snapshot/archive, runtime bytes, native events, capture chain, exact commands/spans and unchanged frozen helper sources. [Successful diagnostic execution](execution-002/receipt.json) performed only byte/source checks. [First execution failure](execution-001/receipt.json) and its helper copy retain a nullable-response-params extraction bug, corrected only in this diagnostic script. No task outcome was recalculated, no model was called, and no production file was edited.
