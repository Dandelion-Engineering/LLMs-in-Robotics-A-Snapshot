"""Calibrated throw from an externally perceived and aligned stationary base.

See Playbooks/Learned/ThrowOrange.md. This program does not acquire, aim,
navigate, or reset. Run only with the exercise object securely lifted.
"""
import argparse
import json
import sys
import time

sys.path.insert(0, "/")
from robot_client import call


def report(label, status):
    keys = ("sim_time", "gripper", "battery", "last_action", "throw_feedback")
    print(json.dumps({"phase": label, **{k: status.get(k) for k in keys}}), flush=True)


def action(kind, parameters):
    before = call("status", {})
    if before.get("action"):
        raise RuntimeError("Another physical action is active")
    receipt = call("command", {"kind": kind, "parameters": parameters})
    print(json.dumps({"command": kind, "receipt": receipt}), flush=True)
    if not receipt.get("accepted"):
        raise RuntimeError("Command rejected")
    deadline = time.monotonic() + 30
    while True:
        time.sleep(0.1)
        status = call("status", {})
        if not status.get("action"):
            break
        if time.monotonic() > deadline:
            raise RuntimeError("Action still active; inspect status before further control")
    if status.get("last_action", {}).get("status") != "completed":
        report("action_failed", status)
        raise RuntimeError("Action did not complete")
    report(kind, status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-scale", type=float, default=1.0)
    args = parser.parse_args()
    if not 0.7 <= args.duration_scale <= 1.4:
        parser.error("duration scale must be between 0.7 and 1.4")
    status = call("status", {})
    grip = status.get("gripper", {})
    if "learn to throw" not in status.get("assignment", "").lower():
        raise RuntimeError("Requires the throwing practice assignment")
    if status.get("action") or status["battery"]["low_warning"]:
        raise RuntimeError("Robot busy or battery warning active")
    if status["battery"]["work_seconds_remaining"] < 10:
        raise RuntimeError("Insufficient work time for another trial")
    if not (grip.get("bilateral_contact") and grip.get("secure_lift_confirmed")):
        raise RuntimeError("Requires an already confirmed secure lift")
    if not 0.08 <= grip.get("width", 0) <= 0.10:
        raise RuntimeError("Measured grasp opening differs from the calibrated object")
    action("gripper", {"width": 0.025, "duration": 0.5})
    action("arm", {"x": 0.32, "y": 0, "z": 0.85, "duration": 1})
    time.sleep(0.5)
    status = call("status", {})
    if not status["gripper"]["bilateral_contact"] or status["battery"]["low_warning"]:
        raise RuntimeError("Contact lost or battery warning before release")
    release_start = status["sim_time"]
    scale = args.duration_scale
    action("trajectory", {"points": [
        {"x": 0.63, "y": 0, "z": 1.08, "width": 0.025, "duration": 0.22 * scale},
        {"x": 1.00, "y": 0, "z": 1.35, "width": 0.15, "duration": 0.24 * scale},
    ]})
    deadline = time.monotonic() + 4
    while True:
        time.sleep(0.2)
        status = call("status", {})
        feedback = status.get("throw_feedback")
        if feedback and feedback.get("landed_sim_time", -1) >= release_start:
            break
        if time.monotonic() > deadline:
            break
    report("landing", status)
    if status["gripper"]["bilateral_contact"]:
        raise RuntimeError("Contact remains; inspect before retracting")
    action("arm", {"x": 0.36, "y": 0, "z": 1.16, "duration": 1.5})
    if not feedback or feedback.get("landed_sim_time", -1) < release_start:
        raise RuntimeError("No fresh landing feedback; outcome unconfirmed")


if __name__ == "__main__":
    main()
