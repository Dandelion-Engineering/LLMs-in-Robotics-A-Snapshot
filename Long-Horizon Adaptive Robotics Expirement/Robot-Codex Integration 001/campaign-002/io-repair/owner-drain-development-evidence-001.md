# Owner-drain development evidence

This is an additive development record, not qualification or task evidence. Smoke014/dev049 remains a failed official run with no empirical assessment. Its historical tail bytes and exact generic `channel_ValueError` cause remain unknown. These tests use actual parser/relay/bridge code with in-memory transports and fake owner/retirement fixtures; they do not authenticate a native deployment. The focused suite also includes the previously authorized tiny base-Python PID check, without a socket or namespace.

The [prospective method](CHANNEL_OWNER_DRAIN_V1.md) separates durable close intent and its original HTTP/2 frontier from final sealing. BEGIN/ACK precedes shutdown bytes; every admitted upload must reach genuine EOF and drain before FINISH. Existing downloads may finish afterward within the same original-marker-plus-25-second limit. Cancellation is not EOF. No historical verdict changes.

## Reproduction and paired evidence

- [Old dev049 reproduction](owner-drain-dev049-reproduction/receipt.json) retains the exact previously executed script/result and hash-verified archived bridge, mux and owner sources. The actual old `upload()` path raised `client_data_after_owner_finish`, emitted only FINISH and counted none of the synthetic 13-byte CANCEL tail. This demonstrates a scheduling path, not the identity of Smoke014's unretained bytes.
- [Paired positive](owner-drain-paired-positive-001/codehost-owner-bridge-v3.json) and [pending-read proof](owner-drain-paired-positive-001/pending-read-proof.json) exercise the actual bridge/Linux relay and protected synchronization helper. The fixed 17-byte GOAWAY is a declared synthetic teardown control. All observed byte meters match; original frontier, ACK, genuine EOF, seal and closure are retained. Its fake-owner `qualified: true` is a development fixture result, not a campaign qualification.
- [Negative 002](owner-drain-paired-negative-002/codehost-owner-bridge-v3.json) retains a tied EOF/marker clock. The independent helper rejected that chronology in [compatibility 001](owner-drain-verifier-producer-compatibility-001.json). [Negative 003](owner-drain-paired-negative-003/codehost-owner-bridge-v3.json) uses the actual strict clock barrier: EOF `475351.109` precedes marker `475351.125`. Its exact 45-byte incomplete upload remains unqualified. [Compatibility 002](owner-drain-verifier-producer-compatibility-002.json) binds the positive and strictly ordered negative producer metadata; its scope excludes OS ownership/retirement authentication.
- [Negative 006](owner-drain-paired-negative-006/codehost-owner-bridge-v3.json) and [negative 007](owner-drain-paired-negative-007/codehost-owner-bridge-v3.json) retain deterministic closed-input `BrokenPipeError` and `ConnectionResetError` variants with wrapper exit 1. The original `channel_ValueError` remains; later codes are `namespace_finished_unqualified`, the typed `frame_write_*` failure, `drain_invalid`, `namespace_wrapper_nonzero`, and `namespace_receipt_ValueError`. `owner_input_closed` with `after_finish_drain: false, failed_cleanup: true` records an attempted local close, not delivered FINISH or peer EOF. Fake retirement remains explicitly bounded diagnostic cleanup. [Compatibility 003](owner-drain-verifier-producer-compatibility-003.json) independently accepts the retained positive, strict negative and both closed-pipe phase/framing metadata shapes; it reports which controls were actually written and does not infer namespace input EOF. Earlier paired negatives 001/004/005 remain untouched as intermediate fixtures.

## Retained failures and final development checks

[Parser development 001](owner-drain-parser-development-001.json) retains four preimplementation missing-API/control regressions. [Bridge development 003](owner-drain-bridge-development-003.json) retains the expanded suite's test-fixture error: an AsyncMock returned a nested coroutine, causing failed result serialization. [Probe barrier development 001](owner-drain-probe-barrier-development-001.json) retains rejection of prescribed failed namespace completion arriving before the strict next-clock barrier. Its prospective correction permits only that exact failed terminal; unrelated failures and successful-terminal substitution remain rejected.

[Bridge/probe development 005](owner-drain-bridge-development-005.json) records **81 tests passing in 7.710 seconds**, exit 0. [Linux/parser development 003](owner-drain-linux-development-003.json) records **50 tests passing in 0.970 seconds**, exit 0. Coverage includes pending reads, fragmented CANCEL, new stream open-and-close rejection, partial downloads at seal, missing ACK, expiry of the original deadline, exact incomplete EOF, terminal ordering and failed pipe cleanup. These results do not replace the full retained checks or fresh source-bound native, transport, host and model qualification.

The bridge's only change after development receipt 005 was its cancellation comment. Reversing that exact comment recovers tested SHA `64a84323ceb88bd2cc51f288a5db2884f69b18e40f12e028ca9d61d3ed45da94`; this was mechanically checked while writing this note. Other current identities below match receipt 005.

## Current source identities

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| [codehost_bridge_v3.py](../harness/codehost_bridge_v3.py) | 43362 | `5fb47c6cb083b510e5d7f7b965612c7426c132ea262f12ae44044a4448b4353b` |
| [test_codehost_bridge_v3.py](../harness/test_codehost_bridge_v3.py) | 33364 | `da9dd4f550045343cd6284a4cc3e14348987ef14bc258d0530071c4dc35767d9` |
| [codehost_transport_probe_v3.py](../harness/codehost_transport_probe_v3.py) | 59544 | `24eca3b0ea9897199fa8b978337dfcca31ffe74e95ccb631090e8ba57eb32591` |
| [test_codehost_transport_probe_v3.py](../harness/test_codehost_transport_probe_v3.py) | 60638 | `d952d25d7f4ab3d3d59b4badbe63f4fda1d98ae77c22a31186d0f424ea027f7a` |
| [codehost_mux_protocol.py](../harness/codehost_mux_protocol.py) | 17468 | `ff7a1387d15f4fd3e739146cb2a52024393157bb6893f720b51be5e263517071` |
| [codehost_inside_v3.py](../harness/codehost_inside_v3.py) | 30797 | `44906afa4691cf52c7aa9f2e12dea7233827f6a2b75bb0960de6d80ff09123f2` |

## Receipt identities

Hashes below bind the selected original records; linked compatibility receipts bind their full producer input files.

| Record | Bytes | SHA-256 |
| --- | ---: | --- |
| [owner-drain-dev049-reproduction/receipt.json](owner-drain-dev049-reproduction/receipt.json) | 3426 | `8e6db03ef0d6d9933cfd85327f87c2251a874159c129fce83eee3fa3c140b85d` |
| [owner-drain-bridge-development-003.json](owner-drain-bridge-development-003.json) | 8025 | `1fea788f6516952a23649b014203ff1f8504e93cebfaf6a98c5f6722183374f5` |
| [owner-drain-probe-barrier-development-001.json](owner-drain-probe-barrier-development-001.json) | 822 | `6862922876aa36aa7a6baf496329ec3ff1cdabe4f685bdf313a429097a0c55e8` |
| [owner-drain-bridge-development-005.json](owner-drain-bridge-development-005.json) | 2106 | `84c5a1e38c4bfaf6fcb062ca23340e802fbba931d3b4c0e54a61da415cc7c10d` |
| [owner-drain-linux-development-003.json](owner-drain-linux-development-003.json) | 1548 | `d2a2cfd448038860cffe15aefea4fbc9262791fe746dca9a9c0cdae1a7e99bfb` |
| [owner-drain-verifier-producer-compatibility-001.json](owner-drain-verifier-producer-compatibility-001.json) | 4324 | `19e461764e779e053807145c0efb950a8aaf482de57d75b6981c69e40239e4a2` |
| [owner-drain-verifier-producer-compatibility-002.json](owner-drain-verifier-producer-compatibility-002.json) | 3723 | `4c6d1d2dc7ecd8bd04186261da9db76008b2747f22f94f787b567df1d392e114` |
| [owner-drain-paired-negative-006/codehost-owner-bridge-v3.json](owner-drain-paired-negative-006/codehost-owner-bridge-v3.json) | 27467 | `9e48f4130e2ad80c59fa6f5f71722fb6eea4d3a9c6204883324a8a1ddf2f5131` |
| [owner-drain-paired-negative-007/codehost-owner-bridge-v3.json](owner-drain-paired-negative-007/codehost-owner-bridge-v3.json) | 27470 | `82742be8b22ed9d49e642bad800aa76911df3ffe10ebeb3be17cf491b4c687fd` |
| [owner-drain-verifier-producer-compatibility-003.json](owner-drain-verifier-producer-compatibility-003.json) | 7681 | `7c05b0216e0855a4ccde02f75f98c647e439a9de2c719bb35629020924da0850` |

Relative links resolve from this original `campaign-002/io-repair` directory. No runtime, test, method, map, history or retained artifact was changed by this note.
