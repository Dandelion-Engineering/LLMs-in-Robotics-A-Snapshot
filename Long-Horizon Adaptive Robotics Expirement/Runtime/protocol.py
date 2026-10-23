"""Frozen-release matrix construction and evidence-based analysis.

No simulator or model is called here. ``describe`` contains no held-out seeds.
Only an explicit, readiness-gated ``create`` command creates concealed seeds.
Analysis never changes missing/unrun outcomes into failures or measured zeros.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import re
import secrets


SCHEMA_VERSION = "robot-evaluation-release-1.0"
ARCHITECTURES = ("baseline", "A1", "A2", "A3")
LLM_ARCHITECTURES = ("A1", "A2", "A3")
HORIZONS = {"short": {"parts": 3, "cap_s": 300},
            "standard": {"parts": 6, "cap_s": 600},
            "extended": {"parts": 10, "cap_s": 900}}
GROUPS = ("nominal", "physical-or-order-change", "continuity-or-mixed")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
RELEASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
TERMINAL = {"completed", "failed", "timed_out", "aborted"}
REQUIRED_GATES = (
    "physical_workcell", "public_perception", "independent_evaluator", "conventional_baseline",
    "candidate_implementations", "model_and_terms", "isolation", "timing_and_resources",
    "evidence_retention", "disturbance_admissibility", "equal_development_opportunity",
)


class ProtocolError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protocol_sha256():
    """Exact source identity; the freeze must match this implementation."""
    return sha256_file(__file__)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _load(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"),
                           parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ProtocolError("Cannot read valid JSON from " + str(path)) from exc
    if not isinstance(value, dict):
        raise ProtocolError("Expected JSON object: " + str(path))
    return value


def public_cases():
    """24 case definitions; no hidden seed or future disturbance boundary."""
    patterns = {
        "short": ["nominal", "nominal", "nominal", "order_change", "order_change", "restart", "mixed", "mixed"],
        "standard": ["nominal", "nominal", "order_change", "order_change", "order_change", "restart", "restart", "mixed"],
        "extended": ["nominal", "nominal", "nominal", "order_change", "order_change", "order_change", "restart", "mixed"],
    }
    counterparts = {"C01": "C06", "C09": "C14", "C10": "C15", "C17": "C23"}
    inverse = {v: k for k, v in counterparts.items()}
    cases = []
    for horizon, scenarios in patterns.items():
        for scenario in scenarios:
            case_id = "C" + str(len(cases) + 1).zfill(2)
            group = "nominal" if scenario == "nominal" else (
                "physical-or-order-change" if scenario == "order_change" else "continuity-or-mixed")
            counterpart = counterparts.get(case_id, inverse.get(case_id))
            family = min(case_id, counterpart) if counterpart else case_id
            cases.append({
                "case_id": case_id, "scenario_id": case_id, "scenario_family_id": "F" + family[1:],
                "horizon": horizon, "disturbance_group": group, "scenario": scenario,
                "parts": HORIZONS[horizon]["parts"], "cap_s": HORIZONS[horizon]["cap_s"],
                "counterpart_case_id": counterpart,
                "uninterrupted_counterpart": case_id in counterparts,
                "ablation_included": group == "continuity-or-mixed" or case_id in counterparts,
            })
    return cases


def public_run_slots(release_id="planned"):
    """Public run identities and stratification, without randomization/seeds."""
    if not RELEASE_RE.fullmatch(release_id):
        raise ProtocolError("release_id must be a short filesystem-safe identifier")
    slots = []
    for case in public_cases():
        for replicate in (1, 2):
            block = f"{release_id}-{case['case_id']}-rep{replicate}"
            for architecture in ARCHITECTURES:
                conditions = ["persistent"]
                if architecture in LLM_ARCHITECTURES and case["ablation_included"]:
                    conditions.append("no-persistence")
                for condition in conditions:
                    slots.append({
                        "schema_version": SCHEMA_VERSION, "run_id": f"{block}-{architecture}-{condition}",
                        "release_id": release_id, "protocol_id": release_id, "stage": "evaluation",
                        **case, "paired_block_id": block, "replicate": replicate,
                        "architecture": architecture, "condition": condition,
                    })
    validate_matrix(slots)
    return slots


def validate_matrix(manifests):
    """Refuse silent subset, duplicate identity, wrong pairing or altered design."""
    if len(manifests) != 264:
        raise ProtocolError("The complete release must contain exactly 264 runs")
    expected_cases = {c["case_id"]: c for c in public_cases()}
    identities, ids, releases = set(), set(), set()
    grouped = defaultdict(list)
    for row in manifests:
        if not isinstance(row, dict):
            raise ProtocolError("Run manifest must be an object")
        try:
            case_id, architecture, condition, replicate = (row[k] for k in ("case_id", "architecture", "condition", "replicate"))
            identity = case_id, architecture, condition, replicate
            run_id, release_id = row["run_id"], row["release_id"]
        except KeyError as exc:
            raise ProtocolError("Run identity field is missing") from exc
        if identity in identities or run_id in ids:
            raise ProtocolError("Duplicate run identity")
        identities.add(identity); ids.add(run_id); releases.add(release_id)
        if case_id not in expected_cases or architecture not in ARCHITECTURES or type(replicate) is not int or replicate not in (1, 2):
            raise ProtocolError("Unknown case, architecture or replicate")
        case = expected_cases[case_id]
        if condition not in ("persistent", "no-persistence"):
            raise ProtocolError("Unknown persistence condition")
        if condition == "no-persistence" and (architecture == "baseline" or not case["ablation_included"]):
            raise ProtocolError("Unplanned ablation or stateless baseline")
        for key, value in case.items():
            if row.get(key) != value:
                raise ProtocolError("Case design mismatch: " + case_id + "/" + key)
        expected_block = f"{release_id}-{case_id}-rep{replicate}"
        if row.get("paired_block_id") != expected_block or row.get("stage") != "evaluation":
            raise ProtocolError("Invalid paired block or stage")
        grouped[(case_id, replicate)].append(row)
    if len(releases) != 1:
        raise ProtocolError("Runs from different frozen releases cannot form one matrix")
    main = [r for r in manifests if r["condition"] == "persistent"]
    controls = [r for r in manifests if r["condition"] == "no-persistence"]
    if len(main) != 192 or len(controls) != 72:
        raise ProtocolError("Expected 192 main runs and 72 persistence controls")
    for architecture in ARCHITECTURES:
        chosen = [r for r in main if r["architecture"] == architecture]
        if len(chosen) != 48 or Counter(r["horizon"] for r in chosen) != Counter({h: 16 for h in HORIZONS}):
            raise ProtocolError("Entrant horizon pairing is incomplete")
        if Counter(r["disturbance_group"] for r in chosen) != Counter({g: 16 for g in GROUPS}):
            raise ProtocolError("Entrant disturbance pairing is incomplete")
    for architecture in LLM_ARCHITECTURES:
        if sum(r["architecture"] == architecture for r in controls) != 24:
            raise ProtocolError("Entrant ablation matrix is incomplete")
    # If concealed seeds are present, test actual equality and independence.
    have_seeds = ["seeds" in r for r in manifests]
    if any(have_seeds) and not all(have_seeds):
        raise ProtocolError("Only part of the release contains seed manifests")
    if all(have_seeds):
        family_world = {}
        family_rep = {}
        for row in manifests:
            seeds = row["seeds"]
            if set(seeds) != {"world_seed", "layout_seed", "policy_seed", "noise_seed"}:
                raise ProtocolError("Seed fields differ from frozen protocol")
            if any(type(v) is not int or v < 0 for v in seeds.values()):
                raise ProtocolError("Invalid seed value")
            family = row["scenario_family_id"]
            world_pair = seeds["world_seed"], seeds["layout_seed"]
            policy_pair = seeds["policy_seed"], seeds["noise_seed"]
            if family in family_world and family_world[family] != world_pair:
                raise ProtocolError("World/layout differs across entrants, replicates or exact counterparts")
            family_world[family] = world_pair
            key = family, row["replicate"]
            if key in family_rep and family_rep[key] != policy_pair:
                raise ProtocolError("Policy/noise seed differs inside a paired replicate")
            family_rep[key] = policy_pair
        for family in family_world:
            one, two = family_rep[(family, 1)], family_rep[(family, 2)]
            if one[0] == two[0] or one[1] == two[1]:
                raise ProtocolError("The two policy/noise replicates must have different seeds")
    return {"runs": 264, "main_runs": 192, "ablation_runs": 72, "case_units": 24,
            "scenario_families": 20, "paired_blocks": 48}


def describe():
    slots = public_run_slots()
    return {
        "schema_version": SCHEMA_VERSION, "status": "public plan; no evaluation seeds generated",
        "protocol_sha256": protocol_sha256(), "counts": validate_matrix(slots), "cases": public_cases(),
        "cross_tab": {h: dict(Counter(c["disturbance_group"] for c in public_cases() if c["horizon"] == h)) for h in HORIZONS},
        "planned_wall_cap_s": sum(r["cap_s"] for r in slots),
        "ordinary_evidence_allowance_gib_at_2_per_run": 2 * len(slots),
        "primary_bootstrap_cluster": "scenario_family_id; keeps counterpart cases and both replicates together",
    }


def validate_release_gates(freeze_path, readiness_path):
    freeze, readiness = _load(freeze_path), _load(readiness_path)
    release_id = freeze.get("release_id")
    if not isinstance(release_id, str) or not RELEASE_RE.fullmatch(release_id):
        raise ProtocolError("Freeze lacks a valid release_id")
    for field in ("code_sha256", "environment_sha256", "model_sha256", "protocol_sha256"):
        value = freeze.get(field)
        if not isinstance(value, str) or not HASH_RE.fullmatch(value):
            raise ProtocolError("Freeze lacks a valid " + field)
    if freeze["protocol_sha256"] != protocol_sha256():
        raise ProtocolError("The generator source does not match the frozen protocol hash")
    try:
        frozen_at = datetime.fromisoformat(freeze["frozen_at"].replace("Z", "+00:00"))
        if frozen_at.utcoffset() is None:
            raise ValueError("timezone required")
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError("Freeze requires a timezone-qualified frozen_at") from exc
    if not isinstance(freeze.get("selection_criteria"), str) or not freeze["selection_criteria"].strip():
        raise ProtocolError("Freeze requires predeclared selection_criteria")
    if type(freeze.get("maximum_retries")) is not int or freeze["maximum_retries"] != 0:
        raise ProtocolError("Scored policy attempts are once-only; infrastructure block reruns receive new manifests")
    if readiness.get("scored_ready") is not True:
        raise ProtocolError("Readiness has not explicitly established scored_ready: true")
    if readiness.get("release_id") != release_id or readiness.get("freeze_sha256") != sha256_file(freeze_path):
        raise ProtocolError("Readiness is not bound to this exact frozen release")
    gates = readiness.get("gates")
    if not isinstance(gates, dict) or any(gates.get(gate) is not True for gate in REQUIRED_GATES):
        raise ProtocolError("One or more required readiness gates have not passed")
    references = readiness.get("evidence_refs")
    if not isinstance(references, list) or not references:
        raise ProtocolError("Readiness requires evidence references; declarations alone are insufficient")
    for ref in references:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not HASH_RE.fullmatch(str(ref.get("sha256", ""))):
            raise ProtocolError("Malformed readiness evidence reference")
        path = Path(ref["path"])
        if not path.is_absolute():
            path = Path(readiness_path).resolve().parent / path
        if not path.is_file() or sha256_file(path) != ref["sha256"]:
            raise ProtocolError("Readiness evidence is missing or changed: " + ref["path"])
    # Explicit class mode must have prior byte-verified evidence before seed creation.
    from restart_calibration_loader import CalibrationInputError, load_restart_qualification
    try:load_restart_qualification(freeze, freeze_path)
    except CalibrationInputError as exc:raise ProtocolError(str(exc)) from exc
    return freeze, readiness


def _entropy(bits):
    return secrets.randbits(bits)


def _unique_seed(bits, used):
    for _ in range(100):
        value = _entropy(bits)
        if value not in used:
            used.add(value)
            return value
    raise ProtocolError("Seed source repeated values unexpectedly")


def _write_json(path, value):
    # Exclusive creation prevents overwriting an already published manifest.
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def create_release(release_dir, freeze_path, readiness_path):
    """Explicit caller action after gates; never called by describe or analysis."""
    freeze, _ = validate_release_gates(freeze_path, readiness_path)
    release_dir = Path(release_dir).resolve()
    if release_dir.exists() or not release_dir.parent.is_dir():
        raise ProtocolError("Select a new release directory beneath an existing operator-controlled parent")
    for supplied in (freeze_path, readiness_path):
        if Path(supplied).resolve().is_relative_to(release_dir):
            raise ProtocolError("Input evidence cannot be created inside a not-yet-existing release")
    slots = public_run_slots(freeze["release_id"])
    used_world, used_layout, used_policy, used_noise = set(), set(), set(), set()
    family_seeds = {}
    for family in sorted({r["scenario_family_id"] for r in slots}):
        family_seeds[family] = {
            "world_seed": _unique_seed(63, used_world), "layout_seed": _unique_seed(63, used_layout),
            "replicates": {rep: {"policy_seed": _unique_seed(31, used_policy), "noise_seed": _unique_seed(63, used_noise)} for rep in (1, 2)},
        }
    blocks = defaultdict(list)
    for row in slots:
        values = family_seeds[row["scenario_family_id"]]
        row["seeds"] = {"world_seed": values["world_seed"], "layout_seed": values["layout_seed"],
                        **values["replicates"][row["replicate"]]}
        row["freeze_sha256"] = sha256_file(freeze_path)
        row["readiness_sha256"] = sha256_file(readiness_path)
        row["artifact_hashes"] = {k: freeze[k] for k in ("code_sha256", "environment_sha256", "model_sha256", "protocol_sha256")}
        blocks[row["paired_block_id"]].append(row)
    validate_matrix(slots)
    # Randomize blocks and entrants/conditions within blocks. All seed material
    # and schedules remain outside candidate-visible mounts.
    rng = random.Random(_entropy(256))
    block_ids = sorted(blocks)
    rng.shuffle(block_ids)
    ordered = []
    for block_id in block_ids:
        rng.shuffle(blocks[block_id])
        ordered.extend(blocks[block_id])
    release_dir.mkdir()
    (release_dir / "runs").mkdir()
    records = []
    for index, row in enumerate(ordered, 1):
        row["scheduled_index"] = index
        relative = "runs/" + row["run_id"] + ".json"
        path = release_dir / relative
        _write_json(path, row)
        records.append({"run_id": row["run_id"], "path": relative, "sha256": sha256_file(path), "scheduled_index": index})
    release = {
        "schema_version": SCHEMA_VERSION, "release_id": freeze["release_id"], "created_at": _utc(),
        "freeze_manifest": {"path": str(Path(freeze_path).resolve()), "sha256": sha256_file(freeze_path)},
        "readiness": {"path": str(Path(readiness_path).resolve()), "sha256": sha256_file(readiness_path)},
        "counts": validate_matrix(ordered), "manifest_refs": records,
        "confidentiality": "operator/evaluator only; path convention does not establish OS isolation",
    }
    _write_json(release_dir / "release.json", release)
    # Return only identities/counts: never print seeds into ordinary tool output.
    return {"release_id": freeze["release_id"], "release_dir": str(release_dir), "counts": release["counts"],
            "release_sha256": sha256_file(release_dir / "release.json")}


def load_release(release_dir):
    root = Path(release_dir).resolve()
    release = _load(root / "release.json")
    manifests = []
    for ref in release.get("manifest_refs", []):
        path = (root / ref["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha256_file(path) != ref["sha256"]:
            raise ProtocolError("Manifest reference escaped, is missing or has changed")
        manifests.append(_load(path))
    validate_matrix(manifests)
    return manifests


def _success(result):
    independent = result.get("independent_outcome")
    if isinstance(independent, dict) and type(independent.get("success")) is bool:
        return independent["success"]
    if type(result.get("task_success")) is bool:
        return result["task_success"]
    if result.get("outcome") == "success":
        return True
    if result.get("outcome") in ("failure", "partial"):
        return False
    return None


def _infra_invalid(result):
    return (result.get("infrastructure_invalid") is True or result.get("validity") == "infrastructure_invalid"
            or (result.get("validity") == "invalid" and result.get("invalidity_class") == "infrastructure"))


def _numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def cluster_bootstrap(rows, *, draws=2000, seed=0, confidence=0.95, cluster_key="scenario_family_id"):
    """Resample all observed paired rows in each scenario-family cluster.

    Both policy/noise replicates and exact interrupted/uninterrupted counterpart
    cases remain together. This respects 20 matched families, not a false 48-run
    independence claim. An optional case_id diagnostic exposes the difference.
    """
    if type(draws) is not int or draws < 100 or not 0 < confidence < 1:
        raise ProtocolError("Bootstrap requires at least 100 draws and a valid confidence level")
    if cluster_key not in ("scenario_family_id", "case_id"):
        raise ProtocolError("Unsupported resampling unit")
    clusters = defaultdict(list)
    for row in rows:
        if not _numeric(abs(row["difference"])):
            raise ProtocolError("Nonfinite paired difference")
        clusters[row[cluster_key]].append(row["difference"])
    if len(clusters) < 2:
        return {"interval": None, "confidence": confidence, "cluster_key": cluster_key,
                "cluster_count": len(clusters), "draws": 0, "seed": seed,
                "missing_reason": "fewer than two observed clusters"}
    values = list(clusters.values())
    rng, estimates = random.Random(seed), []
    for _ in range(draws):
        selected = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(sum(sum(cluster) for cluster in selected) / sum(map(len, selected)))
    tail = (1.0 - confidence) / 2
    return {"interval": [_percentile(estimates, tail), _percentile(estimates, 1 - tail)],
            "confidence": confidence, "cluster_key": cluster_key, "cluster_count": len(clusters),
            "draws": draws, "seed": seed, "missing_reason": None}


def _pair_summary(rows, *, draws, seed):
    table = {"both_success": 0, "left_only": 0, "right_only": 0, "both_failure": 0}
    for row in rows:
        key = "both_success" if row["left_success"] and row["right_success"] else (
            "left_only" if row["left_success"] else "right_only" if row["right_success"] else "both_failure")
        table[key] += 1
    count = len(rows)
    return {
        "paired_table": table, "paired_run_count": count,
        "case_units": len({r["case_id"] for r in rows}),
        "scenario_families": len({r["scenario_family_id"] for r in rows}),
        "left_success_count": table["both_success"] + table["left_only"],
        "right_success_count": table["both_success"] + table["right_only"],
        "left_success_rate": (table["both_success"] + table["left_only"]) / count if count else None,
        "right_success_rate": (table["both_success"] + table["right_only"]) / count if count else None,
        "paired_success_difference": sum(r["difference"] for r in rows) / count if count else None,
        "bootstrap": cluster_bootstrap(rows, draws=draws, seed=seed),
        "missing_reason": None if count else "no jointly observed valid terminal outcomes",
    }


def analyze(manifests, results, *, bootstrap_draws=2000, analysis_seed=0):
    """Analyze terminal independent outcomes from one exact planned release.

    Results must contain one selected record per run after explicit resolution
    of any append-only supersession history. Duplicate results are an error.
    Invalid infrastructure excludes the entire case/replicate paired block,
    including all entrants and persistence conditions. No run is silently rerun.
    """
    validate_matrix(manifests)
    by_id = {r["run_id"]: r for r in manifests}
    by_result = {}
    for result in results:
        run_id = result.get("run_id")
        if run_id not in by_id or run_id in by_result:
            raise ProtocolError("Unknown or duplicate result run_id; resolve supersession explicitly")
        by_result[run_id] = result
    invalid_blocks = defaultdict(list)
    for run_id, result in by_result.items():
        if _infra_invalid(result):
            invalid_blocks[by_id[run_id]["paired_block_id"]].append({
                "run_id": run_id, "reason": result.get("validity_reason", result.get("reason", "unspecified infrastructure defect"))})
    disposition, success, times = {}, {}, []
    for run_id, manifest in by_id.items():
        result = by_result.get(run_id)
        if manifest["paired_block_id"] in invalid_blocks:
            reason = "paired_block_infrastructure_invalid"
        elif result is None or result.get("execution_status") == "not_run":
            reason = "unrun"
        elif result.get("execution_status") not in TERMINAL:
            reason = "nonterminal"
        elif result.get("validity") != "valid":
            reason = "unknown_validity" if result.get("validity") in (None, "unknown") else "invalid_result"
        elif _success(result) is None:
            reason = "missing_outcome"
        else:
            reason = "eligible"
            success[run_id] = _success(result)
            completion = result.get("completion_time_s")
            duration = result.get("wall_duration_s")
            completed_time = completion if success[run_id] and _numeric(completion) else None
            measured_duration = duration if _numeric(duration) else None
            times.append({
                "run_id": run_id, "architecture": manifest["architecture"], "condition": manifest["condition"],
                "case_id": manifest["case_id"], "replicate": manifest["replicate"], "cap_s": manifest["cap_s"],
                "task_success": success[run_id], "completion_time_s": completed_time,
                "observed_wall_duration_s": measured_duration, "right_censored": not success[run_id],
                "observed_censor_time_s": min(measured_duration, manifest["cap_s"]) if not success[run_id] and measured_duration is not None else None,
                "plot_time_s": completed_time if success[run_id] else manifest["cap_s"],
                "plot_basis": "measured_completion" if completed_time is not None else (
                    "missing_success_time" if success[run_id] else "failed_run_at_protocol_cap_not_measured_completion"),
                "time_missing_reason": "success time was not measured" if success[run_id] and completed_time is None else (
                    "actual exposure duration was not measured" if measured_duration is None else None),
            })
        disposition[run_id] = reason
    comparisons = []
    specs = [((a, "persistent"), (b, "persistent")) for a, b in itertools.combinations(ARCHITECTURES, 2)]
    specs += [((a, "persistent"), (a, "no-persistence")) for a in LLM_ARCHITECTURES]
    identities = {(r["case_id"], r["replicate"], r["architecture"], r["condition"]): r for r in manifests}
    for left, right in specs:
        name = "/".join(left) + " minus " + "/".join(right)
        rows, unavailable = [], []
        for case in public_cases():
            for replicate in (1, 2):
                a = identities.get((case["case_id"], replicate, *left))
                b = identities.get((case["case_id"], replicate, *right))
                if a is None or b is None:
                    continue  # Outside predeclared ablation subset, not missing data.
                if disposition[a["run_id"]] != "eligible" or disposition[b["run_id"]] != "eligible":
                    unavailable.append({"case_id": case["case_id"], "replicate": replicate,
                                        "left_run_id": a["run_id"], "left_reason": disposition[a["run_id"]],
                                        "right_run_id": b["run_id"], "right_reason": disposition[b["run_id"]]})
                    continue
                sa, sb = success[a["run_id"]], success[b["run_id"]]
                rows.append({"case_id": case["case_id"], "scenario_family_id": case["scenario_family_id"],
                             "horizon": case["horizon"], "disturbance_group": case["disturbance_group"],
                             "replicate": replicate, "left_run_id": a["run_id"], "right_run_id": b["run_id"],
                             "left_success": sa, "right_success": sb, "difference": int(sa) - int(sb)})
        pair_seed = analysis_seed ^ int(hashlib.sha256(name.encode()).hexdigest()[:12], 16)
        summary = _pair_summary(rows, draws=bootstrap_draws, seed=pair_seed)
        strata = {}
        for key, values in (("horizon", HORIZONS), ("disturbance_group", GROUPS)):
            strata[key] = {value: _pair_summary([r for r in rows if r[key] == value], draws=bootstrap_draws,
                                               seed=pair_seed + index + 1) for index, value in enumerate(values)}
        comparisons.append({"name": name, "left": {"architecture": left[0], "condition": left[1]},
                            "right": {"architecture": right[0], "condition": right[1]}, **summary,
                            "strata": strata, "paired_rows": rows, "unavailable_pairs": unavailable})
    entrants = []
    for architecture in ARCHITECTURES:
        for condition in ("persistent", "no-persistence"):
            selected = [r for r in manifests if r["architecture"] == architecture and r["condition"] == condition]
            if not selected:
                continue
            valid = [r for r in selected if disposition[r["run_id"]] == "eligible"]
            numerator = sum(success[r["run_id"]] for r in valid)
            entrants.append({"architecture": architecture, "condition": condition, "planned_runs": len(selected),
                             "eligible_runs": len(valid), "success_count": numerator,
                             "success_rate": numerator / len(valid) if valid else None,
                             "case_units": len({r["case_id"] for r in valid}),
                             "dispositions": dict(Counter(disposition[r["run_id"]] for r in selected))})
    return {
        "schema_version": "robot-evaluation-analysis-1.0", "release_id": manifests[0]["release_id"],
        "planned_counts": validate_matrix(manifests), "result_records_supplied": len(results),
        "dispositions": dict(Counter(disposition.values())),
        "excluded_paired_blocks": [{"paired_block_id": block, "triggering_results": records} for block, records in sorted(invalid_blocks.items())],
        "entrants": entrants, "comparisons": comparisons, "time_observations": times,
        "analysis_seed": analysis_seed, "bootstrap_draws": bootstrap_draws,
        "limitations": ["Selected simulated cases do not establish population or factory reliability.",
                        "24 case units include four exact counterpart pairs: 20 scenario families are the conservative resampling unit.",
                        "Failure markers at protocol caps are a plotting convention, not measured completion times.",
                        "Infrastructure-block exclusions and missing outcomes remain visible; no unrun attempt is a failure.",
                        "Structural validation does not establish independent evaluator correctness or evidence authenticity."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("describe", help="Public matrix/counts/hash only; creates no evaluation seeds")
    create = sub.add_parser("create", help="Explicitly create concealed manifests only after readiness and freeze")
    create.add_argument("--release-dir", required=True)
    create.add_argument("--freeze-manifest", required=True)
    create.add_argument("--readiness", required=True)
    analysis = sub.add_parser("analyze", help="Read protected manifests and selected terminal result records")
    analysis.add_argument("--release-dir", required=True)
    analysis.add_argument("--results", required=True, help="JSON array of selected results or JSON object with results array")
    analysis.add_argument("--output", required=True)
    analysis.add_argument("--bootstrap-draws", type=int, default=2000)
    analysis.add_argument("--analysis-seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.command == "describe":
            value = describe()
        elif args.command == "create":
            value = create_release(args.release_dir, args.freeze_manifest, args.readiness)
        else:
            result_value = json.loads(Path(args.results).read_text(encoding="utf-8"))
            results = result_value.get("results") if isinstance(result_value, dict) else result_value
            if not isinstance(results, list):
                raise ProtocolError("Results input must contain an array")
            report = analyze(load_release(args.release_dir), results, bootstrap_draws=args.bootstrap_draws, analysis_seed=args.analysis_seed)
            _write_json(args.output, report)
            value = {"output": str(Path(args.output).resolve()), "sha256": sha256_file(args.output), "dispositions": report["dispositions"]}
    except (ProtocolError, OSError, ValueError) as exc:
        parser.exit(2, "Refused: " + str(exc) + "\n")
    print(json.dumps(value, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
