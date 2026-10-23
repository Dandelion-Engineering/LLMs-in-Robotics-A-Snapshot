# Batch 01 evaluation release plan

**Status: complete proposed matrix and analysis implementation; no scored release or concealed evaluation seeds have been created by this work.** Randy requested complete experiments, including their prerequisites, followed by the engineering investigation workspace. The generator and plan support that work; they do not replace it or establish that the physical workcell, candidates or scored-readiness gates have passed.

The [original evaluation design](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Evaluation.md), [common contract](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Contract.md), [evidence requirements](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Evidence%20and%20Investigation.md) and [shared implementation contract](Shared%20Implementation%20Contract.md) govern execution. [protocol.py](../Runtime/protocol.py) implements the matrix, release checks and analysis; [test_protocol.py](../Runtime/test_protocol.py) contains clearly labeled synthetic unit checks. Test fixtures are not runs and never enter the Architecture Map.

## Exact scope

The main comparison includes the conventional durable baseline and all three LLM architectures. Every entrant receives the same 24 cases, each with two independently seeded policy/noise replicates. All main runs retain candidate episode storage. Three within-candidate controls remove persistence at restart; the baseline keeps normal durable state.

| Component | Cases per entrant | Replicates | Entrants | Runs |
|---|---:|---:|---:|---:|
| Main persistent comparison | 24 | 2 | 4 | 192 |
| No-persistence control | 12 | 2 | 3 LLM candidates | 72 |
| **Complete release** | | | | **264** |

Each LLM candidate therefore has 48 main runs plus 24 controls; the baseline has 48 main runs. The optional summary-only control is not included in this release. Adding it would require a declared extension before scored evidence is inspected.

The proposed horizon settings are three parts and a 300-second cap for short cases, six parts and a 600-second cap for standard cases, and ten parts and a 900-second cap for extended cases. These are within the original task-size ranges. They remain calibration settings until the full workcell demonstrates that its layouts, tray capacity, insert changes, sensing and recovery opportunities can support them. Change numerical settings openly before freeze if evidence requires it, then update the generator/tests and its hash. Do not silently reduce the matrix or shorten scored caps to finish sooner.

| Horizon | Nominal | Physical or order change | Continuity or mixed | Total cases |
|---|---:|---:|---:|---:|
| Short | 3 | 2 | 3 | 8 |
| Standard | 2 | 3 | 3 | 8 |
| Extended | 3 | 3 | 2 | 8 |
| **Total** | **8** | **8** | **8** | **24** |

For this release, all eight cases in the physical-or-order-change group use **order changes**. The continuity group contains four restart cases and four mixed order-change/restart cases. These choices fit the current scenario vocabulary: `nominal`, `order_change`, `restart`, `mixed`. They do not establish performance under grip-force changes, displaced parts, obstacles, machine faults or every disturbance in the wider design. Each actual disturbance exposure and any declared fallback must still be recorded; failure to reach a physical trigger is not recovery.

## Counterparts, seeds and independence

The four uninterrupted counterparts are already included in the eight nominal cases:

| Nominal case | Interrupted case | Horizon | Exact counterpart relationship |
|---|---|---|---|
| C01 | C06 | Short | Same initial world/order; restart removed |
| C09 | C14 | Standard | Same initial world/order; restart removed |
| C10 | C15 | Standard | Same initial world/order; restart removed |
| C17 | C23 | Extended | Same initial world/order; restart removed |

All four interrupted members are pure restart cases. Choosing mixed cases here would leave order amendments in their uninterrupted counterparts, making a nominal label misleading. The 12-case ablation subset comprises all eight continuity/mixed cases plus the four listed nominal counterparts. Its horizon split is four short, five standard and three extended cases. Counterpart horizons are balanced as closely as four pairs across three horizons permits: one, two and one.

World and layout seeds stay fixed across entrants, persistence conditions and both policy/noise replicates of a case. Exact counterpart cases also share these seeds. Policy and sensor-noise seeds are separate from the world/layout seeds, differ between the two replicates, and are matched across entrants and conditions within a replicate. The counterfactual interruption can change later observations and model outputs; matching seed identities does not promise identical trajectories or random draws after divergence.

There are **24 case units**, not 48 independent scenarios. Four pairs deliberately reuse the same initial scenario family, leaving **20 matched scenario families**. The primary bootstrap resamples those 20 families, retaining both noise/policy replicates and both members of each counterpart pair together. For the persistence subset, 12 case units form eight families. The analysis exposes these denominators. A separately labeled case-cluster diagnostic is available; it does not replace the conservative family-cluster analysis or establish that the matched cases are independent.

Only explicit creation of a ready, frozen release generates cryptographic seed values. Public case descriptions, plan inspection and analysis do not generate future seeds. The protected manifests contain them; candidate observation packets, prompts and episode mounts must not. The OS isolation evidence must show that the chosen operator/evaluator directory is inaccessible to candidates. A folder name or Windows read-only flag does not provide that protection.

## Freeze and gate contract

`create` refuses to run without both an existing freeze manifest and readiness evidence. A minimum freeze JSON has these fields:

```json
{
  "release_id": "batch01-eval-r1",
  "frozen_at": "<actual ISO timestamp with timezone>",
  "code_sha256": "<64 lowercase hexadecimal characters>",
  "environment_sha256": "<64 lowercase hexadecimal characters>",
  "model_sha256": "<64 lowercase hexadecimal characters>",
  "protocol_sha256": "<exact current protocol.py SHA-256>",
  "selection_criteria": "<predeclared selection and representative-trace rules>",
  "maximum_retries": 0
}
```

These placeholders document the schema and cannot pass validation. The code/environment/model hashes identify actual frozen bundles containing the candidate code, common services, evaluator/scenario generator, dependency/controller versions, weights, tokenizer, settings, prompts and development knowledge. The generator checks the protocol source hash itself. The supervisor must independently verify that all frozen artifacts actually match and are used; four syntactically valid hash strings cannot establish that fact.

Readiness must contain `scored_ready: true`, the same `release_id`, `freeze_sha256` matching the exact freeze file, an `evidence_refs` array of real path/SHA-256 pairs, and all of these explicit Boolean gates:

- `physical_workcell`: the complete contact-based task is reachable and physically feasible at every horizon.
- `public_perception`: delivered detections and process marks derive from permitted sensors, with calibrated uncertainty and age.
- `independent_evaluator`: completion, partial work, errors and disturbance exposure are checked independently of candidate declarations.
- `conventional_baseline`: the competent durable comparator and admissible recovery opportunities have been calibrated.
- `candidate_implementations`: all three actual LLM mechanisms and matched persistence conditions operate within the shared interface.
- `model_and_terms`: local model/runtime identity, resource fit and commercial-use terms have been checked.
- `isolation`: candidate filesystem, process, network and actuator restrictions have passed adversarial tests.
- `timing_and_resources`: physics advances during inference; deadlines, quotas and frozen lag tolerances have measured support.
- `evidence_retention`: logs, frames, context versions and consequential chains are retained within verified capacity.
- `disturbance_admissibility`: each released case and intervention opportunity is valid, with exposure/fallback rules fixed.
- `equal_development_opportunity`: the common development budget and any symmetric extensions are documented before selection.

The generator verifies referenced evidence bytes and refuses missing, changed or failed gates. It cannot judge whether their scientific/engineering interpretation is correct. A failing gate means continue the authorized prerequisite work, preserve its evidence and resolve the failure; it does not authorize bypassing the gate or relabeling development runs as evaluation. A successful `create` command generates manifests only. Registration, execution and independent result recording remain required.

From the project root, the read-only command is:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Runtime/protocol.py' describe
```

After actual freeze/readiness files exist, explicitly run `protocol.py create --release-dir <new protected operator directory> --freeze-manifest <actual freeze JSON> --readiness <actual readiness JSON>` using the same interpreter. The selected parent directory must already exist; creation refuses to overwrite a release. The output contains one plain JSON manifest per run, a hash-bound release index, and a randomized schedule across paired blocks and within each block. Standard output exposes counts and artifact hashes rather than seeds. Do not copy protected manifests into the candidate workspace.

## Execution and evidence duties

Register each exact attempt manifest and frozen revision before execution. Submit sustained work through the shared queue, record its job ID, and require `succeeded` with exit status zero before using its output. A successful queue job is not successful robot work: every attempt still needs independent outcome, execution status and validity. Preserve failures, timeouts, contract violations, cancellations and infrastructure-invalid attempts. Reruns receive new IDs and links to the original attempt; no automatic retries are hidden inside a scored run.

At the proposed caps, the main comparison has a 32-wall-hour maximum task-time allowance. The controls add 11 hours 30 minutes, for **43 hours 30 minutes across 264 runs**, before launch, logging, development and diagnostics. At the design's conservative 2 GiB per ordinary run, 264 runs imply **528 GiB** before rich captures. Neither value is measured throughput or storage consumption. Preflight real capacity, compression and resource contention; schedule bounded batches and retain all attempts. Do not launch the complete matrix blindly or delete failed evidence to fit it.

The release currently separates world/layout and policy/noise seeds. The supervisor must actually apply their intended roles and expose their hashes in protected evidence. Assigning extra seed fields that execution ignores is not a passed implementation. Likewise, declared thresholds, controls and retention limits require measured verification before the gate can pass.

## Analysis and return

The analysis library accepts the complete 264-manifest release and one explicitly selected terminal result per run. Resolve append-only result corrections beforehand and preserve that selection's provenance; duplicate or unknown run IDs are rejected. Missing results, `not_run`, nonterminal execution, unknown validity and missing outcomes remain distinct. They are not fabricated failures, successful runs or zero-duration measurements.

Infrastructure-invalid evidence excludes the entire affected case/replicate block across all entrants and persistence conditions. A valid candidate crash, timeout or contract failure stays in the denominator. The report lists excluded blocks and triggering evidence. Uncertain exclusions require a separately labeled adjudication/sensitivity analysis; their source records must remain unchanged.

The report returns six main pairwise comparisons and three within-candidate persistence comparisons, exact paired success tables, counts and rates, raw paired rows, horizon/disturbance strata and seeded scenario-family bootstrap intervals. Small selected case sets do not support broad population or factory-reliability claims. Full-system differences do not by themselves isolate the language model or its memory mechanism.

Successful completion times remain measured values or explicitly missing. Failed runs are right-censored; their actual observed wall duration is kept separately from a failure marker placed at the protocol cap. That cap marker is a display convention, not measured completion time or evidence that an early crash ran until the cap. There is no unlabeled timeout-penalized mean and no success-only speed claim that silently omits failures.

The CLI is `protocol.py analyze --release-dir <protected release directory> --results <JSON array of selected results> --output <new analysis JSON> --analysis-seed <declared integer>`. The analysis seed is public and distinct from concealed evaluation seeds. The investigation workspace should consume the resulting denominators, exclusions, paired cases and actual evidence links. Completing that workspace and the entire authorized experimental batch still requires the real runs and their validated records.
