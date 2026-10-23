# Prospective epoch-revocation evidence and prepared-result index shorthand

Declared 2026-09-29 after Smoke023/dev078 failed and before implementing either change. The original assessment SHA256 is `aa0b4ceb104e4cefd6d8bac1d0fca424ae555401e7d8a3dcd2846ab0b745c733`: 59 of 62 checks passed. It remains failed/invalid, with unknown task outcome. V25 stopped before pilots022 and scoring. This declaration does not resolve the separate resumed canary-readback rejection; its proof design remains under investigation.

## Protected mirror authority

The authenticated source and retained chronology in `smoke-023-transport-diagnosis.json` identify a source-defined race: the gateway can authenticate a queued GET under the old invocation and then reject it with HTTP409 `stale_authentication` when the physics host executes it after authority rotation. The mirror currently recognizes typed403 revocations only. Smoke023's mirror-error receipt was emitted 10.0054ms after protected retirement, but did not retain the failing status, body or request start. The mechanism is supported; the exact historical response is unknown. Do not substitute the mechanism for missing historical evidence.

Prospectively retain bounded mirror request and reply context: method/path, fresh request identity, pinned invocation and genuine integer authority epoch, request/response times, genuine integer HTTP status, typed response body or its safely redacted exact retained identity, and response origin. Never retain a token or credential. Preserve failed request phase and available context on every failure, without borrowing a previous request's reply.

Latch the existing local authority fence for exactly the protected GET/status denial with genuine integer status409, `ok:false`, and exact error code `stale_authentication`, bound to this invocation's request and reply. Use a distinct reason. Independent assessment must authenticate that record and prove the invocation/epoch transition from protected history within the request interval and before reply/latch. Missing, altered, ambiguous or mismatched context fails. A denial establishes loss of authority only; it is not successful continuity, action, task recovery, or host outcome. Do not change host/gateway behavior, action authority, physics or evaluator.

Keep existing accepted-handback and typed403 semantics, existing local-denial responses, and upstream-failure handling. An existing `mirror-error.json` still fails. Do not forgive a generic409, invalid_action, unsupported_resumption,400/429/504, malformed body, wrong invocation/epoch, missing retirement, early denial, mismatched timestamp or unbound reply. No mirror publication or new broker forwarding follows an established revocation.

Test the actual queued-GET/epoch-rotation path through the existing gateway fixture, known403 and200 behavior, capture of request/reply/error context, no post-revocation publication/forwarding, and all the negative provenance cases above. Source-pin suppliers may be mechanically updated only after the runtime diff is reviewed; original protected sources and historical archives remain immutable.

## Prepared-result shorthand

The resumed startup wrapper in Smoke023 uses `for (let i=0;i<results.length;i++) text({i,...results[i]});`. The existing finite parser rejects the shorthand index property. Standard object shorthand emits a property named by the counter identifier, with the counter's value. It has the same ordered-index semantics as the already supported literal `index:i` and `part:i` templates.

Extend only the existing two indexed emission templates to accept one shorthand identifier immediately before the sole result spread, and only when that identifier is exactly the bound counter/callback-index identifier. The emitted key is that identifier's literal spelling. All identifier binding, child counts, pure literal cats, exact native/runtime source checks, complete process capture, unique parent/child pairing, metadata, collision, prefix, native truncation and whole-file requirements in PREPARED_STARTUP_SEGMENTS_V1 remain unchanged. No arbitrary property expression, extra member, evaluation, alias or wrapper transformation is introduced.

Require the exact shorthand key and genuine ordered integer input index in actual complete/pretruncation-prefix records. Reject wrong variable, mismatched loop index, duplicate/colliding native field, computed key, extra member, reordered/missing/boolean index or altered spread. Test both finite emission templates, consistent renamed variables, complete and prefix paths, and the negative cases. Never credit partial Tools bytes or reconstruct the truncated suffix.

## Adoption boundary

Development uses separately named artifacts; original Smoke023 assessment, map result and history row are unchanged. Preserve every development failure. These are prospective infrastructure/evidence changes, not model/prompt/policy tuning or relaxed timing/isolation/retirement criteria. No new qualification launches until all Smoke023 blockers have a supported repair, updated immutable inventories, meaningful focused and full checks, fresh predeclared IDs and a new complete qualification lineage. Do not combine partial V25 admissions with a new revision, and do not retry any existing attempt.
