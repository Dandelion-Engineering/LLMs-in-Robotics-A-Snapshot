# Session 4 local payload retention proposal

Proposed only; `.gitignore` has not been edited. Snapshot: 2026-09-26T18:40:52.023173+00:00.

Keep 10,351 generated/local payload files (1,072,718,049 bytes) in place and omit them from normal Git objects. None is currently tracked. Metadata-only inventory; no raw payload read or rehash was performed.

| Class | Files | Bytes |
|---|---:|---:|
| calibration_npz_depth_arrays | 3,973 | 527,874,830 |
| calibration_png_images | 3,970 | 264,087,444 |
| calibration_streams | 69 | 185,277,005 |
| cross_language_fixture_payloads | 22 | 1,485,993 |
| first_declared_trace_payloads | 2,317 | 93,992,777 |

## Exact proposed append

```gitignore
# Retain local calibration images/streams and generated validation payloads.
# Compact manifests, descriptors, reports, receipts and source bundles remain versioned.
# These rules remove no local evidence and do not cover canonical Map JSONL.
/Long-Horizon Adaptive Robotics Expirement/Evidence/calibration/**/*.png
/Long-Horizon Adaptive Robotics Expirement/Evidence/calibration/**/*.npz
/Long-Horizon Adaptive Robotics Expirement/Evidence/calibration/**/*.jsonl
/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-004/first-declared-trace/data/*
/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-00[1-4]/cross-language-fixture/data/*
!/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-001/cross-language-fixture/data/ea6e7fd41672014c6319703cb5ca88843e32b93001bbb257efc3c696f70b3a05.json
!/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-002/cross-language-fixture/data/ea6e7fd41672014c6319703cb5ca88843e32b93001bbb257efc3c696f70b3a05.json
!/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-003/cross-language-fixture/data/ea6e7fd41672014c6319703cb5ca88843e32b93001bbb257efc3c696f70b3a05.json
!/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-004/cross-language-fixture/data/8a5734d54ee2a176fe35a3f3447fe7fd5ccbbc8a92c517faaa82207d68ad72e2.json
!/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-004/cross-language-fixture/data/955573ab7f58421dd8c60644046004edb9bdeb5854633a4a20f639acfcff689a.json
!/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-004/first-declared-trace/data/1090d74e230ad4dcbc928a9c7871b3403cf20e706027a6960e222cbb34caa0a3.json
!/Long-Horizon Adaptive Robotics Expirement/Evidence/derived/investigation007-package-validation-004/first-declared-trace/data/f91a5732d4ef3ed40684ec70f314ec2cdafcff3794d5fad8021291aebe58665b.json
```

The negations retain the actual first-trace and synthetic-fixture package manifests and top-level metadata references. Root descriptors, reports, manifests, calibration source archives and XML/configuration JSON remain eligible for Git. Calibration `.jsonl` rules never apply to canonical Architecture Map JSONL.

## Preservation and reproduction

The JSON audit binds small production copies and reproducibility controls, lists compact calibration anchors and records a path/size inventory fingerprint for each class. Those inventory fingerprints are not payload-content hashes. Every original local file remains in place. No staging, deletion, moving or configuration edit occurred.

Calibration replay is not a promise of bit-identical measurements or authorization to rerun trials. Rebuilding the investigation package requires retained local original evidence plus the exact bound005 reader and007 packager. A source-only Git clone does not contain all evidence. Synthetic fixtures can be regenerated with the bound validator. Existing terminal/control records and selected analysis/derivative outputs stay in scope.

## Exact production metadata copies

- `Long-Horizon Adaptive Robotics Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation007-003-build-result.json` — 8,267 bytes; SHA-256 `5420133a2fa891e5f63061b47aff20ebcfd40509a4a119ff5608904465e3acbc`. Exact source bytes verified.
- `Long-Horizon Adaptive Robotics Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation007-003-package-manifest.json` — 27,784 bytes; SHA-256 `8999e9170a0b8fa1154b06dfd704f84a2d0ad233ef0ae7837e754459ade93ad7`. Exact source bytes verified.

Browser verification and complete session closeout are separate gates; this retention proposal establishes neither.
