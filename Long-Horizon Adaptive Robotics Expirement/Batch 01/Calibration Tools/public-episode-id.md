# Matched public episode identity proposal

Status: prepared but **not applied** during the active development batch. This is a prefreeze causal-control correction. Existing development evidence, registered run identities and the 264-run evaluation matrix are unchanged.

The current supervisor passes its protected `run_id` directly to `Cell.public_packet`. The candidate retains that value and includes it in its model context. Evaluation run IDs encode `persistent` or `no-persistence`, which exposes the assigned condition through an otherwise incidental identity field. Source locations are [the supervisor](../../Runtime/experiment.py), [the candidate context](../../Runtime/candidates.py), [public run slots](../../Runtime/protocol.py), and [the verified evaluation context](../../Runtime/release_runner.py).

The [unapplied patch](public-episode-id.patch) adds `matched_public_episode_id(release_id, paired_block_id, architecture)` and a matching property on `VerifiedEvaluationContext`. Its exact formula is:

```text
"episode-" + lowercase_hex_SHA256(
  protocol.canonical([
    "candidate-episode-identity-v1", release_id, paired_block_id, architecture
  ])
)
```

`protocol.canonical` is sorted-key, compact UTF-8 JSON with nonfinite numbers forbidden. The version marker and ordered JSON fields make the encoding explicit and avoid delimiter ambiguity. The identity inputs contain neither condition nor any seed. The paired block already identifies the case and replicate. Matched persistence/control runs for one entrant therefore receive the same identity, while different entrants, cases, replicates and releases receive distinct digest values in the planned matrix.

The supervisor derives this alias only after the existing authorization function validates the exact evaluation context and protected arguments. It supplies the alias as the `run_id` field of every candidate-facing public packet, including packets recorded as observations and exact `candidate_input` deliveries. Development continues to use its existing public ID verbatim. The protected local manifest records `candidate_public_episode_id` for auditability.

Protected `Evidence.run_id`, event-envelope IDs, registered manifest IDs, result IDs, map identities and release/attempt paths retain the original identifier. Each condition still gets its own protected evidence directory and private `candidate_state` directory. The existing persistence/reset behavior remains in force. Candidate code is identical across conditions and needs no change; no release manifest fields or seed values are added to candidate packets. The digest is an opaque identifier, not a cryptographic secrecy guarantee. This correction does not claim to erase legitimate post-restart differences in memory or behavior.

Validation used a temporary copy outside Runtime: **65 synthetic tests passed in 24.826 seconds**, comprising nine focused identity tests and the existing supervisor and release-runner suites. No simulator, model inference or queue job ran. The focused checks cover all 72 planned matched controls; distinct case/replicate/entrant/release identities; exact encoding; exclusion of all seed roles, condition and protected ID from identity derivation; rejected malformed identities; actual supervisor dispatch with matched aliases; preserved protected IDs and isolated paths; unchanged development identity; and rejection of an unissued context before evidence or cell creation. `git apply --check --whitespace=nowarn` passed. Both Runtime source hashes remained unchanged after validation and the proposed new Runtime test file does not yet exist there.

Exact base/proposed hashes and test output are retained in [the validation record](public-episode-id.validation.json). Patch SHA256: `60c38bc6b4c16bacda56f6d2a9e1f39a3d20d6dd03aa914d1d07d918b491f322`.

After the active batch ends, apply against the recorded base hashes, rerun relevant checks with the combined prefreeze changes, and include the resulting source and new test in the frozen artifact index. This proposal neither creates readiness nor authorizes evaluation.
