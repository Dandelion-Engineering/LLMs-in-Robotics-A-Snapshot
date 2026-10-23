# Recovery construction 002

Official job `20260923T085627326649Z-366dbd1a` completed with state `succeeded` and integer exit status 0 at 2026-09-23T09:07:26.321833Z. The [receipt](../Evidence/queue-receipts/20260923T085627326649Z-366dbd1a.json) and raw evidence at `D:/CodexEvidence/LLMs-in-Robotics/recovery-construction-002` are retained.

All 28 original construction trials passed physical predicates; 24 passed host timing, compared with 14 in construction001. No selected trial was unstarted, no source changed, and all 12 original independent validation trials remain deferred. The exact [repeat declaration](Recovery%20Qualification/construction-repeat-002.json) fixes the applied hold-observation and exact-native-byte memo changes; thresholds and recording frequencies were unchanged. This is not a qualification or readiness pass.

The largest observed lag was 0.07283029999844182 s, below the unchanged 0.1 s limit. Twelve one-second windows violated the unchanged [0.95,1.05] real-time-factor range, distributed as follows:

| Original trial | Maximum lag (s) | Violating wall windows (s) | Measured real-time factors |
|---|---:|---|---|
| parking2-corner-B-1 | 0.06702260 | 11-12, 12-13 | 0.94289888, 1.05671610 |
| parking2-corner-B-5 | 0.06927320 | 11-12, 12-13 | 0.94200000, 1.06000000 |
| parking1-corner-B-1 | 0.06850890 | 6-7, 7-8, 11-12, 12-13 | 0.94987773, 1.05012227, 0.93488831, 1.06511169 |
| parking1-corner-B-5 | 0.07216220 | 6-7, 7-8, 11-12, 12-13 | 0.94600000, 1.05400000, 0.92991484, 1.07008516 |

These four trials are the two in-domain ten-part B parameter points at both destinations. Every one still has a dip and rebound in the warm recovery-admission interval around wall seconds 11-13; parking1 also has a cut-boundary dip and rebound around seconds 6-8. A cold memo initialization change alone cannot be assumed to solve the warm boundary. In-place operation timings on one original construction trial are the next diagnostic; diagnostic output will not replace the full phase or untouched validation. Physical success alone does not repair failed timing.
