# Exact readiness registration

`register.py` is an operator helper. It never runs the model, simulator or queue. Obtain the Architecture Map write claim before using `prepare` or `finish`; use a new revision and run ID for each changed implementation or attempted stage. All commands use the project `venv` Python with `-X utf8 -B`.

Before a trial:

```text
register.py prepare --revision <new-revision> --run-id <new-run> --manifest <attempt.json> [--mechanism <mechanism.md>] [--expected-sha256 <inspected-map-store-hash>]
register.py verify --snapshot <Architecture Map/releases/new-revision/snapshot.json>
```

The manifest must have matching `run_id`, `stage` set to `development-only`, `development` or `diagnostic`, and a nonempty `qualification_stage` or `mode`. It should declare the actual tasks, scenario, seeds where applicable, model/client binary identities, invocation count, time/action/observation/storage limits, shutdown/interruption protocol, gates, and intended evidence. Put protected fixture solutions/seeds only in this operator manifest. `runtime_input_files` may name additional repository-relative inputs to freeze; dynamic generated inputs should otherwise be deterministic outputs of the captured code/templates and have their actual hashes retained in run evidence.

`prepare` captures host, runtime and generic templates, launch code, Session 9 WSL/native-client dependencies, Session 10 boundary/orchestrator/templates/registration, Runtime 004 Python, recorder Python, requirements and frozen provenance manifests. It excludes records, probes and credential roots. It bundles each captured source's **same bytes that were hashed**, stores the original manifest bytes, validates the proposed linked records, and appends through the map's guarded store digest. It refuses every reused ID or revision directory. The bundle is immutable even if a later append fails; preserve that preparation and choose a new revision rather than overwriting it. Large robot assets are identified by their vendor manifest; this helper does not rehash 12 GB of vendor/archive content or assert asset qualification.

The default mechanism explicitly includes bounded agent-written shell/Python within the invocation boundary and protected gateway budgets. It does not claim those capabilities passed qualification. Pass an exact mechanism document if the implemented architecture differs. `verify` compares every frozen source hash with the current tree immediately before launch; the launcher must separately bind its runtime inputs and effective executable/configuration evidence. A clean Git commit alone is not that verification.

After a queue receipt is terminal:

```text
register.py finish --run-id <run> --result <result.json> --queue-receipt <queue.json> --execution-status completed --validity valid --outcome failure --reason "<measured basis>" --termination "<actual reason>" [--evidence <file>]
```

Execution status, validity and outcome are explicit and separate. A succeeded/exit0 queue receipt allows an assessed task failure as well as success. A failed/missing queue receipt permits only invalid infrastructure diagnostics with unknown/unassessed task outcome, or a truthful `not_run` record. This preserves unsuccessful attempts without consuming them as completed experimental evidence. Existing results require an explicit map correction record, not a rerun of `finish`. The helper rebuilds and validates the map after appending; it never rewrites historical records. No scored campaign is supported.

Run `test_register.py` for five temporary-map checks covering exact byte binding and append preservation, stale-store refusal, source drift, failed queue evidence, and task failure under successful queue execution. Tests do not touch the real map or invoke a model/simulator.
