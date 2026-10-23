# Home01: a rejected handback exposes an unfinished exchange

This is the first scheduled blocked-insert-home episode, selected for inspection
before outcomes. It is a **valid task success**, with all 41 declared checks
passed. [Original admitted assessment](../execution/RCI001-C02-home-01/assessment.json)
and [terminal disposition](../execution/RCI001-C02-home-01/disposition.json)
bind assessment SHA
`1b4a8401c07783d81c90bb72850e64933750eec02148abc22e9b3edeb1410925`.

Part A1 occupied insert A's return location, blocking the conventional setup
of insert B. Robot-Codex moved A1 to parking1 and checked the placement. Its
first handback was rejected with `unsupported_resumption`: the protected
controller still lacked a supported next action. The model then requested the
protected setup operation for family B, verified the exchange and requested
handback again. This second handback was accepted.

| Recorded event | Simulation seconds | Public-history physical line |
|---|---:|---:|
| Third conventional setup is rejected: destination occupied | 1.474 | 16 |
| Conventional assistance request | 1.684 | 19 |
| Robot requests A1 transport to parking1 | 94.768 | 944 |
| First handback rejected: unsupported resumption | 189.072 | 1894 |
| Robot requests protected setup B | 233.112 | 2336 |
| Second handback accepted; conventional control resumes | 302.358 | 3041 |
| Conventional loading of B2 begins | 302.446 | 3043 |
| Conventional processing, inspection and tray2 delivery follow | 314.454–337.082 | 3168–3412 |
| Episode stops for protected task success | 348.850 | 3548 |

The [original public history](../../local-evidence/campaign002/RCI001-C02-home-01/host/public-history.jsonl)
retains exact times and receipts. A successful HTTP exchange for the first
handback does not mean authority transferred: the protected command record
explicitly says rejected. Both robot action effects were independently
matched to public observations. Six valid protected continuity commits were
retained, and the final local note matched the last commit. Independent timing
replay found maximum lag 3.371 ms and zero bad windows among 347 full one-second
windows; transport verification passed.

The useful observation is adaptation to explicit feedback within one invocation:
clearance alone did not allow handback, so the model completed an additional
setup action. The rejected handback remains visible inside the successful
episode. It was neither erased nor treated as an infrastructure-invalid slot.
After accepted handback, conventional control performed loading, processing,
inspection and delivery. The model's final message left those remaining steps
unverified; protected independent evidence establishes the final success.

[Authenticated bounded inspection](session19-results-001/first-episodes-001/inspection.json)
retains public tool/message receipts and provenance. Extraction job
`20260930T215958862501Z-180a3227` succeeded with integer exit 0 after fresh
authentication of original run job `20260930T214446477570Z-e5c34e42`.
This is a recorded sequence, not access to private deliberation or a controlled
comparison of recovery strategies.
