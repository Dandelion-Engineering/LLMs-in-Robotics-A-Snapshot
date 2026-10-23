# Sealed Campaign 001 admission consumer

`admitted.py` is additive. The prepared `assess.py` remains unchanged and always
reports `scorable=false`. This consumer verifies the operator's prospectively
sealed campaign bindings, canonical immutable map registration, actual external
storage receipts and each episode's timing before allowing scoring. It does not
authorize a different experiment and does not launch models, simulation or jobs.

The scientific claim remains repeatability on the two known development fixtures.
The certificate is an operator seal independent of the robot's runtime. It is not
a second scientist's validation or a cryptographic identity signature. Its SHA256
must come from the pre-outcome seal/registration, never from an untrusted
certificate's self-declared `admitted` field.

## Certificate interface

`verify_certificate(certificate_path, certificate_sha256)` authenticates the
external digest and returns the validated certificate or raises `ValueError`.
Registration calls this before appending records. Required document fields:

```text
schema: rci-campaign-scientific-admission-1
campaign_id: RCI001-Campaign001
created_at: timezone-qualified UTC timestamp
framework_revision: RCI001-wsl-010d
release_revision: RCI001-C01-frozen-001
source_count: 624
conditions: {maximum_attempts: 24, no_replacements: true,
             no_injected_restart: true, no_tuning: true}
timing: {maximum_lag_s_exclusive: 0.1, rtf_min: 0.95, rtf_max: 1.05,
         outside_fraction_exclusive: 0.01}
storage: {free_reserve_bytes: 100000000000,
          planning_peak_bytes: 37962254720,
          planning_allowance_is_hard_limit: false}
artifacts: named {path: absolute file path, sha256: digest} records
attempts: ordered 24 entries from execution-plan.json
```

Required artifact names are `protocol`, `original_plan`, `schedule`, `snapshot`,
`archive`, `assessor`, `admitted_assessor`, `timing_source`, `approval`,
`storage_monitor`, `storage_policy`, `storage_tests`, `preflight_capacity`,
`retained_timing`, `retained_timing_queue`, and `asset_refresh`. All additional
artifact bindings are hash-verified too. Each attempt has `run_id`, `ordinal`,
`manifest: {path,sha256}`, `workspace`, `evidence`, `host_evidence`, and
`storage_receipt`; paths are absolute and attempts have distinct output locations.
The original fixed schedule's family, order, seed, manifest and workspace fields
are verified, including the exact bootstrap, Astra Max and one invocation.

The historical 010d snapshot and archive hashes are fixed constants. All 624
current source hashes and archive entries must agree. The unchanged frozen
TimingMonitor code is verified as one of those sources. The retained 010d pilot's
237 windows are recomputed from its hash-authenticated journal; its original
per-tick lag is checked separately. The older 010c failure remains a failure.
Actual native/WSL capacity, matching storage-code qualification and current asset
hashes/package versions are verified instead of accepting a bare pass field.

The separate registration document uses schema `rci-campaign-registration-1`
and binds the certificate digest, `release_revision`, `source_snapshot_sha256`,
`map_root`, `release_snapshot`, `release_archive`, `release_record`, and 24
`attempts` with `run_id`, `manifest_sha256` and `run_record`. File bindings use
`{path,sha256}`. The exact staged revision/run payloads must also appear uniquely
in the canonical map JSONL. Registration files alone are insufficient. All
records and admission must predate the attempt's authenticated queue start.

## Assessing a completed attempt

Run the project Python with `-X utf8 -B`, this module's absolute path, and:

```text
--certificate <sealed certificate.json>
--certificate-sha256 <digest from pre-outcome seal>
--registration <registered release/registration.json>
--run-id <fixed scheduled run ID>
--queue-receipt <attempt storage/queue-receipt.json>
--job-id <official shared queue ID>
--output <new assessment.json>
```

Official `succeeded` and integer `exit_status=0` are required before any attempt
output is opened. Queue direct executable, launcher, arguments and every path
must match the sealed attempt. Model/host timestamps must fall in that queue
window, as enforced by the unchanged base assessor. The guard's final queue
receipt is the canonical receipt to pass here.

For each episode, the unchanged TimingMonitor reconstructs one-second windows
from protected journal events, retaining maximum sample spacing and interpolation
limits. Both its strict lag `<0.1` and outside-RTF fraction `<0.01` checks must
pass, as must the original per-tick lag `<0.1`. Reconstructed windows are never
represented as missing original per-tick windows. Sparse sampling remains an
explicit measurement limit, not an invented sub-window guarantee.

Storage authentication checks source/policy/baseline, identity, paths, original
queue receipt, sample hashes, coverage before/after the queue window, minimum
native/WSL free space, protected retirement margin, sampled peak, monitor stop
status and sample gaps. The approved planning allowance remains advisory. Sampled
peaks do not prove the exact between-sample peak.

The output retains the base assessor's observed task outcome, model disposition,
handback, continuity and lifecycle evidence. Natural successful host closure keeps
its missing retirement/late-403 receipts absent. `scorable=true` requires both
valid episode evidence and admitted timing/storage. Valid model timeout or output
budget failures can be scored task failures; infrastructure-invalid attempts keep
`task_outcome=unknown`. Failure to authenticate the queue, certificate or map raises
an error; the runner must retain that slot as invalid with no replacement.

Run `test_assess.py` and `test_admitted.py` using the project Python. Tests never
launch a model or simulator; retained timing reconstruction is read-only.
