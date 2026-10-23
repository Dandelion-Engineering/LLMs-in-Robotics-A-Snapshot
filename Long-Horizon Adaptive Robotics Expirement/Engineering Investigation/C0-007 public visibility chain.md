# C0-007 public visibility and assistance chain

Reviewed on 2026-09-23 after root confirmed successful extraction receipt `20260923T072807363789Z-7ea5a5f8` (end 07:28:39.108853 UTC). This review reads only the completed [compact incident report](../Evidence/derived/C0-007-B6-incident-001/incident.json). It does not reread raw events, inspect protected truth to guide candidate actions, or change results. Canonical result remains `B01-dev-C0-007-result`, partial 9/10, as reported by root.

The public chain supports persistent missing B6 visibility followed by repeated identical assistance rounds. **It does not establish repeated use of one camera frame as the cause of this run's first help.** The [separate source counterexample](Baseline%20visibility%20counterexample.md) remains a valid synthetic interface defect.

The extraction streamed the finalized original `Evidence/raw/B01-dev-C0-007/events.jsonl` once: 1,231,870,668 bytes, 20,253 lines, before/after SHA256 `daa645dc61e8de12c34dbadbe36e9945bb04dc46eebe9495ed555429cbf6871a`. Execution receipt SHA256 is `7f14e293496d13f98566bf2563ceed25af40b1dc3bc804bd48ebfb5de7ac97d4`. The raw candidate source hash matches the retained counterexample/proposal base: `fc101b3a79a4f647735f396d8938cb6156e180566d114eb5e46f8c8659e89c47`.

| Public evidence | Retained facts |
|---|---|
| Last candidate-retained B6 sighting | Capture 465, sim 46.974 s; raw zone and raw mark. This older `last_seen` is not current visibility. |
| Last B6 detection anywhere in the public observation stream | Event/line 804, sim 50.778 s; capture 503 at sim 50.700 s, age 0.078 s, 12 pixels, raw zone, **unknown mark**. Position `(0.503185, -0.238696, 0.017444)` m. |
| Last successful resolution before first help | Event 4911 at sim 312.486 s; the source resets its idle counter on successful public reconciliation. |
| Four observations before first help | Event 4911/index 2, then 4922, 4933, 4944; capture sequences 3119, 3121, 3123, 3125. These are distinct captures. |
| First help | Event 4954/index 2, sim 313.174 s; trigger capture 3126 at 313.000 s, packet age 0.150 s. B6 absent. Fresh raw A5/A7/A9 are visible under order version 1; they do not supply the missing B-family requirement. |
| First assistance answer delivered | Answer 00001 was created at event 5421 and actually received at candidate event 5424/index 1, sim 328.204 s. The source clears halt and resets idle count on a new answer ID. |
| Next help | Event 5468/index 2, sim 328.890 s; capture 3283. Four intervening observe captures are 3277, 3278, 3280, 3282. B6 remains absent. |
| Later work and recurrence | First seven retained incidents still show A5/A7/A9 raw under order 1. Retained help at event 11797, sim 633.500 s, follows productive late-A work under order 2; its fresh raw-stock list is empty. Last eight retained incidents also have order 2 and empty fresh raw stock. |
| Last retained help | Event 19849/index 2, sim 887.336 s; capture 8868, B6 absent. |

There are **24 total help incidents, 16 retained incident windows, and 8 omitted middle windows** under the extractor's declared first-eight/last-eight limit. Event-type totals are 24 `help_requested` and 23 `scripted_human_answer`. Every retained help has reason `required progress lacks publicly supported eligible action`, every corresponding packet explicitly lacks B6, and no following fresh B6 detection exists in the extracted stream. The final candidate checkpoint is halted with no pending action, no last error and no action failure counts; B6's retained older sighting has no cycle or inspection proof. Those records explain the public policy's refusal to invent a supported B6 action.

Root separately inspected the referenced image and protected final state and reported that B6 is tipped approximately 90 degrees with its marker hidden. That is separate physical evidence; public detection absence alone would not prove a tip or its cause. The neighboring A3 pickup/contact geometry is being investigated separately. This document makes no claim about the exact tipping time or contact mechanism.

The [visibility change and retained proposal](Visibility%20reacquisition%20proposal.md) address observation bookkeeping and repeated help. Root subsequently applied this change and ran the recorded Runtime tests. It cannot recover a permanently hidden marker, infer B6 from its last location, or establish that C0-007 would succeed. All original outcomes and assistance costs remain unchanged.
