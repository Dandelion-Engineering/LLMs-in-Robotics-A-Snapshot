# Transport probe phase-accounting correction

This prospective correction changes only the independent verifier and its tests. The [Transport010 diagnosis](transport-probe-010-failure-analysis.json), [unassessed failure disposition](transport-probe-010/records/queue-failure.json), and [completed failure registration](transport-probe-010/records/finish-receipt.json) remain unchanged. Official job `20260928T181807629948Z-06ccd2f4` failed with integer exit 1; its outcome remains unknown and invalid, not admitted qualification.

The frozen verifier compared channel1's `ready_to_finish.sent` snapshot, recorded before closing intent, with its final transport meter. The already declared [owner-drain workload](CHANNEL_OWNER_DRAIN_V1.md) sends one additional GOAWAY after the protected pending-read acknowledgment. The diagnostic evidence therefore contains three distinct identities:

| Phase | Bytes | SHA-256 |
| --- | ---: | --- |
| Before closing: HTTP/2 preface, SETTINGS, SETTINGS ACK and fixed PING | 59 | `0a6966c986e17f2a5e2490805da8b2b11b65701ed1e40aeee628624e25d94636` |
| After acknowledgment: GOAWAY(NO_ERROR, last_stream_id=0) | 17 | `57704c1e774aa7a5d0cef2b8add417e403944119c48c8acccedf7cb1b7502226` |
| Final concatenated upload | 76 | `2c667a8bb941463a76132bf05e360adb3c44aa12f9c4d8a9482abd77807a61b9` |

The [corrected verifier](../assessment/transport_integrity_v3.py) independently checks every ordered DATA slice against those fixed bytes, rather than inferring payload identity from counts. It binds the unchanged original frontier, pending upload read, DRAIN_BEGIN/ACK, complete retained ledger prefix, unique child shutdown-control observation, genuine EOF, drained uploads and final seal within the original 25-second budget. Exact authenticated endpoints, client-read/upload/namespace-upload equality, namespace-download/parent-download/client-written equality, full framing and retirement remain mandatory. Channels2/3 and the boundary probe retain their direct saved-to-final meter equality. Wrong baseline or tail hashes, changed endpoints, missing or duplicate controls, altered prefixes, premature DATA, lost bytes and invalid cleanup still reject the proof; negative diagnostics cannot become ordinary passes.

`grant_monotonic_s` precedes the source-bound pipe write and is the causal lower bound for child and relay observations. `control_sent_monotonic_s` is sampled **after** that blocking write returns, so the child or relay may already have processed the control before this sample. The verifier requires grant ≤ control_sent < deadline, and grant before the observed shutdown activity; it does not invent an ordering from the later completion sample to earlier child activity. A dedicated race regression preserves this distinction.

The [initial full-verifier regression](probe-phase-verifier-development-check-001.json) reproduced the old 59-versus-76 rejection. The [final focused receipt](probe-phase-verifier-development-check-004.json) records 93 passing tests, including 18 mutation subcases, fragmented shutdown bytes and the completion-clock race. The [full checks015 receipt](checks-015/repair-test-receipt.json) binds 306 harness and 336 assessment tests, all passing, to the new freeze.

The [v18 source comparison](v18-source-change-inventory-001.json) finds exactly two changed files among all 816 dev050 sources: the verifier and its test. Runtime, probe, method and other snapshot sources remain byte-identical. The [dev051 snapshot](../../../Architecture%20Map/releases/RCI001-C02-dev-051/snapshot.json) has SHA-256 `e023a2757738f1ab73badf47df573a6086fdf101aea3895b4cd1a4e5ac11d4d3`; it binds verifier `75051d99906b5febd3f9155176aefef59554a79499f751da2515a195289d5b04` and test `5d309c4378980cf59e1cd1902192fdfdd6a6a1aad5e3c366d361c959e96e729e`.

These development checks establish the prospective correction, not a replacement verdict for Transport010. Fresh identities and the complete independently admitted qualification sequence remain required. This note does not inspect or assert completion of current diagnostic or qualification jobs.
