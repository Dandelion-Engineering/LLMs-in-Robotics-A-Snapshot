# Parking1 corridor byte projection from construction 003

This is a small-file size calculation, not a classifier benchmark, accepted bundle or qualification. Root's [prospective choices](root-provisional-choices-001.json) select **A1+B10**, 50 mm center bins and 10 mm materialized padding. B2 remains unsupported. Final rules must bind fresh construction 004 after the Runtime route change; these construction-003 sizes do not replace its measurements.

The completed [compact-cover receipt](../../Evidence/queue-receipts/20260923T094229717164Z-170731a4.json) records succeeded/exit 0, ending 2026-09-23 09:42:50.881419 UTC. Only its small JSON outputs and source/schema files were read here; no raw streams, native models, tests, queue commands, helper edits or classifier calls occurred.

| Existing parking1 50 mm cover | Boxes | Canonical full cover-record array | Canonical plain box array | Canonical plain box array with ±10 mm |
| --- | ---: | ---: | ---: | ---: |
| A1, selected prospectively | 587 | 451,925 bytes | 80,273 bytes | 80,189 bytes |
| B10, selected prospectively | 463 | 356,277 bytes | 63,272 bytes | 63,247 bytes |
| B2, unselected reference only | 610 | 470,462 bytes | 83,365 bytes | 83,328 bytes |
| **A1+B10 selected sum** | **1,050** | **808,202 bytes** | **143,545 bytes** | **143,436 bytes** |

The projection takes each `covers[*].box`, subtracts `0.01` from each minimum and adds `0.01` to each maximum in memory, without rounding or changing the retained file. Byte counts use `json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')`. The sum retains the two separate cell arrays. Fewer serialized digits after arithmetic explain the small byte decrease; no precision reduction was applied.

With the existing four full-bundle identity digests in a usual qualified grip-plus-one-route classification, these two padded arrays alone account for **573,744 canonical input bytes** across those four calls. This excludes every other bundle field, compatibility work, selected-calibration copying/hashing, event encoding, allocation and disk costs. It is neither the final bundle size nor a wall-time estimate. Full cover records would additionally repeat per-box provenance already retained in their referenced originals. The prospective builder owns the thin inline representation; no source or representation optimization was applied here.

Further optimization, including digest caching, is deferred until the actual accepted-bundle [offline CPU benchmark](QUALIFIED-RESTART-CPU-BENCHMARK.md) measures the whole path. Actual-host development timing remains separate.

| Retained input | Exact SHA-256 |
| --- | --- |
| [A1 50 mm cover](D:/CodexEvidence/LLMs-in-Robotics/recovery-final-compact-parking1-001/A1-bin-50mm.json) | `ae102b87737e3596645688b9c7894a41ae1ea7c075ec23c5eadd224bd5fc0313` |
| [B10 50 mm cover](D:/CodexEvidence/LLMs-in-Robotics/recovery-final-compact-parking1-001/B10-bin-50mm.json) | `a515f87afe835b0f1b8579bfdb58938e7b3f5b5d04b513d9855fac4cfa8ef9d5` |
| [B2 50 mm cover](D:/CodexEvidence/LLMs-in-Robotics/recovery-final-compact-parking1-001/B2-bin-50mm.json) | `cbff11da036998fd464f97fb79d89e4fb90f1ad8530def6313381c5ec3a5d64f` |
| Official compact-cover receipt linked above | `36f5e9d23cdc0a4e2e1a00b49de2283a8da6fe5f067eeccac93758d610a3ec0e` |
| Root choices at this calculation | `0dc4687822db5229e6d9fead06c39516facd06c6452f047d90e2e25b5ba406a5` |
