"""Read-only synthetic scheduler counterexample; no physics, queue or run data.

Mocks only candidate persistence and directory existence/creation. All policy
decisions use the actual current candidates.py implementation and public-shaped
synthetic packets. Nothing is written when this script executes.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

RUNTIME = Path(__file__).resolve().parent.parent / "Runtime"
sys.path.insert(0, str(RUNTIME))
from candidates import Candidate


def demonstrate():
    code = RUNTIME / "candidates.py"
    before = hashlib.sha256(code.read_bytes()).hexdigest()
    packet = {"run_id": "synthetic-read-only", "incarnation": 1, "sequence": 100,
        "sim_time": 50., "capture_sim_time_s": 50.,
        "order": {"version": 1, "closed": True, "requirements": [
            {"family": "A", "recipe": "A", "count": 5, "tray": "tray1"},
            {"family": "B", "recipe": "B", "count": 5, "tray": "tray2"}]},
        "detections": [], "station": {"busy": False, "ready": True, "fault": False,
            "fixture_insert": "B", "occupied_visible_id": None},
        "gripper": {"holding_visible_id": None, "width": .08}, "inspection": None, "last_feedback": None}
    completed = ["A1", "A3", "A5", "A7", "A9", "B2", "B4", "B8", "B10"]
    with patch.object(Path, "mkdir", return_value=None), patch.object(Path, "exists", return_value=False), \
         patch.object(Candidate, "_persist", return_value=None):
        candidate = Candidate("baseline", Path("synthetic-no-files-created"), True)
        for i, pid in enumerate(completed):
            family = pid[0]
            packet["detections"].append({"id": pid, "family": family, "pos": [.4, .1, .03],
                "zone": "tray1" if family == "A" else "tray2", "visible_mark": "processed", "age_s": 0.})
            candidate._part(pid).update(family=family,
                cycle={"complete": True, "cycle_id": i+1, "recipe": family},
                inspection={"status": "pass", "cycle_id": i+1})
        packet["detections"].append({"id": "B6", "family": "B", "pos": [.1, .3, .03],
            "zone": "raw", "visible_mark": "unknown", "age_s": 0.})
        trace = []
        for i in range(5):
            current = copy.deepcopy(packet); current["sim_time"] += .2*i
            for detection in current["detections"]: detection["age_s"] = .2*i
            reply = candidate.step(current)
            trace.append({"same_capture_sequence": current["sequence"],
                "operation": reply.get("action", {}).get("operation", reply["type"]),
                "idle_steps": candidate._idle_steps, "halted": candidate.state["halted"]})
        assert [row["operation"] for row in trace] == ["observe"]*4 + ["help"]
        assert candidate.state["pending"] is None and candidate.state["last_error"] is None
        assert candidate.state["failure_counts"] == {}
        current = copy.deepcopy(packet)
        current.update(sequence=101, sim_time=51., capture_sim_time_s=51.)
        current["detections"][-1]["visible_mark"] = "raw"
        halted_reply = candidate.step(current)
        supported_if_unhalted = candidate._baseline_action()
        assert halted_reply == {"type": "wait"}
        assert supported_if_unhalted == {"operation": "transport", "part_id": "B6", "destination": "fixture"}
        current["human_answers"] = [{"answer_id": "synthetic-new-answer"}]
        current["sequence"] = 102
        resumed = candidate.step(current)
        assert resumed["action"]["operation"] == "transport" and resumed["action"]["part_id"] == "B6"
    after = hashlib.sha256(code.read_bytes()).hexdigest()
    assert before == after, "Runtime source changed during counterexample"
    return {"scope": "Synthetic source behavior only; not a diagnosis or observation of C0-007",
            "runtime_source": {"path": str(code), "sha256_before": before, "sha256_after": after},
            "repeated_frame": trace, "fresh_raw_after_halt_reply": halted_reply,
            "scheduler_action_if_unhalted": supported_if_unhalted,
            "new_answer_reply": {"operation": resumed["action"]["operation"], "part_id": resumed["action"]["part_id"]},
            "limits": "No camera image, physics, queue, project evidence or filesystem persistence was used"}


if __name__ == "__main__":
    print(json.dumps(demonstrate(), indent=2))
