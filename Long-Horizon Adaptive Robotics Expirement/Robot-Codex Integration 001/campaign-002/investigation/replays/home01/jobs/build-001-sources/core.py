"""Small reusable evidence operations. Never executes retained experiment code."""
from __future__ import annotations
from bisect import bisect_right
import difflib
import hashlib
import json
import math


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def clock_bracket(anchors, wall):
    """No extrapolation; return adjacent measured anchors and a navigation estimate."""
    if not finite(wall):
        return {"kind": "untimed", "sim_min": None, "sim_max": None, "estimate": None}
    if not anchors:
        raise ValueError("No clock anchors")
    walls = [a["wall"] for a in anchors]
    i = bisect_right(walls, wall)
    if i == 0:
        return {"kind": "before-recording", "sim_min": None, "sim_max": None, "estimate": None}
    left = anchors[i - 1]
    if wall == left["wall"]:
        return {"kind": "exact-anchor", "sim_min": left["sim"], "sim_max": left["sim"],
                "estimate": left["sim"], "left": left["id"], "right": left["id"]}
    if i == len(anchors):
        return {"kind": "after-stop", "sim_min": None, "sim_max": None, "estimate": None,
                "after_stop_wall_s": wall - left["wall"], "left": left["id"]}
    right = anchors[i]
    fraction = (wall - left["wall"]) / (right["wall"] - left["wall"])
    return {"kind": "wall-bracket", "sim_min": left["sim"], "sim_max": right["sim"],
            "estimate": left["sim"] + fraction * (right["sim"] - left["sim"]),
            "left": left["id"], "right": right["id"]}


def validate_anchors(anchors):
    if len(anchors) < 2 or any(not finite(a["wall"]) or not finite(a["sim"]) for a in anchors):
        raise ValueError("Incomplete finite clock bridge")
    for a, b in zip(anchors, anchors[1:]):
        if b["wall"] <= a["wall"] or b["sim"] < a["sim"]:
            raise ValueError("Regressed or duplicate wall clock; needs a separate clock segment")


def diff_text(before, after, path):
    if before is None:
        return None  # Unknown is not the empty string.
    return "".join(difflib.unified_diff(before.splitlines(keepends=True),
        after.splitlines(keepends=True), fromfile=path + " (previous evidenced)",
        tofile=path + " (selected evidenced)"))


def script_json(value):
    # Safe in a JS file or HTML script element, including literal </script>.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
