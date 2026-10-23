# Native009 admission observation

Created 2026-09-28T05:56:45.780048+00:00. Diagnostic follow-up to completed no-model reference suite `RCI001-C02-native-009` / `RCI001-C02-dev-035`.

Official queue `20260928T053438977071Z-2c966502` was freshly authenticated as `succeeded` with integer exit status `0` before empirical consumption. It ended `2026-09-28T05:42:45.967127Z`. The retained assessment reports **6/6 cases and 66/66 checks passed**; no assessment was rerun.

**Home-1 transport completion precedes inspection admission.** After handback event 560 at 54.410 s, the B2 transport to inspection (`3ef2a6e0-f4ef-4fb7-9755-8b048000fea1`) reached supervisor terminal event 897 at 86.914 s (native completion payload: 86.912 s). Inspection `ee8585b5-637e-4373-85d5-c0533fdf0ba2` was requested once at event 898 / 86.926 s, accepted at event 900 / 86.934 s, and completed with inspection status `pass` at event 922 / 88.936 s. The transport terminal precedes the request by 12 simulated ms and admission by 20 simulated ms. Corresponding journal wall gaps are 11.020 ms and 20.026 ms.

The inspection references observation 850: capture 86.780 s, packet 86.818 s, journal event 896 at 86.840 s. The complete eight-command post-handback sequence, exact IDs, journal line numbers, native feedback and wall timestamps are in the JSON. The independent evaluator subsequently recorded B2 accepted in tray2, with first success at 100.910 s. Final controller state has no pending command and is not halted; its retained `last_error` still says `bounded attempt limit reached`, which is not erased or treated as a new fault.

| Case | Supervisor command rejections | Native admission rejections | Rejections after handback | resource_busy records/events |
|---|---:|---:|---:|---:|
| stock-1 | 0 | 0 | 0 | 0 / 0 |
| home-1 | 0 | 3 | 0 | 0 / 0 |
| stock-2 | 0 | 0 | 0 | 0 / 0 |
| home-2 | 0 | 3 | 0 | 0 / 0 |
| stock-3 | 0 | 0 | 0 | 0 / 0 |
| home-3 | 0 | 3 | 0 | 0 / 0 |

Each home case has three setup rejections with reason `destination occupied`, all before recovery and handback. Stock cases have none. Rejected request-ID sets match between registry and admission/rejection journal events. There is no `resource_busy` in any of the six full histories or registries.

The [retained native008 diagnosis](native-008-admission-analysis.md) describes the opposite relevant order in home-1: inspect request event 898 at 86.954 s, `resource_busy` rejection event 899 at 86.958 s, then the prior transport terminal event 900 at 86.964 s. The fixture and noise seeds (173 / 24002) and declared caps match. Native008 remains a failed qualification.

**Interpretation limit:** this is observed corrected-suite behavior. The journal does not expose guard deferrals or the exact thread/drain interleaving, so this run does not establish that the old race was exercised or measure a causal performance gain. The separate deterministic regression demonstrates the targeted ordering condition. These no-model reference cases do not qualify Robot-Codex recovery performance or the full campaign.

Provenance: [JSON observation](native-009-admission-observation.json), SHA-256 `80a4c734c0802e176b16979043de22986d5a85b70787e53e3ac7db6a3725a25b`. Its 34 input bindings retain exact hashes and byte counts for queue, manifest, snapshot/archive, assessment, suite result, six per-case manifests/histories/registries/results, home-1 controller state, method and prior diagnosis. The frozen archive binds `run_host.py` and its deterministic test; the decision guard is at lines 358–366 and its main-loop call at line 446.

No frozen runtime, method, certificate, history or earlier evidence was edited; no model, simulation, reassessment or running qualification-output inspection was performed for this follow-up.
