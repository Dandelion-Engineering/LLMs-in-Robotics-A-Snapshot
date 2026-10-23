# Campaign 002 retained-evidence assessment

`assess.py` assesses a single uninterrupted pilot or campaign attempt. It never
launches a model, simulator, process, queue job or credential endpoint. Campaign
001 sources, evidence and results remain unchanged. This assessment always
returns `scorable: false`; scientific admission needs the separately frozen
certificate consumer and storage/release gates.

The caller supplies `expected_revision` explicitly. The manifest's
`framework_revision` and frozen snapshot's `revision` must both equal it. The
snapshot's source inventory must contain the new assessor, direct launcher,
runtime, protected host and timing code, plus the unchanged retained-evidence
helpers and `TimingMonitor` source. Archive entries and current source bytes
must match the snapshot. An arbitrary successful outer worker cannot substitute
for the exact direct `campaign-002/harness/physical.py` queue command.

```python
result = assess.assess(
    manifest, orchestrator_evidence, host_evidence, official_queue_receipt,
    snapshot, predeclared_manifest_sha256, expected_job_id,
    expected_workspace=workspace, expected_revision=predeclared_revision)
```

CLI flags are `--manifest`, `--manifest-sha256`, `--framework-revision`,
`--evidence`, `--host-evidence`, `--queue-receipt`, `--snapshot`, `--workspace`,
`--job-id` and `--output`. The output is created exclusively. `--timing-max-lag-s`
can impose an additional bound; it cannot weaken the unchanged strict monitor.

The official queue must first report `state=succeeded` and integer
`exit_status=0`. Queue identity, exact launcher/paths, manifest bytes/revision
and source/archive integrity are checked before attempt outcomes are read.
Failure of those bindings raises an exception. After binding, malformed timing
or transport evidence becomes an explicit failed check while the observed
independent task outcome stays visible; the valid task outcome becomes unknown.
Original evaluator, lifecycle, namespace retirement, bootstrap, model/client,
canary, continuity, command budget and public-effect checks remain in force.

`verify_timing(host, host_result, frozen)` independently reads
`timing-samples.bin` as little-endian float64 wall/simulation pairs and verifies
`timing-v2.json`. It validates exact byte count/hash, finite nondecreasing clocks,
the initial `(0, 0)`, common monotonic loop origin, final terminal sample, exact
frozen monitor file/class hashes, report equality and host result bindings. It
requires matching Windows scheduling receipts, the declared AboveNormal process
priority, successful paired 1 ms timer requests and restoration to the original
priority. The unchanged monitor requires lag strictly below 0.1 s, one-second
RTF in the inclusive interval 0.95–1.05, and fewer than 1% outside windows.
No full wall window cannot pass. Initialization and cleanup remain outside the
measured loop interval. No between-sample timing precision is inferred.

`verify_transport(stage_root, registry, history)` joins each durable
`broker-requests.jsonl` pre-dispatch trace to its `broker-events.jsonl` reply.
Local capability denials must stay HTTP403 denials and cannot become host
retirement, successful continuity or task evidence. A local revocation fence
requires a matching prior protected host reply; an accepted handback additionally
needs the protected command registry and owner-transfer event. New upstream
requests after a latch fail verification. Any broker failure or ordinary mirror
error remains invalid. A nonfatal mirror connection closure requires a previously
established revocation and the narrow upstream-request error provenance.

`assess_smoke_v2.py` retains the original readiness interruption/fresh-resume
smoke assessor's controls and adds the new bindings, exact `--mode smoke`
launcher, independent timing and per-stage transport checks. Its explicit
manifest does not need to equal the native qualification manifest originally
associated with the framework snapshot. The snapshot is never rewritten or
relabeled. Both invocations still require their original explicit retirement and
old-token denial receipts; completed resume requires native exit0.

```python
result = assess_smoke_v2.assess(
    orchestrator_evidence, host_evidence, official_queue_receipt, snapshot,
    expected_job_id, manifest_path=manifest,
    manifest_sha256=predeclared_manifest_sha256,
    expected_revision=predeclared_revision, expected_workspace=workspace)
```

Run the synthetic assessment tests from the repository root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment" -p "test_*.py"
```

They cover failure before outcome reads, direct-command and explicit manifest
binding, old snapshot identity preservation, source/archive mismatch, timing
corruption and unchanged strict failures, producer/independent-reader agreement,
Windows scheduling failure, transport trace loss, false local successes,
revocation provenance, and the original lifecycle/smoke evidence invariants.
