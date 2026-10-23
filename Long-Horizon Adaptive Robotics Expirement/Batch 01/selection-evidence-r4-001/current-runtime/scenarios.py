"""Versioned public orders and protected scenario-event bookkeeping.

This service runs with the supervisor/evaluator and survives candidate restarts.
Only ``order`` and ``events`` may be delivered to candidates. ``exposures`` and
``private_config`` are protected evidence. No entropy, simulator, model, external
API or compute queue is used here; every variation comes from supplied inputs.

The extended order creates a later A-reuse opportunity. It does not force a
physical sequence: anticipatory processing and finite-buffer management remain
legitimate candidate choices. Actual insert changes must be measured separately.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random


SCHEMA_VERSION = "robot-scenario-orders-1.0"
SCENARIOS = ("nominal", "order_change", "restart", "mixed")
PART_COUNTS = (3, 6, 10)
REROUTE_TIME_S = 40.0
LATE_RELEASE_FALLBACK_S = 420.0
LATE_RELEASE_DISTINCT_B_PARTS = 5


class ScenarioError(ValueError):
    pass


def _finite_nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def derive_event_seed(world_seed):
    """Deterministic domain separation, not generation of a new random seed.

    An operator may map a protected world's seed into this separate event stream.
    Layout/model/noise seed handling stays with their independent services.
    Counterpart cases should provide the same world/event seed.
    """
    if type(world_seed) is not int or world_seed < 0:
        raise ScenarioError("A supplied nonnegative integer world seed is required")
    digest = hashlib.sha256(_canonical({"domain": "batch01-order-events-v1", "world_seed": world_seed})).digest()
    return int.from_bytes(digest[:8], "big")


def public_rules():
    """Freeze this public rule object with the executable and private parameters."""
    return {
        "schema_version": SCHEMA_VERSION,
        "short": {"parts": 3, "initial_A": 2, "initial_B": 1},
        "standard": {"parts": 6, "initial_A": 3, "initial_B": 3},
        "extended": {"parts": 10, "stock_A": 5, "stock_B": 5,
                     "initial_A": 2, "initial_B": 5, "late_A": 3,
                     "release_after_distinct_completed_B_parts": LATE_RELEASE_DISTINCT_B_PARTS,
                     "default_fallback_s": LATE_RELEASE_FALLBACK_S,
                     "rework": "one A part is privately designated for a single rework response; actual exposure must be measured"},
        "order_change_and_mixed": {"default_reroute_time_s": REROUTE_TIME_S, "B_destination": "tray3",
                                   "late_A_destination_after_reroute": "tray2"},
        "nominal_and_restart_destinations": {"initial_A": "tray1", "initial_B": "tray2", "late_A": "tray3"},
        "rework_allowance_per_part": 1,
        "timing": "40s/420s defaults; any explicit parameter change must be frozen before scoring; this service does not jitter clocks",
        "ordering": "if a poll exposes both events together, B reroute is applied first; every mutation gets a new version",
        "independence": "the protected event seed selects the rework identity and is not a layout, policy or sensor-noise seed",
        "acceptance": "order.closed only after expected order events resolve; restart/intervention acceptance gates remain separate",
        "sequence_limit": "late A is a reuse opportunity, not a guaranteed second insert change; preprocessing is permitted",
    }


def _stock_registry(n, stock_ids):
    if stock_ids is None:
        entries = [(f'{"A" if i % 2 == 0 else "B"}{i + 1}', "A" if i % 2 == 0 else "B") for i in range(n)]
    elif isinstance(stock_ids, dict):
        entries = []
        for part_id, metadata in stock_ids.items():
            if isinstance(metadata, str):
                entries.append((part_id, metadata))
            elif isinstance(metadata, dict) and metadata.get("kind", "part") == "part":
                entries.append((part_id, metadata.get("family")))
    elif isinstance(stock_ids, (list, tuple)):
        entries = []
        for item in stock_ids:
            if isinstance(item, str):
                entries.append((item, item[:1]))
            elif isinstance(item, dict) and item.get("kind", "part") == "part":
                entries.append((item.get("id"), item.get("family")))
            else:
                raise ScenarioError("Invalid stock registry entry")
    else:
        raise ScenarioError("Stock must be an explicit part registry or sequence")
    if (len(entries) != n
            or any(not isinstance(name, str) or not name or family not in ("A", "B") for name, family in entries)
            or len({name for name, _ in entries}) != n):
        raise ScenarioError("Stock must contain exactly n distinct A/B part identities")
    registry = dict(entries)
    if sum(f == "A" for f in registry.values()) != (n + 1) // 2 or sum(f == "B" for f in registry.values()) != n // 2:
        raise ScenarioError("Stock family totals do not match the released job")
    return registry


def _requirement(item_id, family, count, tray):
    return {"order_item_id": item_id, "family": family, "recipe": family,
            "count": count, "tray": tray, "max_rework_cycles": 1}


def _text(order):
    lines = [f"Order version {order['version']}."]
    for row in order["requirements"]:
        noun = "part" if row["count"] == 1 else "parts"
        lines.append(f"Process and inspect {row['count']} distinct {row['family']} {noun} using recipe {row['recipe']}; deliver them to {row['tray']}.")
    lines.append("One rework cycle per part is permitted only after an inspection requests rework.")
    lines.append("The order stream is closed." if order["closed"] else "The order stream remains open; amendments may follow.")
    return " ".join(lines)


class ScenarioService:
    """Supervisor-owned scenario state. It must outlive candidate processes.

    API::

        service = ScenarioService(10, 'mixed', event_seed=supplied_seed,
                                  stock_ids=cell.registry)
        order = service.initial_order()
        private = service.private_config()  # evaluator only; do NOT send to candidate
        update = service.advance(sim_elapsed, completed_cycle_records)
        order = update['order']

    ``protected_completed_cycles`` accepts a list/tuple of protected cycle
    records, or Cell's protected ``truth`` mapping whose values contain
    ``cycle_history`` lists. Only accepted, completed records count. The B
    milestone counts distinct known part IDs, so five cycles on one reworked
    part cannot trigger it. Completed-at timestamps are retained by the caller;
    this service does not confuse absolute simulator time with elapsed time.
    """

    def __init__(self, n, scenario="nominal", *, event_seed=0, stock_ids=None, event_params=None):
        if type(n) is not int or n not in PART_COUNTS:
            raise ScenarioError("Supported released part counts are 3, 6 and 10")
        if scenario not in SCENARIOS:
            raise ScenarioError("Unknown released scenario")
        if type(event_seed) is not int or event_seed < 0:
            raise ScenarioError("event_seed must be a supplied nonnegative integer")
        self.n, self.scenario = n, scenario
        self._stock = _stock_registry(n, stock_ids)
        self._event_seed = event_seed
        params = dict(event_params or {})
        if set(params) - {"reroute_time_s", "late_release_fallback_s", "rework_part_id"}:
            raise ScenarioError("Unknown event parameter; revise/freeze the public rules before extending them")
        self._reroute_time = params.get("reroute_time_s", REROUTE_TIME_S)
        self._fallback_time = params.get("late_release_fallback_s", LATE_RELEASE_FALLBACK_S)
        if not _finite_nonnegative(self._reroute_time) or not _finite_nonnegative(self._fallback_time):
            raise ScenarioError("Event times must be finite and nonnegative")
        self._needs_reroute = scenario in ("order_change", "mixed")
        self._needs_late_a = n == 10
        self._resolved = set()
        self._last_elapsed = None
        self._completed_b = set()
        self._milestone_first_observed_at = None
        self._exposures = []
        self._public_events = []
        if self._needs_late_a:
            a_ids = sorted(name for name, family in self._stock.items() if family == "A")
            self._rework_part = params.get("rework_part_id", random.Random(event_seed).choice(a_ids))
            if self._rework_part not in a_ids:
                raise ScenarioError("Extended rework target must be one of the five actual A parts")
        else:
            if params.get("rework_part_id") is not None:
                raise ScenarioError("The single scripted rework target belongs only to the extended job")
            self._rework_part = None
        initial_a, initial_b = (2, 5) if n == 10 else ((n + 1) // 2, n // 2)
        self._order = {"version": 1, "closed": not (self._needs_reroute or self._needs_late_a),
                       "requirements": [_requirement("initial-A", "A", initial_a, "tray1"),
                                        _requirement("initial-B", "B", initial_b, "tray2")]}
        self._order["text"] = _text(self._order)
        self._initial = copy.deepcopy(self._order)

    def initial_order(self):
        return copy.deepcopy(self._initial)

    @property
    def order(self):
        return copy.deepcopy(self._order)

    def private_config(self):
        """Protected manifest/config only. This is NOT a public observation."""
        return {
            "schema_version": SCHEMA_VERSION, "audience": "evaluator/operator only",
            "scenario": self.scenario, "part_count": self.n, "event_seed": self._event_seed,
            "stock": dict(self._stock), "reroute_time_s": self._reroute_time if self._needs_reroute else None,
            "late_release_fallback_s": self._fallback_time if self._needs_late_a else None,
            "late_release_distinct_B_parts": LATE_RELEASE_DISTINCT_B_PARTS if self._needs_late_a else None,
            "rework_part_id": self._rework_part, "rework_once": self._needs_late_a,
            "required_order_events": self._required_events(),
            "public_rules_sha256": hashlib.sha256(_canonical(public_rules())).hexdigest(),
            "implementation_limit": "inspection service must implement and record the one rework; this service does not modify part outcomes",
        }

    def _required_events(self):
        return (["reroute-B"] if self._needs_reroute else []) + (["release-late-A"] if self._needs_late_a else [])

    def _events_resolved(self):
        return set(self._required_events()).issubset(self._resolved)

    def _cycle_records(self, supplied):
        if isinstance(supplied, dict):
            records = []
            for state in supplied.values():
                if not isinstance(state, dict) or not isinstance(state.get("cycle_history", []), list):
                    raise ScenarioError("Protected truth entries must contain cycle-history lists")
                records.extend(state.get("cycle_history", []))
            return records
        if isinstance(supplied, (list, tuple)):
            return supplied
        raise ScenarioError("Distinct-part milestone requires cycle records, not a scalar count")

    def _observe_cycles(self, supplied, elapsed):
        observed_b = set(self._completed_b)
        for cycle in self._cycle_records(supplied):
            if not isinstance(cycle, dict):
                raise ScenarioError("Malformed protected cycle record")
            if cycle.get("accepted") is not True or cycle.get("completed") is not True:
                continue
            part_id = cycle.get("part_id")
            if part_id not in self._stock:
                raise ScenarioError("Completed cycle names an unknown stock identity")
            if cycle.get("recipe") != self._stock[part_id]:
                raise ScenarioError("Completed process recipe contradicts the fixed family interlock")
            if self._stock[part_id] == "B":
                observed_b.add(part_id)
        self._completed_b = observed_b
        if len(self._completed_b) >= LATE_RELEASE_DISTINCT_B_PARTS and self._milestone_first_observed_at is None:
            self._milestone_first_observed_at = elapsed

    def _commit(self, key, elapsed, exposure):
        parent_version = self._order["version"]
        self._resolved.add(key)
        self._order["version"] += 1
        self._order["closed"] = self._events_resolved()
        self._order["text"] = _text(self._order)
        event = {"event_id": "order-event-" + key, "event_type": "order_amendment", "sim_elapsed_s": elapsed,
                 "parent_order_version": parent_version, "order_version": self._order["version"],
                 "order": copy.deepcopy(self._order)}
        protected = {
            "event_id": event["event_id"], "audience": "evaluator/operator only", "sim_elapsed_s": elapsed,
            "order_version": self._order["version"], "order_sha256": hashlib.sha256(_canonical(self._order)).hexdigest(),
            **exposure,
        }
        self._public_events.append(event)
        self._exposures.append(protected)
        return event, protected

    def advance(self, sim_elapsed, protected_completed_cycles):
        if not _finite_nonnegative(sim_elapsed):
            raise ScenarioError("Elapsed simulation time must be finite and nonnegative")
        elapsed = float(sim_elapsed)
        if self._last_elapsed is not None and elapsed < self._last_elapsed:
            raise ScenarioError("Scenario clock cannot move backward on candidate restart")
        self._observe_cycles(protected_completed_cycles, elapsed)
        self._last_elapsed = elapsed
        events, exposures = [], []
        if self._needs_reroute and "reroute-B" not in self._resolved and elapsed >= self._reroute_time:
            for row in self._order["requirements"]:
                if row["order_item_id"] == "initial-B":
                    row["tray"] = "tray3"
                elif row["order_item_id"] == "late-A":
                    # If unusually fast B work already released late A, keep
                    # the later public amendment consistent rather than giving
                    # A and B the same final tray or forcing a hidden sequence.
                    row["tray"] = "tray2"
            event, exposure = self._commit("reroute-B", elapsed, {
                "trigger": "fixed_elapsed_order_change", "fallback_used": False,
                "scheduled_elapsed_s": float(self._reroute_time), "delivery_delay_s": elapsed - self._reroute_time,
            })
            events.append(event); exposures.append(exposure)
        milestone = len(self._completed_b) >= LATE_RELEASE_DISTINCT_B_PARTS
        fallback = elapsed >= self._fallback_time
        if self._needs_late_a and "release-late-A" not in self._resolved and (milestone or fallback):
            destination = "tray2" if "reroute-B" in self._resolved else "tray3"
            self._order["requirements"].append(_requirement("late-A", "A", 3, destination))
            used_fallback = fallback and (self._milestone_first_observed_at is None or self._milestone_first_observed_at > self._fallback_time)
            event, exposure = self._commit("release-late-A", elapsed, {
                "trigger": "fixed_deadline_fallback" if used_fallback else "five_distinct_completed_B_parts",
                "fallback_used": used_fallback, "fallback_elapsed_s": float(self._fallback_time),
                "milestone_satisfied": milestone, "milestone_first_observed_at_s": self._milestone_first_observed_at,
                "distinct_completed_B_count": len(self._completed_b), "distinct_completed_B_ids": sorted(self._completed_b),
                "delivery_delay_after_fallback_s": max(0., elapsed - self._fallback_time) if used_fallback else None,
                "reuse_claim": "later A work opportunity; actual insert changes depend on candidate behavior",
            })
            events.append(event); exposures.append(exposure)
        return {
            "order": self.order, "events": copy.deepcopy(events), "exposures": copy.deepcopy(exposures),
            "changed": bool(events), "order_events_resolved": self._events_resolved(),
            "acceptance_limit": "order events only; supervisor must also resolve required restart/intervention opportunities",
        }

    def protected_history(self):
        return copy.deepcopy(self._exposures)

    def public_history(self):
        return copy.deepcopy(self._public_events)


def initial_order(n, scenario="nominal"):
    """Convenience public initial order. Keep a ScenarioService to advance it."""
    return ScenarioService(n, scenario).initial_order()
