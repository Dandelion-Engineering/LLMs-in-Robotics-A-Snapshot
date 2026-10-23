# Prospective initial-read composition and completion-time evidence

Declared after Smoke021/dev070 failed independent qualification and before implementation, a new freeze, or another model invocation. The original Smoke021 assessment (`ede5c5cb33f7e8a35fac137aa73068b2eb7fcb5b5f92de6f98d6029f04da6f6f`) and registered invalid/unknown result remain unchanged. Queue success is not qualification. V23 stopped before both family pilots; no scored slot exists.

This is an evidence-verifier correction. RobotAgentPrompt, model configuration, startup instructions, recovery policy, physics, evaluator, action/observation budgets, timing limits, isolation, native cleanup, byte/EOF rules and the twenty-slot plan stay fixed. READ_EVIDENCE_V2 and all earlier methods remain intact. Full fresh source-bound qualification is required after development checks.

## Retained observations and unchanged requirement

Smoke021 passed timing, transport, cleanup, two fresh native invocations, continuity commits, action/authority and boundary checks. The sole failed top-level criterion was `both_models_read_fixed_startup_and_initial_continuity_bytes`.

The interrupted invocation successfully executed a literal concatenation of two readonly live JSON mirrors followed by empty `Continuity.md`. Its complete 12,473-byte stdout equals the app-visible output: two JSON segments consume all bytes. The prior literal helper deliberately rejected empty composite continuity, while the separate empty reader supports a different exact Python recipe.

The resumed invocation successfully executed a sole initial `cat /workspace/Continuity.md` followed by a bounded literal `find` listing. Its complete 4,445-byte stdout equals the app-visible output. Its first 3,715 bytes equal the protected initial note, hash `91cd41a01ca258f281d7ebdca7be319a0f3b048f5138e9d19d3c0320cf452ab5`. The final local note is a different committed revision. The old generic reader uses the final local snapshot; the additive literal helper excludes `find`.

The existing startup requirement already permits all exact initial bytes within combined output (`readiness-session-10/assessment/assess_bootstrap.py`, `exact_input_bytes_within_combined_output`). It does not require that the entire current file contain no additional bytes. This correction adds two narrowly authenticated proof forms; it does not interpret arbitrary shell or Python or infer attention/understanding.

The separate read and chronology analyses are retained as `smoke-021-read-proof-diagnosis.{json,md}` and `smoke-021-chronology-analysis.{json,md}`. Their actual source/stream identities must be included in the new source inventory before freezing.

## Common authentication and limits

Both new forms require the unchanged complete executor hash chain, unredacted actual request argv, unique process/tool identity, successful integer-zero exit, no stderr, contiguous full output through process closure, every required transport-delivery receipt, unique unchanged app started/completed command, and equality of complete app-visible and executor output. A shortened aggregate is insufficient for these new forms. Actual prepared raw output can be retained as corroboration without adding a new parallel-call grammar or claiming service attention.

Bind the reviewed readonly executable/import/shell boundary, closed process environment, source archive, trusted initial runtime hash, protected initial continuity bytes, invocation/epoch, complete protected history and every consumed input. No commandActions inference, arbitrary evaluation, reconstructed model output or mutable final-note substitution is permitted. Keep the existing literal reader's 16-operand, 4,096-script-byte and 4 MiB output caps. Unknown forms and ambiguous evidence fail closed.

## Terminal zero-byte operand in a pure literal read

Accept only the existing pure literal `cat` grammar, with `Continuity.md` occurring exactly once as the final operand and at least one preceding approved nonempty operand. Its trusted initial hash and retained protected initial bytes must both identify the empty file. All preceding operands must be fully consumed using the existing exact static-byte or readonly JSON serialization rules; live mirrors must also match protected episode, invocation, epoch, observation and order evidence. No byte may remain.

Successful execution of this source-bound, option-free, nonmutating literal read proves that the terminal logical continuity operand contributed zero bytes. Preserve an explicit zero-length span and empty hash; do not represent it as a printed empty-string marker or a separate command. Reject missing initial bytes, nonempty initial hashes, duplicate/nonterminal continuity operands, extra bytes, unknown paths, modifications, redirection, transformations and unqualified execution. Existing independent empty-read recipes remain unchanged apart from the shared timestamp correction below.

## Initial continuity prefix followed by a finite listing

Support only one literal `cat` of `Continuity.md` or `/workspace/Continuity.md`, then `&&`, then the exact readonly listing form:

`find /workspace/notes /workspace/programs -maxdepth 3 -type f -printf '%p\n'`

Recognize actual literal argv with a finite grammar; equivalent arbitrary programs, options, other roots, redirection, expansion, appended commands or alternative find actions remain unsupported. The initial protected note must be nonempty and have a matching preceding protected commit and initial runtime hash. Require the complete initial N bytes to equal stdout bytes `[0,N)`.

There are exactly two possible initial byte prefixes of nonempty find stdout: `/workspace/notes` and `/workspace/programs`. Reject the proof if either complete prefix occurs starting before N in the expected note, or if any nonempty suffix of the expected note is a proper prefix of either root. The latter rule covers a find prefix straddling byte N.

This supplies a finite attribution argument: if find contributed any of the first N bytes, its first output would expose one of those root prefixes wholly or partially within them. Both possibilities are excluded. Thus all N required initial bytes came from the preceding cat, even with newline-containing filenames. A zero-output find cannot contribute bytes. Authentication proves the complete output actually reached the app-visible aggregate.

Explicitly label this `complete_initial_continuity_prefix_from_literal_cat`. Retain the prefix span/hash and the length/hash of the unattributed remainder. Do not claim that the whole current file equals the initial note, that the remainder came entirely from find, that a final directory snapshot existed at read time, or that no local mutation occurred. Additional cat suffix bytes are allowed by this limited complete-initial-content claim. The existing whole-output literal-segment proof remains strict and unchanged for nonempty forms.

## Millisecond emission interval and evidence-completion bound

The retained native source computes `emittedAtMs` with `SystemTime` duration `.as_millis()`, truncating to integer milliseconds. An emission value M represents the half-open interval `[M/1000,(M+1)/1000)`, not an exact instant. For the observed startup read, close capture is 1790638440.984023, delivery logging is 1790638440.9850233, and native M is 1790638440985. The old point comparison rejects by approximately 23.3 microseconds within the same millisecond bucket.

Also, the executor capture writes the delivery receipt after `await websocket.send(...)`. Native processing can race ahead of local receipt logging. A delivery-log timestamp is therefore not necessarily a causal predecessor of native emission. Native short-lived process completion can itself precede process/closed on an output deadline; do not invent a universal closed-before-completed invariant.

A shared helper will retain the original timestamps and exact native interval. Require finite timestamps, an exact nonnegative integer millisecond value, unchanged capture sequence/order, unique complete delivered closure, and request strictly before close capture. For this conservative accepted proof subset, require close capture strictly before the native interval upper bound. This sufficient condition rejects impossible-early/unsupported completions; it is not claimed to be necessary for every native completion branch.

Define a separately named `evidence_complete_upper_wall_unix_s` as the maximum of the native interval upper bound and the authenticated local delivery-log completion times required by the proof. Use that conservative bound for existing strict invocation, episode and mutation chronology checks. Never relabel it as the actual app emission time. No arbitrary epsilon, time-limit relaxation, cross-OS clock comparison or adjusted historical timestamp is allowed. Apply the same rule to literal-read, exact empty-read and canary-exit proof paths that currently repeat the invalid delivery-before-truncated-emission predicate.

## Validation and adoption

Retain development failures and before/after source bindings. Include adversarial cases for missing/changed/truncated output, wrong initial hashes, stderr/nonzero exit, duplicate identities, incomplete delivery, nonterminal/duplicate empty operands, extra zero-read bytes, unknown shell forms, forged listing contribution, full and straddling root prefixes, newline filenames, and the explicitly unattributed tail. Reject unsupported clocks, malformed milliseconds and genuinely too-early app completion; reproduce both quantization and post-send logging races without invoking a model.

Use retained Smoke021 streams only as separately labeled development verification with new helper sources. Never overwrite or supersede its official assessment, map result or qualification verdict. Bind all new helpers, tests, source analyses and this declaration in a new inventory version, run complete development checks, freeze fresh revisions/attempt IDs, then execute the entire required qualification before campaign admission.
