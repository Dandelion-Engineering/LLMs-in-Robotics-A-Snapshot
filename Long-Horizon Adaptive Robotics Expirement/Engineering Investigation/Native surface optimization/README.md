# Native surface export proposal

Applied by root at 2026-09-23 08:45:14 UTC with exact source guards; [integration.json](integration.json) records the application. The exact original exporter and staged proposal remain archived, and the historical `manifest.json` binds their hashes and the patch. Only `Runtime/restart_physical_class.py` changes. All current live model fields are still inspected each export; only verified exact native bytes avoid repeated descriptor computations. See [the source diagnosis and limits](../Hold%20and%20rich%20capture%20timing%20proposal.md).

Twelve [static checks](../native_surface_checks.py) passed in 0.403 s. They cover actual native model surfaces, cold/repeated outputs, same-time mutations of model arrays/options, nonfinite values, mark color rules, fresh XML/registry/seal checks, synthetic new/missing/unsupported properties and dtype/shape/signed-zero changes, model replacement, returned-payload isolation, weak-key release, and full rich-capture/classification equality through authority/device/observation/future changes. They do not step physics or establish performance.

Run the bounded checks from the project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/native_surface_checks.py'
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/hold_observation_regression.py'
```

The surface checks select the applied Runtime module only if it exactly matches the retained staged hash; otherwise they test the staged module while requiring Runtime to match the original. Neither mode accepts an unrecorded implementation. The hold regressions compare the applied module with hash-exact archived pre-change bytes; its twelve tests passed in 0.038 s.

Root queued this payload before applying the exporter patch:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/benchmark_native_surface.py" --output "Long-Horizon Adaptive Robotics Expirement/Evidence/derived/native-surface-benchmark-001" --repeats 8
```

The helper enforces its own queue process ownership. It constructs one n10 model, performs native forward initialization, and runs no `mj_step`, Cell, planner, sensor, policy or candidate. Source inputs and final native-state identity are checked before/after. The first call is memo-cold with an already initialized evaluator index cache; it is not a fresh-process startup measurement. Then eight pairs of warm calls per implementation alternate order. Both class export and full rich capture retain raw wall/CPU measurements and actual output hashes, with exact dictionary equality required against the original. Full original/proposed outputs are retained separately. This isolates CPU cost on one fixed native state; a later unchanged-rule construction/qualification remains necessary.

The benchmark officially succeeded under job `20260923T084415083917Z-00143ee6`, ending 08:44:18.121406 UTC. Outputs matched exactly, with unchanged native state and source inventories. Warm class-export median wall time was 25.02025 ms before and 9.7624 ms after; warm rich capture was 27.98365 ms before and 12.7093 ms after. First memo-cold rich capture was 26.2229 and 25.8089 ms. [Benchmark 001](Benchmark%20001.md) links the retained result and official receipt. Later construction 002 passed 28/28 physical trials and 24/28 timing checks; four RTF failures remain, so qualification is still pending.

The helper retains its original pre-integration Runtime hash guard; the command above is the historical executed payload, and will intentionally refuse the now-modified current exporter without a reviewed benchmark revision. The original results and guards must not be silently replaced. Root verified all 436 Runtime tests passed in 40.855 s under job `20260923T084539361298Z-0e0c1c2e` and 29 fixture tests passed in 0.315 s.
