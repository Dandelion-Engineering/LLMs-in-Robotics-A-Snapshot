# Output-delivery diagnostic: blocked before launch

This directory preserves the prospective six-case design in [OUTPUT_DELIVERY_PROBE_V1.md](../OUTPUT_DELIVERY_PROBE_V1.md) and deterministic protocol tests. **It is not a qualified or launched diagnostic.** No model, native app-server probe, WSL fixture or simulation was launched to implement or test these files.

Subsequent source review found that the pinned app-server `command/exec` implementation uses a local subprocess launcher. In [command_exec.rs](../native-output-source-001/codex-rs__app-server__src__command_exec.rs), lines 143–229 handle the local Windows sandbox and lines 231–294 convert the cwd to a local absolute path and call `codex_utils_pty::spawn_*`. Selecting a default remote environment does not provide a supported route through this API. A fresh source retrieval is evidence about the tagged implementation, not proof of the installed binary's precise cause of smoke008's loss.

`run()` therefore raises an explicit unsupported-route error before checking sources, creating output or constructing Runtime. The original planned lifecycle is retained in the deliberately unlaunched `_unlaunched_draft_run`; it is not reachable from the CLI. Do not bypass this block or treat passing synthetic tests as remote-path qualification. A different supported method requires a new prospective contract.

The pure `make_cases()` returns exactly six fixed cases: immediate streaming, separated streaming, immediate buffered, separated buffered, empty streaming, and mixed stdout/stderr streaming. Nonempty stdout is 13,029 bytes in two producer writes (8,192 + 4,837); separated variants sleep 100 ms between writes; mixed stderr is 257 bytes. Total expected output is 65,402 bytes. Planned bounds are 65,536 bytes per stream, ten seconds per command and 120 seconds for the whole diagnostic. Production configuration, instructions and evidence criteria remain unchanged.

The draft would use existing Runtime/canaries, captured executor, native Client on a worker thread, and an isolated producer. Streaming final responses are empty by protocol; streaming deltas and buffered final responses are checked separately. Original command response/delta wire lines are retained separately from parsed client events. `assess_records(app, wire, captures)` performs deterministic route, identity, sequence, delivery, close, exit, output-cap and exact byte-parity checks. A byte gap remains a failed parity observation; it is never filled from executor bytes. `assess(output, snapshot, manifest)` is a separately callable fail-closed replay, but no empirical output exists for this abandoned route.

Metadata helpers `required_inputs()` and `binary_bindings()` perform file reads only. The manifest schema is `campaign002-output-delivery-probe-manifest-1`, with `run_id`, `framework_revision`, exact `cases=make_cases()`, zero integer `model_calls` and `model_turns_max`, false `physical_simulation` and `recovery_actions`, `runtime_input_files` as repository-relative strings, `input_bindings` mapping each string to `{sha256, bytes}`, and `binaries=binary_bindings()`. Each binary entry has `path`, `host_path`, `sha256`, and `bytes`. Source checks require the manifest SHA in the snapshot and the existing complete frozen-source verification.

Planned CLI (currently blocked): `probe.py --snapshot PATH --manifest PATH --output PATH`. Read-only assessment CLI: `probe.py --snapshot PATH --manifest PATH --assess OUTPUT`. There is no `run` subcommand and no case-tuning argument. Planned result schema is `campaign002-output-delivery-probe-1`; `execution_completed` and `passed` are distinct. Standalone command output could not establish model unified_exec/code-mode subscriber behavior even if a remote route were available.

Run only the deterministic tests:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair/output-delivery-diagnostic" -p test_probe.py -v
```

No files in the frozen harness, native binary, original assessment or failed smoke008 were changed. The smoke008 startup-read criterion and failure remain intact.
