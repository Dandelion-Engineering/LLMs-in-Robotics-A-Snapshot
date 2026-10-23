"""Recompute campaign sizing from completed compact evidence; never launch work.

Run with project Python and --write to replace this helper's two derived outputs.
Only standard-library metadata reads/arithmetic are performed. No simulator,
candidate, model, queue command, protected seed generation, or raw trace read.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPERIMENT = ROOT / "Long-Horizon Adaptive Robotics Expirement"
INTEGRATION = EXPERIMENT / "Robot-Codex Integration 001"
SOURCES: dict[str, dict] = {}


def source(path: Path):
    content = path.read_bytes()
    relative = path.relative_to(ROOT).as_posix()
    SOURCES[relative] = {
        "path": relative, "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }
    return content


def load(path: Path):
    return json.loads(source(path))


def relocate(recorded: str):
    normalized = recorded.replace("\\", "/")
    marker = "Long-Horizon Adaptive Robotics Expirement/"
    if marker not in normalized:
        raise ValueError("Evidence path outside expected experiment")
    return EXPERIMENT / normalized.split(marker, 1)[1]


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def distribution(values):
    present = sorted(x for x in values if isinstance(x, (float, int)))
    if not present:
        return {"n": 0, "missing_reason": "No measured values"}
    return {
        "n": len(present), "sum_s": sum(present),
        "mean_s": statistics.mean(present),
        "sd_s": statistics.stdev(present) if len(present) > 1 else None,
        "minimum_s": present[0], "median_s": statistics.median(present),
        "p90_nearest_rank_s": present[math.ceil(.9 * len(present)) - 1],
        "maximum_s": present[-1],
    }


def wilson(successes, n, z=1.959963984540054):
    p = successes / n
    denominator = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denominator
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
    return [centre - half, centre + half]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    selected = load(EXPERIMENT / "Evidence/derived/evaluation-r4-administrative005-001/selected-results.json")
    analysis = load(EXPERIMENT / "Evidence/derived/evaluation-r4-analysis005-001/analysis.json")
    provenance = load(EXPERIMENT / "Evidence/derived/evaluation-r4-analysis005-001/analysis-provenance.json")
    assert selected["complete_disposition_accounting"] and provenance["status"] == "complete"
    assert provenance["inputs_unchanged"] and analysis["result_records_supplied"] == 264
    results, times = selected["results"], analysis["time_observations"]
    assert len(results) == 264 and len({r["run_id"] for r in results}) == 264
    receipts = {}
    for row in selected["provenance"]:
        ref = row.get("official_queue_receipt")
        if ref:
            path = relocate(ref["path"])
            data = load(path)
            actual = SOURCES[path.relative_to(ROOT).as_posix()]["sha256"]
            if actual != ref["sha256"]:
                raise ValueError("Selected-result receipt hash mismatch: " + str(path))
            receipts[data["id"]] = data
    groups = []
    for entrant in analysis["entrants"]:
        rows = [r for r in times if (r["architecture"], r["condition"]) ==
                (entrant["architecture"], entrant["condition"])]
        cases = defaultdict(list)
        for row in rows:
            cases[row["case_id"]].append(row)
        pairs = [v for v in cases.values() if len(v) == 2]
        groups.append({
            **entrant,
            "observed_wall_duration": distribution([r["observed_wall_duration_s"] for r in rows]),
            "success_completion_time": distribution([r["completion_time_s"] for r in rows if r["task_success"]]),
            "fully_observed_two_replicate_cases": len(pairs),
            "within_case_success_disagreements": sum(p[0]["task_success"] != p[1]["task_success"] for p in pairs),
            "paired_absolute_wall_duration_difference": distribution([
                abs(p[0]["observed_wall_duration_s"] - p[1]["observed_wall_duration_s"]) for p in pairs]),
        })
    measured = distribution([r.get("wall_duration_s") for r in results])
    queue_durations = [(timestamp(r["ended_at"]) - timestamp(r["started_at"])).total_seconds()
                       for r in receipts.values()]
    queue_sum = sum(queue_durations)
    queue_span = (max(timestamp(r["ended_at"]) for r in receipts.values()) -
                  min(timestamp(r["started_at"]) for r in receipts.values())).total_seconds()
    episode_missing = [r["run_id"] for r in results if r.get("wall_duration_s") is None]
    # This difference includes the unmeasured interrupted episode, not pure overhead.
    queue_minus_observed = queue_sum - measured["sum_s"]
    pilot_manifest = load(INTEGRATION / "readiness-session-10/records/pilot-001-manifest.json")
    pilot_queue = load(INTEGRATION / "readiness-session-10/records/pilot-001-queue.json")
    pilot_assessment = load(INTEGRATION / "readiness-session-10/assessment/pilot-001.json")
    pilot_supplement = load(INTEGRATION / "readiness-session-10/assessment/pilot-001-terminal-lifecycle-supplement.json")
    pilot_duration = (timestamp(pilot_queue["ended_at"]) - timestamp(pilot_queue["started_at"])).total_seconds()
    controls = []
    for path in sorted((INTEGRATION / "records").glob("RCI001-*-result.json")):
        data = load(path)
        controls.append({"run_id": data["run_id"], "mode": data["mode"],
                         "wall_elapsed_s": data["wall_elapsed_s"], "terminal": data["terminal"],
                         "independent_success": data["independent_outcome"]["success"]})
    for path in [INTEGRATION / "host/challenges.py", INTEGRATION / "host/run_host.py",
                 EXPERIMENT / "Runtime 004/cell.py", INTEGRATION / "readiness-session-10/README.md", Path(__file__)]:
        source(path)
    precision = []
    for per_family in (8, 12, 16):
        precision.append({"per_family": per_family, "total_model_episodes": 2*per_family,
            "family_wilson_95_at_half_success": wilson(per_family//2, per_family),
            "mixture_wilson_95_at_half_success_descriptive": wilson(per_family, 2*per_family),
            "family_chance_observe_failure_if_failure_probability_0p2": 1-.8**per_family,
            "family_chance_observe_failure_if_failure_probability_0p1": 1-.9**per_family,
            "family_all_success_one_sided_exact_95_lower": .05**(1/per_family),
            "host_wall_cap_sum_h": 2*per_family*pilot_manifest["wall_cap_s"]/3600})
    comparison = [{k: c[k] for k in ("name", "paired_run_count", "scenario_families",
                    "paired_success_difference", "paired_table", "bootstrap")}
                  for c in analysis["comparisons"] if c["left"]["architecture"] == "baseline"
                  and c["right"]["architecture"] == "A3"]
    output = {
        "schema": "robot-codex-first-campaign-empirical-sizing-1",
        "scope": "Sizing from completed metadata only; recommendation is not an immutable attempt release or launch authorization",
        "completed_batch01": {
            "selected_disposition_counts": selected["counts"], "primary_dispositions": analysis["dispositions"],
            "planned_counts": analysis["planned_counts"], "measured_episode_wall": measured,
            "missing_wall_duration_run_ids": episode_missing,
            "outcome_counts": [{"execution_status": k[0], "validity": k[1], "outcome": k[2],
                "termination_reason": k[3], "count": n} for k,n in Counter((r.get("execution_status"),
                r.get("validity"),r.get("outcome"),r.get("termination_reason")) for r in results).items()],
            "entrant_groups": groups, "baseline_a3_comparison": comparison,
            "excluded_paired_blocks": analysis["excluded_paired_blocks"],
            "queue": {"receipt_count": len(receipts), "state_counts": dict(Counter(r["state"] for r in receipts.values())),
                "duration": distribution(queue_durations), "elapsed_span_s": queue_span,
                "queue_minus_measured_episode_s": queue_minus_observed,
                "residual_per_planned_disposition_s": queue_minus_observed/264,
                "residual_interpretation": "Queue launch/teardown/integrity/other costs plus one unmeasured interrupted episode; not pure overhead",
                "time_outside_recorded_queue_occupancy_s": queue_span - queue_sum},
        },
        "existing_rci_evidence": {"development_controls": controls, "pilot_queue_wall_s": pilot_duration,
            "pilot_host_manifest_caps": {k: pilot_manifest[k] for k in ("sim_cap_s", "wall_cap_s", "invocation_wall_cap_s", "storage_cap_bytes")},
            "pilot_independent_outcome": pilot_assessment["recovery_and_task_outcome"]["independent_task_outcome"],
            "pilot_strict_check_pass_count": sum(pilot_assessment["checks"].values()),
            "pilot_strict_check_count": len(pilot_assessment["checks"]),
            "pilot_lifecycle_supplement_retained": bool(pilot_supplement),
            "limits": "Single stock pilot and one control per family; no RCI runtime variance estimate or home-model result"},
        "sample_size_sensitivity": precision,
        "recommendation": {
            "fixed_model_attempts": 24, "attempts_per_family": 12,
            "families": ["misplaced-stock", "blocked-insert-home"],
            "world_seed": 173,
            "noise_seed_allocation": "24 distinct fresh protected seeds, 12 per family, generated once and frozen before scoring; exclude development seed13",
            "model_seed": "No controllable model seed qualified; record fresh thread identity and fixed Astra Max configuration, not a fictional seeded model replicate",
            "schedule": "12 consecutive blocks, one attempt from each family per block; counterbalance family-first order six/six before observing outcomes",
            "runtime_workspace": "Fresh per attempt; no prior episode memory, conversation, program, or continuation artifacts carried between independent episodes",
            "primary_endpoint": "Protected independent full-task success after recovery and conventional continuation, reported separately within each fixed fixture family",
            "secondary_endpoints": ["accepted protected handback", "productive conventional follow-through", "action/outcome/observation evidence", "durable continuity behavior", "failure category", "observed runtime with failures censored, never success-only speed"],
            "continuity_scope": "Natural within-invocation continuity only; do not inject restarts or ablations into this first fixed-framework campaign; prior interrupted smoke remains development evidence",
            "sample_size_reason": "12 per family yields >90% chance of observing a within-family failure occurring 20% of the time, improves precision materially versus 8 while avoiding the extra 33% time of 16 for only 4.06 percentage points greater 20%-failure detection probability",
            "stopping": "Fixed 24; no success/futility early stop, no outcome-driven extension, replacement, or retry. Safety/integrity/source-identity failure stops campaign, preserving remaining slots as not_run",
            "infrastructure": "Declare evidence-based invalidity categories before launch; keep invalid attempts and no replacements; report validity denominator and all-planned sensitivity, never relabel model timeout, valid refusal or valid task failure as infrastructure",
            "exact_source_constraint": "Use frozen 010d framework bytes. Any manifest/protocol/analysis adapter must remain outside robot framework and preserve actual host development-only labels if unchanged validation requires them",
            "claims": "Initial repeatability and failure mechanisms within two fixed simulated fixtures under fresh sensor noise and fresh model invocations; not 24 independent scenarios, broad reliability, an architecture effect, or causal memory benefit",
        },
        "runtime_projections": {
            "planned_count_reduction_fraction": 1-24/264,
            "at_batch01_observed_episode_mean_h": 24*measured["mean_s"]/3600,
            "at_batch01_queue_occupancy_per_disposition_h": 24*queue_sum/264/3600,
            "at_single_stock_pilot_queue_wall_h": 24*pilot_duration/3600,
            "sum_inherited_host_wall_caps_h": 24*pilot_manifest["wall_cap_s"]/3600,
            "sum_caps_plus_old_residual_sensitivity_h": (24*pilot_manifest["wall_cap_s"]+24*queue_minus_observed/264)/3600,
            "sum_model_invocation_caps_h": 24*pilot_manifest["invocation_wall_cap_s"]/3600,
            "host_cap_sum_vs_prior_measured_queue_fraction": 24*pilot_manifest["wall_cap_s"]/queue_sum,
            "storage_episode_caps_bytes": 24*pilot_manifest["storage_cap_bytes"],
            "limits": "None is a predicted completion guarantee or hard queue budget. RCI differs from old local-Qwen campaign; single stock pilot cannot estimate home latency or tail. Queue gaps/analysis/operator time and additional retained boundary artifacts are outside episode caps. Final protocol must enforce outer limits and current storage admission separately.",
        },
        "sources": list(SOURCES.values()),
    }
    # Verify all source bytes stayed unchanged across this bounded read/derive.
    for ref in output["sources"]:
        if hashlib.sha256((ROOT/ref["path"]).read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("Source changed during sizing: " + ref["path"])
    output["inputs_unchanged"] = True
    p12 = precision[1]
    report = f'''# First Robot-Codex campaign: empirical sizing

Recommend **24 once-only model episodes: 12 per existing recovery family**, exact RCI001-wsl-010d, with one fresh invocation and workspace per episode. This is a sizing recommendation for the separately frozen campaign protocol. It introduces no new framework, comparison, restart condition or ablation.

## What completed Batch 01 actually cost and showed

The completed r4 administrative selection accounts for all 264 planned dispositions: 132 original finalized, 131 annex finalized, and one administrative interruption whose episode duration is missing. Its source-bound analysis contains 253 primary-eligible results; 11 members of two infrastructure-affected paired blocks remain excluded and visible.

The 263 measured episode durations total **{measured['sum_s']/3600:.3f} hours**; mean {measured['mean_s']:.2f} s, SD {measured['sd_s']:.2f} s, median {measured['median_s']:.2f} s, nearest-rank 90th percentile {measured['p90_nearest_rank_s']:.2f} s. These are observed durations including failures, not completion times. Across 69 exact referenced queue receipts, 68 succeeded/0 and one interrupted: summed occupancy was **{queue_sum/3600:.3f} hours**, and first-start to last-end spanned **{queue_span/3600:.3f} hours**. The difference of {queue_minus_observed/3600:.3f} hours between queue occupancy and measured episodes includes launch/teardown/integrity work **and the unmeasured interrupted episode**; it is not a pure overhead estimate. Calendar span includes {(queue_span-queue_sum)/3600:.3f} hours outside those queue executions.

| Eligible condition | Success | Observed wall mean / SD (seconds) | Fully paired cases / success disagreements |
|---|---:|---:|---:|
'''
    for group in groups:
        d = group['observed_wall_duration']
        report += f"| {group['architecture']} {group['condition']} | {group['success_count']}/{group['eligible_runs']} | {d['mean_s']:.2f} / {d['sd_s']:.2f} | {group['fully_observed_two_replicate_cases']} / {group['within_case_success_disagreements']} |\n"
    report += f'''
The old main entrants each have 22 cases with both eligible replicates, with **zero success disagreements within each case**. Case/horizon/architecture differences dominated binary outcomes in that campaign; the same-case baseline median absolute duration difference was 0.466 s and A3's 1.519 s, although their maxima were 66.80 s and 66.16 s. Repeating the old 264-slot cross-architecture/persistence matrix would answer a different question. These old low-noise replicate observations do not establish low stochastic variability for the new hosted Astra framework. Selected scenarios are not a sample of factory tasks.

## Fixed sample and seed allocation

Use 12 episodes of `misplaced-stock` and 12 of `blocked-insert-home`. Keep the already qualified physical fixture and world seed 173 fixed. Use 24 distinct fresh protected sensor-noise seeds (excluding 13), generated once, with 12 assigned per family before the first score. In 12 sequential blocks, run one of each family; counterbalance which family comes first six/six. The final immutable manifests contain the actual allocation. No future seeds are generated by this sizing helper.

The implemented world seed changes mass, friction, part color, process time and some initial positions. The fixture then overwrites the challenged object's initial pose. Fresh world seeds would therefore expand the physical qualification scope without creating wholly new challenge families. Keeping 173 makes the first claim explicitly about the two fixtures already built. The sensor seed drives RGB/depth readout noise; it is not a model seed. No model RNG seed is qualified. Each episode starts a new Astra Max thread and empty episode workspace, with fixed instructions, no previous-run carryover, and the ordinary one-invocation pilot bounds. Fresh invocation is an independent reset, not proof that service stochasticity is statistically independent or identically distributed.

At 12 per family, the chance of seeing at least one failure when the conditional failure probability is 20% is **{100*p12['family_chance_observe_failure_if_failure_probability_0p2']:.2f}%**. At 10% failure it is only {100*p12['family_chance_observe_failure_if_failure_probability_0p1']:.2f}%. The worst-case 95% Wilson interval (6/12) is **{100*p12['family_wilson_95_at_half_success'][0]:.1f}–{100*p12['family_wilson_95_at_half_success'][1]:.1f}%**. Even 12/12 successes gives a one-sided exact 95% lower bound of only {100*p12['family_all_success_one_sided_exact_95_lower']:.1f}%. Thus 24 episodes can reveal common repeatability/failure patterns; it cannot establish high reliability or a small advantage.

Eight per family has only 83.22% chance to see a 20% failure mode and a worst-case Wilson interval of 21.5–78.5%. Sixteen per family improves detection to 97.19%, but costs 33% more time than 12 for roughly 4.06 percentage points more detection. Twelve is a predeclared engineering compromise for initial common-mode characterization, not a confirmatory power calculation. Family-wise counts and intervals are primary. Any pooled 24-episode rate is merely the equal-weight mixture of these two fixed fixtures (worst-case descriptive Wilson interval 31.4–68.6%), not 24 different scenarios. Report actual valid denominators and missingness; do not silently substitute 24 when infrastructure invalidates attempts.

## Runtime and evidence budget

The measured Batch 01 mean projects 24 episode durations to {output['runtime_projections']['at_batch01_observed_episode_mean_h']:.2f} hours; its recorded queue occupancy per planned disposition projects {output['runtime_projections']['at_batch01_queue_occupancy_per_disposition_h']:.2f} hours. These are sensitivity calculations, because the model and task differ. The sole stock pilot occupied {pilot_duration:.2f} s of queue time, giving {output['runtime_projections']['at_single_stock_pilot_queue_wall_h']:.2f} hours if repeated 24 times; it supplies no home-family or tail-variance estimate.

Retaining the qualified pilot's 600 s model limit and 1100 s host wall limit gives 4.00 model-hours and **7.33host- hours** at all 24 caps. Adding the old residual-per-disposition sensitivity gives {output['runtime_projections']['sum_caps_plus_old_residual_sensitivity_h']:.2f} hours, still about one fifth of the prior 38.01 queue-hours. The count is 90.9% smaller. These sums exclude outer startup/cleanup, queue waits, infrastructure pauses, and analysis; the campaign protocol must independently bound those. Existing development baseline help appeared in 2.703 s (stock)/1.453 s (home), and reference completion took 60.282 s/100.859 s, one seed each. Their existing evidence supports fixed-fixture control context, not population control estimates. No extra comparator or reference campaign is required by this recommendation.

The 24 inherited 512 MiB episode caps sum 12 GiB; transcripts, boundary retention and archive overhead need separate accounting and current capacity admission. Do not treat this as a measured storage forecast or delete failures to fit it.

## Outcome and stopping rules to fix before launch

Primary: independent full-task success after recovery and conventional continuation, reported separately for both fixtures. Also retain handback, productive continuation, accepted/rejected commands, public effect evidence, timings, continuity writes, and failure mechanisms. Natural continuity is inspectable; injected restart performance remains outside this first campaign. The earlier interrupted smoke is development evidence, not a scored continuity sample.

Fix 24 slots; no success/futility early stopping, outcome-driven tuning, extension, rerun or replacement. Valid timeouts, refusals and recovery failures stay in the denominator. Declare objectively evidenced infrastructure-invalid categories and safety/integrity stop rules before any new outcome; keep every attempt. An invalid episode reduces the valid denominator rather than buying another attempt. Integrity or source-identity failure stops the campaign and leaves remaining slots explicitly not_run. Any late-lifecycle alternative must be the exact predeclared evidence rule justified by the pilot's retained 26/28 strict checks and separate lifecycle supplement, never an outcome-dependent waiver. The unchanged host's internal development-only schema must remain honestly labeled; campaign identity/scoring can be an external protocol layer without silently editing the exact 010d framework.

## Reproduce and inspect

Run `venv/Scripts/python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-001/design/size_campaign.py" --write` from the repository root. It reads completed compact metadata, verifies all selected-result queue receipt hashes and unchanged inputs, and writes this report plus [empirical-sizing.json](empirical-sizing.json). It never starts physics/model/queue work or generates seeds. The JSON contains exact numbers, outcome counts, all source SHA-256/byte sizes, interval arithmetic and sensitivity alternatives. Uncertainty calculations use the standard binomial/Wilson formulas and explicit conditional-independence assumptions; they are engineering sizing, not an external literature-based statistical claim.

Canonical inputs: [selected results](../../../Evidence/derived/evaluation-r4-administrative005-001/selected-results.json), [analysis](../../../Evidence/derived/evaluation-r4-analysis005-001/analysis.json), [analysis provenance](../../../Evidence/derived/evaluation-r4-analysis005-001/analysis-provenance.json), and each selected result's hash-bound official queue receipt. Integration source/manifest/pilot/control identities are also included in the JSON. Historical record labels, missing data, failures and administrative recovery remain unchanged.
'''
    if args.write:
        (HERE/"empirical-sizing.json").write_text(json.dumps(output, indent=2)+"\n", encoding="utf-8")
        (HERE/"README.md").write_text(report, encoding="utf-8")
    print(json.dumps({"source_count": len(SOURCES), "inputs_unchanged": True,
        "recommended_attempts": 24, "measured_episode_hours": measured["sum_s"]/3600,
        "queue_occupancy_hours": queue_sum/3600, "written": args.write}, indent=2))


if __name__ == "__main__":
    main()
