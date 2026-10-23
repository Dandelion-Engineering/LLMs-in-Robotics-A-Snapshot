# Proposed single stage-timed resource probe

Prepared before execution. Read `stage-probe-plan.json`; no probe has been run by the author. The existing r4 hold remains in force.

Queue the installed project Python directly against `stage_probe.py --output <fresh absolute output directory>`. The output parent must already exist. Use `-X utf8 -B`. Do not queue the private child mode separately. There is no automatic submission, repetition, policy episode, source mutation, or release-review action in this script.

The fixed phases are **30 seconds host idle, 30 seconds loaded-model idle, 120 seconds generic inference**. One model lifetime uses the original model configuration and budgets. A request admitted just before the inference window ends may finish under its original 30-second budget; its drain is separately recorded. At most 120 requests can be submitted. Host and model stages use separate samplers so a host-only sample is not incorrectly treated as an active-model observation; the model sampler remains continuous between its idle and inference phases.

The parent verifies actual queue ownership, records the exact source inventory and command, and launches one declared, directly verified child in a Windows kill-on-close job. The child owns its model and GPU processes. The parent has a 480-second total child limit, covering the 180-second phases, original model startup limit, artifact verification and bounded cleanup. A timeout or incomplete cleanup remains failure evidence.

Both ownership snapshots read live queue state using a hidden PowerShell `FileStream` with `FileAccess.Read` and `FileShare.ReadWrite|Delete`, closing the handle before returning content. Parent ownership uses the frozen `queued_job` code object with a private globals dictionary overriding only the queue-state reader; all other artifact loads and ownership checks remain unchanged. There is no shared module mutation, ordinary live-state open, queue status call or queue write.

GPU instrumentation uses the existing `resources.gpu_sample` and installed Python `subprocess.run` code objects with private function-global dictionaries. Only that GPU path sees a timed `Popen` subclass. The model's global `subprocess` module is untouched. Entry markers are flushed before native calls; completed stage durations exclude entry-marker writing. Sampler capture/publication also includes instrumentation overhead, which is explicitly not equivalent to uninstrumented timing.

`report.json` distinguishes `diagnostic_collection_completed` from `no_failure_observed`. A cleanly retained GPU timeout may produce a completed diagnostic with `no_failure_observed=false`; that is useful failure evidence, not a health pass. Inspect the official queue receipt, `probe/result.json`, per-thread `probe/stage-traces/*.jsonl`, and both original resource streams. No aggregate success flag authorizes continuation. Preserve all outputs and stop at the first observation/model failure.

One explicit cleanup allowance is diagnostic-only: if frozen `ResourceSampler.close()` reaches its five-second bound, its failure is retained while the already-in-flight capture gets ten more seconds to expose its drain/exit stages. This never restarts sampling or changes the seven-second observation gate. Unresolved cleanup causes a nonzero diagnostic exit and parent containment removes descendants.

No tests, native imports, probe execution, registration, queue admission, or source changes outside this staging directory were performed during preparation. Root review and actual queued execution remain required. Passing nonreproduction does not justify another isolated-incident continuation decision by itself.
