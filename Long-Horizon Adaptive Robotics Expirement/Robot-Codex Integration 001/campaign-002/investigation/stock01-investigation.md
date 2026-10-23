# Stock01: restore a usable workpiece, then hand back

This is the first scheduled misplaced-stock episode, selected for inspection
before outcomes. It is a **valid task success**, with all 41 declared checks
passed. [Original admitted assessment](../execution/RCI001-C02-stock-01/assessment.json)
and [terminal disposition](../execution/RCI001-C02-stock-01/disposition.json)
bind the result; the assessment SHA is
`8bede455892bc7733e502c367474953b45b41cb903ec038aacca42a71e029e6c`.

The public camera detections placed raw part A1 in quarantine and the compatible
A insert in the fixture. After bounded visibility checks, the conventional
controller requested assistance because it lacked a supported eligible action.
Robot-Codex inspected the public history, requested one protected transport of
A1 into the fixture, checked the resulting placement and requested handback.

| Recorded event | Simulation seconds | Public-history physical line |
|---|---:|---:|
| Conventional assistance request | 1.904 | 28 |
| Robot invocation gains epoch 3 | 1.944 | 31 |
| Robot requests A1 transport to fixture | 137.474 | 1372 |
| Handback accepted; conventional control resumes | 222.316 | 2234 |
| Conventional recipe A cycle request | 222.404 | 2236 |
| Conventional inspection request | 242.974 | 2452 |
| Conventional transport to tray1 | 245.210 | 2481 |
| Episode stops for protected task success | 256.094 | 2608 |

These are records from the [original public history](../../local-evidence/campaign002/RCI001-C02-stock-01/host/public-history.jsonl),
rounded to milliseconds for reading. Simulation time and receipt wall time
remain separate in the explorer. The transport request was completed and its
effect independently matched a public observation. Three protected continuity
commits were valid; the final local note matched the final protected commit.
The independent timing replay found a maximum lag of 3.147 ms and zero bad
windows among 255 full one-second windows. Transport verification passed.

The model's final public message said processing, inspection and delivery were
unverified. That accurately limits its own report after handback. The later
protected evaluator establishes the complete task outcome. This episode
therefore illustrates a recovery action enabling conventional follow-through,
not model control of every production step.

[Authenticated bounded inspection](session19-results-001/first-episodes-001/inspection.json)
retains source identities and public tool/message receipts. Its extraction job
`20260930T215958862501Z-180a3227` succeeded with integer exit 0 after independently
authenticating the original run job `20260930T213946660895Z-49a816ac`.
No internal reasoning is reconstructed. One known fixture success does not
establish generalization or the causal benefit of an apparatus repair.
