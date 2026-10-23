# Client boundary tests

Run from the project root:

```text
python -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/client-tests" -v
```

The suite uses temporary workspaces and a loopback standard-library HTTP server. It checks origin/capability validation, redirect refusal, response bounds/truncation, timeout and unknown-outcome handling, pinned authority across file/status changes, observation-only refresh, rejection exit codes, request/path identity, local manual bounds and atomic-continuity request contents. It also exercises the proposed read-only program example against the fake service.

These checks never start a robot, simulator or model. They do not establish launcher isolation, physical recovery, exact-once physical effects, live program execution or scored experiment qualification. The host's own tests cover server-side admission/deduplication and atomic note persistence; this suite establishes only client behavior.
