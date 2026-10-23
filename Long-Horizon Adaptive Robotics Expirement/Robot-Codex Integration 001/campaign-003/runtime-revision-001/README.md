# Campaign 003: frozen time choice and separate capacity decision

The prospective time choice is **60 minutes per model invocation, 70 simulation minutes per C encounter, and 75 wall minutes per C encounter**. Its [immutable declaration](runtime-envelope.json) is hash-bound by the [freeze receipt](freeze-receipt.json). This is a frozen selection, **not an installed or qualified executable revision**. No new model invocation, simulation, live attempt, pilot or scored slot has been declared or run.

The next boundary is the separate non-time decision Randy explicitly required in his October 3, 2026 18:52 PDT instruction. The retained evidence indicates that the unchanged action and evidence budgets would compete with the generous time allowance. They have not been changed. The earlier live-001 and pilot-001 failures, their original/corrected dispositions, and all original evidence remain intact.

## Why these times

The original invocations both reached 600 seconds while still attempting the task. The pilot achieved the evaluator's placement condition at 274.806 simulation seconds, had its handback rejected at 373.624 seconds, and continued recentering to the deadline. The original condition remains a joint task failure; that intermediate placement is not reinterpreted as success. Each host continued for about 610 simulation seconds, and each coordinator took about 617 wall seconds. Original strict physics timing passed, with zero bad full-second windows and maximum lag below 22 ms.

A sixfold model allowance is a deliberately generous one-time choice rather than an incremental extension. The additional ten simulation minutes allow for preflight and the existing RTF tolerance; fifteen wall minutes allow for setup, completion, handback and retirement. For example, 3,600 wall seconds at the allowed RTF upper boundary of 1.05 consume 3,780 simulation seconds, leaving 420 simulation seconds inside the chosen C limit. This is engineering headroom, not an estimate that Astra will succeed within an hour.

| Limit | Original contract | Frozen prospective choice |
|---|---:|---:|
| Model invocation | 600 s | 3,600 s |
| C encounter simulation | 900 s | 4,200 s |
| C encounter wall | 1,100 s | 4,500 s |

The executable currently enforces the 600-second model and 900-second encounter simulation limits; its old 1,100-second per-encounter wall declaration was not separately enforced. The revised implementation must bind all three from the frozen declaration, measure encounter wall time from accepted invocation start, and derive total block limits without resetting per-encounter clocks. The declared totals are 4,500/4,800 simulation/wall seconds for single-encounter live qualification and 13,200/14,100 seconds for a three-encounter block. The latter adds 600 seconds for initialization and ordinary A/B work to three complete encounter envelopes. Existing per-job waits remain unchanged.

The times will not be extended again because a new session fails. GPT-6 Astra/max, ChatGPT authentication, sole bootstrap, task geometry, completion thresholds, memory instructions, vision, physical interface and all validity criteria remain unchanged.

## Measured capacity evidence

[measurement.json](measurement.json) binds every retained input file by size and SHA-256. The read-only [measurement worker](measure.py) authenticated both SQLite containers against their original compressed and uncompressed identities, checked database integrity, reconstructed exact recorder quota charges from the frozen accounting rules, and verified that all input bytes and membership remained unchanged after reading. Job `20261004T020348222170Z-b2c231fe` [succeeded with integer exit 0](measurement-official-status.json). Its success is a reader result, not live qualification. The first submit command was rejected before job creation because the project label contained spaces; the corrected existing repository label was `LLMs-in-Robotics`. No worker or model attempt was retried.

| Quantity | live-001 | pilot-001 |
|---|---:|---:|
| Original model deadline | 600 s | 600 s |
| Host simulation interval | 610.728 s | 610.322 s |
| Physical action budget used | 17 / 20 | 15 / 20 |
| Explicit observations | 3 / 50 | 3 / 50 |
| Native core charged bytes | 9,153,076 | 8,949,354 |
| Core quota, entire block | 50,000,000 B | 50,000,000 B |
| Public host history | 27,290,940 B | 27,518,289 B |
| Uncompressed journal and content | 30,122,040 B | 29,287,066 B |

At those observed rates, 20 actions correspond to about **11.8–13.3 model minutes**, while an hour corresponds to **90–102 actions**. This is a behavioral projection: neither old attempt exhausted its action budget, and the evidence does not prove that a fresh successful solution needs more than 20 actions. It does show that keeping 20 would preserve a tight exploration limit despite six times the reasoning time.

The native core quota projects to exhaustion after **55.6–56.8 simulation minutes**. An hour projects to 52.8–54.0 MB, already above its 50 MB ceiling; three full model hours project to 158–162 MB. This core quota covers continuous motion and image-availability records and is independent of action count. Gzip size is not its quota metric.

The three full 70-minute encounter envelopes project to **563–568 MB of public history alone**, exceeding the **512 MiB (536,870,912 B) aggregate host ceiling** before native data, timing samples, explicit images or metadata. Adding the 600-second A/B/setup allowance projects roughly 1.2 GiB of total host files if the observed aggregate host rates persist; a conservative full timing reservation adds about 0.2 GiB. The block's journal projects to about 0.61 GiB including that allowance, below its unchanged 1 GiB cap.

All projections are planning estimates from two ten-minute runs, not observed future failures, qualified maxima, or evidence that a new model would use its full allowance. Faster completion can stay under the old caps. Shrinking the time choice to fit those caps would undermine the requested generous envelope, and deliberately launching with the known mismatch would risk another avoidable apparatus stop.

## Concrete proposal requiring a separate decision

| Non-time budget | Current, still enforced | Proposed only |
|---|---:|---:|
| Physical actions per activation | 20 | 120 |
| Native recorder core per block | 50,000,000 B | 256 MiB |
| Aggregate host evidence per block | 512 MiB | 2 GiB |

The action proposal scales the existing allowance sixfold with the model time. The proposed core cap gives headroom over the approximately 198 MB full-block projection including ordinary-work allowance and stays below the recorder's unchanged 512,000,000-byte container ceiling when combined with image allowances. The proposed host cap provides headroom over the approximately 1.4 GiB conservative host/timing projection. These are finite caps, not an authorization to consume them or discard old evidence.

Explicit observations/images stay at 50 per activation: the observed rate projects to 18 observations per model hour. Workspace 256 MiB, individual files 16 MiB, journal 1 GiB, sparse-camera policy, manual horizon, speed/rate limits, retirement headroom, free-space reserve, memory limits and every scientific/validity criterion stay unchanged. The sparse archive already exhausted much of its initial image allowance early in the old runs; that preexisting policy is distinct from the still-working explicit model image interface and is not expanded by this proposal.

At measurement C: had 118.41 GiB free, above the unchanged 100 GiB reserve plus 2 GiB retirement headroom. This is not scored-allocation admission. No deletion, drive migration or weakening of reserve is proposed. Future blocks and any expanded audit/replay copies must pass capacity admission before creation, with scored allocation chosen only after the actual full pilot costs are known.

Long-duration memory and timing are still unqualified. The old measured private-commit peaks were about 1.24 GB against about 1.60 GB soft and 2 GiB hard ceilings; their startup values were close to the 1 GiB baseline ceiling. Do not convert the ten-minute passes into a long-duration pass or raise memory ceilings. If supported prospective bounded-retention engineering is necessary, preserve exact evidence and all current guards, then qualify it before live admission.

## Resume after the decision

If Randy approves the proposed non-time revision, implement it only in the new Campaign 003 lineage, consume this frozen time declaration, and retain the original inherited source files exactly. Qualify coordinated timeout handling, complete evidence, unchanged safety/authority/memory/timing bounds, and capacity before the required fresh live invocation. A native core or host quota refusal remains a distinct infrastructure/evidence outcome, not a valid model task failure.

Live qualification must pass its declared gates before the full three-encounter unscored pilot. The pilot must pass before prospective allocation/freeze/scoring; no automatic substitute slots. Continue the already-authorized final investigation and replay after a legitimate campaign terminal state. This capacity decision is the only newly requested scientific revision; the time selection remains fixed.

If only evidence quotas are approved, retain the 20-action constraint explicitly and interpret later results within it. If no non-time changes are approved, preserve this frozen selection and the measured conflict; do not silently install new quotas, reduce the generous times to conceal the conflict, or invoke Astra while this dependency is unresolved.
