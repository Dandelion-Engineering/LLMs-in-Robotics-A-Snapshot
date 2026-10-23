# Robot-Codex launcher

Status: **blocked before any model turn**. On 2026-09-27 UTC, the installed
Codex 0.157.1 elevated sandbox failed to qualify all three tested profiles. The
initial deny-by-default profile failed:

> windows sandbox failed: elevated Windows sandbox requires effective `:root` read access

The explicitly authorized development alternative used root read, C:/Users
deny, exact repository/CODEX_HOME/evidence denies, narrow workspace/Python/pwsh
reopens, and denial of other fixed drives. It also failed before running the probe:

> windows sandbox failed: helper_unknown_error: apply deny-read ACLs

A final explicit `bootstrap-diagnostic` removed Users-wide and drive-root denial
but retained exact repository/CODEX_HOME/evidence/synthetic-subtree denials and the
workspace write split. It timed out after 30.031 seconds with empty stdout/stderr
and no completed checks. Its exit code was 0 after cleanup; the timeout explicitly
makes qualification fail. The cause of that timeout is unknown; this does not
establish technical impossibility. This diagnostic leaves other user/system paths
potentially readable and is not adequate isolation for robot or scored work.
No further native probe or model turn was attempted.

The development alternatives are explicit `--boundary-profile` options; they are
not silently selected.
Even if later supported, system-drive paths outside the denied trees remain
readable and would limit it to an explicitly qualified development use.
Metadata preflight passed: the exact
installed version, an existing ChatGPT login, and bundled `gpt-6-astra` with
`max` reasoning were confirmed. Model availability metadata is not a successful
model invocation. No robot or model turn was run by this launcher during this
implementation.

`robot_codex_launcher.py prepare` copies a configured template to a fresh external
workspace. `preflight` checks authorization status and minimal model catalog
metadata. `sentinel` uses synthetic files and a temporary loopback listener to
check the actual native sandbox without a model call. `run` refuses to launch
without a successful same-policy, same-workspace, same-binary sentinel record.
Every invocation requires a fresh operator-owned evidence directory. Previous
failures remain available.

The exact bootstrap is `Follow the instructions in RobotAgentPrompt.md.` The
launcher proposes `exec --ignore-user-config --ignore-rules --strict-config`, pins
`gpt-6-astra` / `max`, and never passes legacy `--sandbox`, `sandbox_mode`, or
bypass switches. Its requested policy makes workspace files readable and only
`Continuity.md`, `notes/`, and `programs/` writable. It requests denial of the
repository, evaluator-containing tree, CODEX_HOME, and operator evidence; these
boundaries have not passed a runtime probe. The base Python installation
has a narrow read grant. Windows/system runtime reads use Codex `:minimal`.
The dedicated program runner is unavailable and task instructions prohibit
generated-program execution. The sandboxed shell remains programmable; the
launcher cannot truthfully claim to disable all arbitrary program execution.
Its job-level process/time bound is not per-program resource qualification.

Windows processes start suspended, enter a kill-on-close Job Object, then resume.
Timeout, output overflow, and normal process completion close that job, retiring
descendants. Stdout, stderr, command arguments, exit status, elapsed time, and
termination reason are retained. Environment credentials are filtered by name
without printing their values. The Codex process keeps CODEX_HOME solely to reuse
its existing login; no authentication file is opened, copied, or modified by the
launcher. Model evidence must come from the CLI startup preamble on stderr; model
prose or the final stdout answer cannot satisfy verification.

The configuration disables memory, subagents, plugins, apps, hooks,
browser/computer use, search, automatic host skill discovery, and shell snapshots.
AGENTS discovery has a
zero-byte budget; the exact bootstrap explicitly loads RobotAgentPrompt.md.
These configured suppressions still need a captured loaded-context/tool inventory
before a model run can count as fully qualified. No loaded runtime inventory or
real model header was captured: current sentinel failures stop that stage.
`--ignore-user-config` alone is not asserted to suppress all instruction sources.

`--loopback` is reserved for the protected HTTP gateway. It configures a network
proxy with only `127.0.0.1` allowed; the domain policy does not enforce a single
port. No loopback-enabled sentinel has been implemented or qualified, so `run`
currently rejects that mode through the qualification gate. No fallback widens
network or filesystem access. Gateway epoch fencing and cancellation remain
separate required controls.

Commands (run from the project root):

```powershell
python -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/launch/test_launcher.py'

python -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/launch/robot_codex_launcher.py' sentinel --workspace 'C:/Users/cresp/AppData/Local/RobotCodex/Integration001/bootstrap-001' --evidence 'C:/Users/cresp/AppData/Local/RobotCodex/Integration001/launch-evidence/sentinel-next'
```

The prepared bootstrap workspace originates from the root-owned `smoke-template`;
the generic `Robot Agent Filesystem v0.1` is unchanged. The Windows packaged app
may resolve Local AppData aliases to its package LocalCache path; evidence records
the resolved path actually used for policy and comparisons.

Official references consulted: [permission profiles](https://learn.chatgpt.com/docs/permissions),
[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox), and
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
The installed sandbox refusal is the decisive runtime evidence, even though
current documentation describes more general profile support.
