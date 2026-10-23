# Local model runtime

All three LLM candidates will use the same selected local model and pinned llama.cpp executable. The initial Qwen3-4B Q4_K_M development attempts are retained. Current setup targets official Qwen3-14B Q4_K_M with thinking disabled after those attempts exposed basic action/procedure errors. This is pre-freeze calibration, not a frozen scored model or a claim of improved performance.

The current 14B download is 9,001,752,960 bytes, revision `530227a7d994db8eca5ab5ced2fb692b614357fd`, SHA-256 `500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0`. Metadata and Apache-2.0 identifier were checked from the [official model API](https://huggingface.co/api/models/Qwen/Qwen3-14B-GGUF?blobs=true). The asset table below records the historical 4B setup; current executable identities are in model_setup.py and the immutable per-attempt manifest.

## Historical 4B resources and common runtime permissions

| Resource | Frozen identity | Terms |
|---|---|---|
| Weights | `Qwen/Qwen3-4B-GGUF`, revision `bc640142c66e1fdd12af0bd68f40445458f3869b`, `Qwen3-4B-Q4_K_M.gguf` | [Apache-2.0, official license at pinned revision](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/LICENSE); commercial use permitted subject to license and notices |
| Inference executable | llama.cpp `b9000`, commit `1a03cf47f67be591699d1f0f7ca28e1ed6eb8c7e`, Windows x64 CUDA 13.1; `llama-server.exe` SHA-256 `eaa37a9f56f53649447113d5aac49d50c61436b9db6b4ad829d3786fad54784c` | [MIT, pinned source license](https://github.com/ggml-org/llama.cpp/blob/1a03cf47f67be591699d1f0f7ca28e1ed6eb8c7e/LICENSE); commercial use permitted with notice retention |
| GPU runtime libraries | CUDA 13.1 DLLs distributed by the [official llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/b9000) | [NVIDIA CUDA 13.1 EULA](https://docs.nvidia.com/cuda/archive/13.1.0/eula/index.html), sections 1.1 and 2.1; application use on NVIDIA GPUs permitted. These proprietary runtime libraries are not Apache/MIT software. This local experiment does not redistribute them. |

No accounts, credential use, remote inference, subscription, or new spending are involved. The model/server Python adapters use only the standard library: no additional `requirements.txt` pins are needed. Licenses are downloaded with the assets and hashed in the local manifest; preserve required notices if distributing a derived product later.

| Download | Size (bytes) | SHA-256 |
|---|---:|---|
| `Qwen3-4B-Q4_K_M.gguf` | 2497280256 | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| `llama-b9000-bin-win-cuda-13.1-x64.zip` | 134909459 | `ef8dc3b39295a586b7da641765b19b5c3561c8c6649df0cba825dae1e8fcbec4` |
| `cudart-llama-bin-win-cuda-13.1-x64.zip` | 402582216 | `f96935e7e385e3b2d0189239077c10fe8fd7e95690fea4afec455b1b6c7e3f18` |

Weight hashes come from the [official model API with LFS metadata](https://huggingface.co/api/models/Qwen/Qwen3-4B-GGUF?blobs=true); release-archive hashes come from the [official release API](https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b9000), checked 2026-09-22 Pacific. Setup verifies these fixed values before extraction/use. Every extracted file is hashed into `vendor/model/asset_manifest.json`; start rechecks all binaries and weights. Downloaded artifacts, license copies, server logs and smoke evidence live in the ignored `vendor/model` folder. The nested `.gitignore` is tracked. Root evidence manifests should retain a copy of relevant compact identity/results before closeout.

## Runtime contract

`LocalModel` is owned by the queued supervisor and binds only `127.0.0.1` on a dynamically selected unused port. On Windows it creates no visible window. It exposes no model-side shell tools or local media access. The caller supplies the entire dialogue on every request; prompt caching and thinking are disabled. JSON grammar constrains response syntax but does not prove action validity or task completion. The supervisor must validate and mediate candidate actions and exclude evaluator-private information from prompts.

The current default configuration is 16384 context tokens, at most 1024 output tokens, three inference/prompt threads, one server slot, all model layers on GPU, flash attention enabled, temperature 0, top-p 1, top-k 0, min-p 0, seed 1729, 30-second request timeout and 180-second launch timeout. All values are returned by `identity`. Explicit per-call seeds support paired replicates. Temperature 0 reduces sampling variation but does not claim cross-hardware bitwise determinism. A generation timeout stops the owned server and propagates an exception; waiting for the serial request slot uses the same budget. It never substitutes a scripted answer. Stop runs when the context exits and is registered for normal interpreter exit. On Windows the owned server is additionally assigned to a [kill-on-close Job Object](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), so forced supervisor termination closes the handle and terminates its inference server independently of queue process cleanup.

```python
# This code must itself be inside the shared compute_queue job.
from model_runtime import LocalModel

with LocalModel(log_path=run_directory / "model-server.log") as model:
    reply = model.complete(
        [{"role": "system", "content": "Select a permitted next action."},
         {"role": "user", "content": public_observation_text}],
        action_schema,
        max_tokens=1024,
        seed=replicate_seed,
    )
    # reply: output (parsed JSON), text/raw_text, tokens, prompt_tokens,
    # completion_tokens, usage, latency_s/latency, timings, identity.
```

`generate_json(prompt, schema, system=..., seed=...)` is a two-message convenience method with the same result. Start hash verification and GPU loading belong to declared initialization; request latency includes waiting for the adapter's one-request lock and the actual response. The world clock must run independently while the supervisor awaits inference. The adapter does not implement process sandboxing, candidate quota enforcement, or isolation from evaluator files; those belong to the common harness.

## Setup and verification

From the repository root, submit setup and smoke through the installed queue:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py' submit --project 'LLMs-in-Robotics' --cwd 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics' -- 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\venv\Scripts\python.exe' -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement\Runtime\model_setup.py' --smoke
```

Record the returned ID and require queue `status <id>` to report `succeeded` and `exit_status` 0 before using outputs. A later smoke-only job can run `Runtime/model_runtime.py` through the same queue. The smoke asks the model to inspect an unverified part, checks the JSON action, records startup/request latency and token usage, and stops the server before writing a unique `smoke_result-<timestamp>.json` (the original 8192-context smoke remains `smoke_result.json`). It tests inference plumbing only; robot competence must come from actual experiments.

Host read-only check on 2026-09-22: NVIDIA RTX 5060 Ti, 16,311 MiB device memory, 14,772 MiB free at first check; driver 596.49 reports CUDA 13.2 support. `C:` had approximately 619 GB free. The pinned CUDA 13.1 build avoids depending on the newer release's CUDA 13.4 runtime.

### Attempt record

- `20260923T021802525938Z-3fb5a00d`: setup/smoke submitted at 02:18:02 UTC; queue subsequently reported `interrupted`, `exit_status: null`, and `Worker disappeared; job was not retried`. No setup manifest or inference result was accepted. The child was observed still downloading after the interruption record, so its known process tree (33784, 6280) was explicitly stopped after queue cancellation refused the already-terminal job. The original worker subsequently recorded `failed`, exit 1 at 02:19:55 UTC. The partial file was ignored and was not a valid model.
- `20260923T022323173828Z-4b96b624`: deliberate setup/smoke retry after the prior worker and all known children exited. No other local queue submissions were allowed while this job was active. Official final status verified `succeeded`, exit 0, ended 2026-09-23 02:28:47 UTC. All three asset hashes matched. The actual model returned `{"action":"inspect","target":"part-7"}` with 67 prompt tokens, 19 completion tokens, no cached tokens, and 0.2940265 seconds measured call latency. Server readiness took 1.8274169 seconds after launch; this timing excludes prior binary/model hashing. Context exit stopped the server, an OS check found no remaining `llama-server.exe`, and GPU memory returned to 1299 MiB used / 14752 MiB free. This is one inference smoke result, not a latency distribution or robot result.

The Windows kill-on-close helper was also checked separately with one harmless sleeping child: closing its owned job handle terminated that child immediately. Syntax parsing and a stubbed response-contract check passed; the actual smoke above supplies the inference evidence.

### Existing queue defect and bounded operation

Read-only investigation identified `pid_alive` using `os.kill(pid, 0)` at line 52 of the installed queue, which is unsafe on Windows according to [Python's os.kill documentation](https://docs.python.org/3.12/library/os.html#os.kill). `ensure_worker` can hit this path when another job is submitted while a worker already runs. `status` and `list` normally only read locked state, but contention for the state lock can reach the same unsafe owner-PID probe. The first attempt overlapped another submission and exposed inconsistent state; this is not an inference failure.

The queue was not edited or bypassed. Local operation submits exactly one job when no prior worker remains, monitors only logs/files and OS process state during activity, then runs official queue `status` after natural worker termination and requires `succeeded`, exit 0. This avoids the observed concurrent-submit and lock-contention paths for this task. It does not repair the shared defect or protect against another project's concurrent submission; interrupted or inconsistent attempts remain invalid and need deliberate reruns. The owner of the shared queue should repair and validate the Windows liveness implementation through that project's workflow.

## Context budget revision before candidate trials

After the initial successful 8192-token-context smoke, the configured context was raised to 16384 tokens for the common candidate budget. The earlier smoke retains its actual configuration and is not evidence that this revision ran. Every request now sends the same complete payload through llama.cpp `/apply-template`, then `/tokenize` with special-token parsing, and rejects when prompt tokens plus the reserved output allowance exceed the configured context. Context shifting is explicitly disabled. The returned inference prompt count must equal preflight; a mismatch withholds the response. No consequential context is silently truncated. Preflight hash/count, reserved output, context cap and truncation flag are returned with every successful response. All three requests share the original wall timeout.


## Current calibrated process bounds

Before the 14B smoke loads the server, the adapter assigns its owned process to a Windows Job Object with one process, a three-core CPU-affinity mask and a 12 GiB private-committed-memory limit. Job assignment follows process creation; this is not a claim about the brief preceding startup interval. This revises the initial proposed 8 GiB host allowance for the shared larger model. File-mapped working-set RSS and GPU allocations are distinct metrics and are measured separately. GPU limits are not falsely described as Windows Job Object limits. The candidate wrapper remains a separate single-process, 256 MiB address-space runtime. Actual fit and timing require queued evidence.


The14B setup/smoke was verified successful, exit0, in queue job `20260923T033848008215Z-bcba886b`; exact evidence is `vendor/model/smoke_result-1790135612363179900.json`. The response was inspect/part-7 with67 prompt and19 output tokens,0.6201seconds latency, and server_stopped=true. Reported CUDA model/KV/compute buffers total11028.5MiB. This is a fit/interface smoke, not a robot result; see Calibration Changes for the separate retained-public-packet probe.
