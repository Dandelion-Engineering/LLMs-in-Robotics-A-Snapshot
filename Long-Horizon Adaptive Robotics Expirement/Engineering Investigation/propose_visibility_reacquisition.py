"""Build an unapplied, exact-source candidate patch; never write Runtime.

Tests execute the proposed source in memory. Running this script writes only
visibility_reacquisition.patch beside this file, for root review/application.
"""
from pathlib import Path
import difflib
import hashlib
import types

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "Runtime" / "candidates.py"
BASE_SHA256 = "fc101b3a79a4f647735f396d8938cb6156e180566d114eb5e46f8c8659e89c47"

METHODS = '''    def _visibility_state(self):
        return self.state.setdefault("visibility_reacquisition", {
            "captures": 0, "requested": False, "last_capture": None,
            "help_request_id": None, "assisted": False, "paused": False,
        })

    def _visibility_capture(self):
        packet = self._packet
        captured = packet.get("capture_sim_time_s")
        sequence = packet.get("sequence")
        if (not _finite(captured) or not isinstance(sequence, int) or isinstance(sequence, bool)
                or not 0 <= packet["sim_time"] - captured <= MAX_AGE_S):
            return None
        return [packet["incarnation"], sequence, captured]

    def _visibility_new_capture(self, capture, previous):
        if capture is None:
            return False
        if previous is None or capture[0] != previous[0]:
            return True
        return capture[1] > previous[1] and capture[2] > previous[2]

    def _visibility_answer(self, answer):
        visibility = self.state.get("visibility_reacquisition")
        if (visibility and visibility["help_request_id"] is not None
                and answer.get("request_id") == visibility["help_request_id"]
                and not visibility["assisted"]):
            visibility.update(captures=0, requested=False, last_capture=None,
                              assisted=True, paused=False)
            self._event("visibility_assisted_round", answer_id=answer["answer_id"],
                        request_id=visibility["help_request_id"])

    def _visibility_action(self):
        visibility = self._visibility_state()
        capture = self._visibility_capture()
        if not visibility["requested"]:
            visibility.update(requested=True, last_capture=capture)
            return {"operation": "observe", "reason": "request a fresh capture for visibility reacquisition"}
        if not self._visibility_new_capture(capture, visibility["last_capture"]):
            return {"operation": "wait", "reason": "await distinct fresh visibility capture"}
        visibility["last_capture"] = capture
        visibility["captures"] = min(4, visibility["captures"] + 1)
        self._idle_steps = visibility["captures"]
        if visibility["captures"] < 4:
            return {"operation": "observe", "reason": "no currently visible eligible stock or unresolved visibility"}
        if visibility["help_request_id"] is None:
            return {"operation": "help", "reason": "required progress lacks publicly supported eligible action"}
        visibility["paused"] = True
        self.state["halted"] = True
        self._event("visibility_reacquisition_blocked", captures=visibility["captures"],
                    help_request_id=visibility["help_request_id"],
                    assisted_round=visibility["assisted"],
                    reason="visibility allowance exhausted without supported progress; repeated help suppressed")
        return {"operation": "wait", "reason": "visibility remains unresolved; assistance request already retained"}

    def _resume_visibility_pause(self):
        visibility = self.state.get("visibility_reacquisition")
        if not visibility or not visibility["paused"] or self.kind not in ("baseline", "A3"):
            return
        if not self._visibility_new_capture(self._visibility_capture(), visibility["last_capture"]):
            return
        # Ask the existing scheduler; do not introduce another action ranking.
        action = self._baseline_action(visibility_fallback=False)
        if (action and action["operation"] in ("transport", "setup", "cycle", "inspect", "done")
                and self._validate(action) is None):
            visibility["paused"] = False
            self.state["halted"] = False
            self._event("visibility_supported_progress_available", action=action,
                        sequence=self._packet["sequence"], grading_authority=False)

'''


def proposed_source():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError("Candidate source changed: review proposal against the new source")
    text = raw.decode("utf-8").replace("\r\n", "\n")

    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError("Proposal anchor must occur exactly once: " + old[:80])
        text = text.replace(old, new)

    replace('            received.append(answer_id)\n',
            '            received.append(answer_id)\n            self._visibility_answer(answer)\n')
    replace('            self.state["failure_counts"].pop(signature, None)\n',
            '            self.state["failure_counts"].pop(signature, None)\n'
            '            self.state.pop("visibility_reacquisition", None)\n')
    replace('    def _baseline_action(self):\n', METHODS +
            '    def _baseline_action(self, *, visibility_fallback=True):\n')
    replace('''        if self._idle_steps < 4:
            return {"operation": "observe", "reason": "no currently visible eligible stock or unresolved visibility"}
        return {"operation": "help", "reason": "required progress lacks publicly supported eligible action"}
''', '''        return self._visibility_action() if visibility_fallback else None
''')
    replace('''        if op == "help":
            self.state["halted"] = True
        if op in ("wait", "observe"):
            self._idle_steps += 1
''', '''        if op == "help":
            self.state["halted"] = True
            visibility = self.state.get("visibility_reacquisition")
            if visibility:
                own_visibility_help = (self.kind in ("baseline", "A3")
                    and visibility["captures"] >= 4 and visibility["help_request_id"] is None
                    and action.get("reason") == "required progress lacks publicly supported eligible action")
                visibility["paused"] = own_visibility_help
                if own_visibility_help:
                    visibility["help_request_id"] = action["request_id"]
''')
    replace('''        if self.state["halted"]:
            return {"type": "wait"}
        if self._model_context:
''', '''        if self.state["halted"]:
            self._resume_visibility_pause()
            if self.state["halted"]:
                return {"type": "wait"}
        if self._model_context:
''')
    return text


def load_proposal():
    module = types.ModuleType("proposed_candidates_visibility")
    module.__file__ = str(SOURCE)
    exec(compile(proposed_source(), str(SOURCE) + " (unapplied proposal)", "exec"), module.__dict__)
    return module


if __name__ == "__main__":
    proposed = proposed_source()
    before = SOURCE.read_text(encoding="utf-8")
    patch = "".join(difflib.unified_diff(before.splitlines(True), proposed.splitlines(True),
        fromfile="a/Runtime/candidates.py", tofile="b/Runtime/candidates.py"))
    destination = HERE / "visibility_reacquisition.patch"
    destination.write_text(patch, encoding="utf-8", newline="\n")
    print(f"Unapplied patch: {destination}; base source SHA256 {BASE_SHA256}")
