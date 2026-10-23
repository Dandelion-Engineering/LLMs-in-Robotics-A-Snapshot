# Original C0-010 restart diagnostic

`inspect_c0_010_restart.py` is a one-off, queue-only, read-only derivation fixed to
`B01-dev-C0-010`. Prepare now; run only after the original development job has an
official succeeded/0 receipt and the canonical finish record has been appended.
This does not classify a later snapshot, change the public cut, or decide a repair.

From the project root, the queued child command is:

```powershell
venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/inspect_c0_010_restart.py" --receipt "<official-dev003-receipt.json>" --output "D:/CodexEvidence/LLMs-in-Robotics/C0-010-original-restart-001"
```

The receipt argument is the **original development execution receipt**, not the
new diagnostic's receipt. The child verifies its own installed-queue identity
with `expected_script=__file__`. It uses `process_development.receipt_files`,
`read_map`, `verify_run`, and `check_sources`; `record_attempt.registered_storage`
supplies the immutable registered C/D location, with no user-selected alternate
run directory. A unique current terminal canonical result must bind the exact
original result, events, and motion bytes. The registered source ZIP must match
its frozen reference and every raw-manifest Python source hash. The diagnostic
reads no motion records and performs no simulator/model work.

The complete finite event chain passes `evidence_adapter.read_lines` and
`continuity.EvidenceIndex`, including payload hashes, monotonic clocks and earlier
parent links. Exact original byte offsets, physical line numbers and SHA-256 line
hashes are retained. Selected JSONL lines are copied without reserialization.
The report preserves:

- Every original `restart_begin` identity. Only a sole original cut receives a
  detail view; absence or multiplicity is explicitly reported without selecting.
- The complete original cut payload and every recorded predicate, all native
  object geometry/poses/contacts, robot/authority state and physical-class data.
- Direct-parent-linked revocation/ready events, with unlinked same-kind events
  retained separately. Missing or multiple expected links remain explicit.
- Every same-request action request/admission, physical service record and
  candidate-input feedback; dispatch/cancellation subsets are labeled explicitly.
- Five events before/after each cut, revocation, ready, matching admission and
  dispatch anchor. Also the nearest five coarse protected `world_snapshot` events
  on each side of the cut. These bounded contexts do not establish continuous state.
- Original raw and canonical results separately, recorded source hashes,
  snapshot-content/classifier/result-copy equality checks, and the existing
  read-only predicate-integrity adapter result. An integrity disagreement is
  visible and never triggers reclassification or favorable record substitution.

Input and operator-source hashes and the canonical map identity are checked
before/after. Current operator source identities are distinguished from the
immutable episode source ZIP. Output must be a fresh directory outside source,
map, originals and candidate state. Partial outputs/errors are retained. Fixed
resource caps are 512 MiB of events, 250,000 events and 2,000 retained events;
exceeding a cap stops rather than truncating. The successful diagnostic receipt
is still required before interpreting its report. Completion is not a physical,
timing, qualification or causal-attribution pass.

Preparation status: source authored only. No helper execution, test, raw evidence
scan, queue operation, Runtime edit or Map edit was performed during active
development physics.
