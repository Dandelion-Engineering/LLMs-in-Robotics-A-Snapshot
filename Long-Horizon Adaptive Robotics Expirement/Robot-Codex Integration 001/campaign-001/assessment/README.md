# Campaign assessment

`assess.py` reads completed, authenticated attempts. It imports only retained-file
helpers from Session 10; it does not modify or run the frozen framework. New
campaign manifests are hash-bound separately from the original 010d pilot manifest.
Freeze this assessment and the protocol before scoring.

The CLI requires `--manifest`, `--manifest-sha256`, `--evidence`, `--host-evidence`,
`--queue-receipt`, `--job-id`, `--snapshot`, `--workspace`, and a new `--output`. The
workspace comes from the sealed launch plan, not from the receipt being checked.
An optional
`--timing-max-lag-s` implements a protocol-declared ceiling. Exit 0 means an
assessment artifact was produced, including when it reports invalid evidence or
task failure. Read `validity`, `task_outcome`, `task_evidence_valid` and `failed_checks`.
`scorable` is always false: this preparation tooling does not yet consume an
independently verified full timing, storage/accounting and scientific-release
admission certificate. Scalar lag alone cannot establish those wider gates.
`scientific_admission` explicitly remains unqualified and not admissible even
when all per-episode evidence checks pass.
Failed/nonzero queue attempts are rejected before outcome files are opened and
must be retained separately as infrastructure dispositions by the campaign runner.
Receipt validation requires an actual integer zero, exact project interpreter,
working directory, frozen direct launcher command, mode and planned paths. Model
and protected-host timestamps must fall inside the authenticated queue window.
Arbitrary outer-worker successful receipts are not accepted.

Valid completed model turns, observed model wall deadlines, and model output-budget
exhaustion are separate model dispositions. A bounded model failure can remain a
valid task failure when the protected host, retirement and full evidence gates
pass. Authentication, transport, provider, evidence and source-integrity failures
are infrastructure-invalid; no task outcome is inferred from their absence.

The lifecycle has two predeclared branches: explicit protected retirement plus
late HTTP403, or successful terminal host closure with protected handback/epoch
transfer, a task-success stop, clean host exit, and all namespace retirements. The
second branch lists the missing receipts as missing. It never marks them passed.
It accommodates the already observed 010d shutdown gap without changing 010d.

Protected task outcome, handback, conventional follow-through, command dispatch,
public effect support, model outcome, timing, continuity and program records remain
separate. Exact hashes cover framework sources/archive, declared inputs, queue
receipt, assessor/helpers, every retained orchestrator file and protected host
file (including native recorder bulk); credential endpoints are excluded.

From the repository root run the project interpreter on
`Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/assessment/test_assess.py`
with `-X utf8 -B`.
The tests exercise synthetic records only and never launch a model or simulator.
