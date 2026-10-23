# Campaign 001 additive registration

`register.py` creates the metadata-only frozen revision `RCI001-C01-frozen-001`,
parented to `RCI001-wsl-010d`, and the exact 24 outer `evaluation` attempts in
`predeclared-v1/schedule.json`. The original 010d source snapshot and archive stay
unchanged and are referenced directly. All runtime manifests are copied byte for
byte, including their required `development-only` host labels. The separate outer
protocol scores repeatability on two known fixtures; it grants no held-out or
framework-comparison claim.

This helper does not launch models, simulations, or jobs. It imports
`assessment/admitted.py:verify_certificate` to check actual scientific admission
evidence, then verifies every frozen source/archive member, schedule slot and
runtime manifest. An asserted admission boolean cannot replace this check.
The guarded append uses `Architecture Map/map.py` and the current canonical store
SHA256; old canonical bytes remain prefixes. No old development `prepare` helper
is used.

From the repository root:

```powershell
$registry = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/registration/register.py'
$map = 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
.\venv\Scripts\python.exe -X utf8 -B $map status --json
.\venv\Scripts\python.exe -X utf8 -B $registry prepare --certificate <certificate.json> --certificate-sha256 <trusted-seal> --expected-sha256 <store-sha> --output <new-preview-directory>
```

`prepare` is a dry run: it writes only its newly named immutable preview directory,
validates all proposed records against a temporary hardlink/copy view of immutable
attachments, and returns `preview.json` plus its SHA256. It never edits the map.
The preview includes the frozen admission certificate, outer protocol, schedule,
unchanged runtime manifests, exact revision/run records and registration binding.
Inspect that concrete preview, then publish it:

```powershell
.\venv\Scripts\python.exe -X utf8 -B $registry append --preview <preview.json> --preview-sha256 <preview-seal> --expected-sha256 <current-store-sha>
```

The returned binding path is
`Architecture Map/releases/RCI001-C01-frozen-001/registration.json` under the
experiment directory. Pass it to the admitted assessor and campaign runner.
It identifies the original snapshot/archive, frozen revision record, all 24
immutable run records, their hashes, admission seal and canonical map root.
The assessor verifies those records against the actual canonical JSONL store.

Publishing can be resumed using the same sealed preview after inspecting the
current store. Existing identical assets/records are recognized, differing bytes
are refused, and only missing records are appended. Each new append predicts its
own next store digest so an intervening writer cannot be silently accepted.
Original artifacts, qualified framework files and historical maps are never
rewritten.

## Terminal dispositions

After an official queue receipt reports `succeeded` with an actual integer exit
status `0`, use the separately produced **admitted** assessment:

```powershell
.\venv\Scripts\python.exe -X utf8 -B $registry finish --run-id <scheduled-id> --assessment <admitted-assessment.json> --queue-receipt <official-queue.json> --execution-status completed --reason <evidence-validity-reason> --termination <actual-terminal-reason> --expected-sha256 <current-store-sha>
```

The helper gates the official receipt before opening the assessment. It binds
run, queue, manifest, admission seal and registration; a valid result requires
`scorable:true`. It derives task success/failure from the assessment, preserving
valid task failure separately from infrastructure invalidity.

For an official failed/cancelled queue attempt, omit `--assessment`, retain the
receipt, and use the appropriate `--execution-status failed|timed_out|aborted`.
The recorded task outcome is `unknown`, validity `invalid`; no outcome evidence
is consumed. For a slot never started because a predeclared stop fired, omit both
receipt and assessment and use `--execution-status not_run`. That records unknown
validity, unassessed outcome, null end time and no invented measurements.
All cases require a concrete reason and termination explanation. Existing terminal
results are not overwritten; genuine corrections require an explicit additive
map correction. If a terminal append is interrupted after writing its immutable
asset directory, inspect that directory before manual guarded recovery.

## Verification

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/registration/test_register.py'
```

Eight temporary-map tests cover preview isolation, identical manifest bytes,
all24 fixed slots, canonical prefix preservation, idempotent append recovery,
stale stores, tampered preview assets, valid task failure, failed-queue outcome
non-consumption, rejection of boolean false as integer zero, and unrun slots.
The tests replace certificate validation with a clearly synthetic fixture; they
test registry mechanics and do not establish scientific admission.
