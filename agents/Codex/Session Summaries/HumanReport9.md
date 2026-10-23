# Session 9 — enforced isolation and actual Robot-Codex bootstrap

September 26, 2026 PDT. Randy's focused isolation follow-up was the authority for this session. The practical result is **an OS-enforced WSL2/bubblewrap boundary and an actual ChatGPT-authenticated GPT-6 Astra / Max bootstrap inside it**. No robot experiment or recovery campaign ran.

Read the [focused handoff and evidence map](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/isolation-session-9/README.md). It preserves native Windows, separate-identity, AppContainer, WSL and VM/container observations rather than recasting prior failures as successes.

## What the boundary enforces

The trusted installed Windows Codex 0.157.1 app-server retains the existing subscription login. Its entire credential-free Linux tool executor and required Code Mode host run in separate namespaces under the same policy. The robot workspace is readable; only notes, programs and Continuity.md are persistent writable mounts. System runtime files are read-only and temporary process scratch is disposable. Windows drives, user homes, repository/evaluator/reference/development files and Windows interop are absent. Capabilities and nested user namespaces are disabled, and there is no external network route.

A fixed broker exposes only authenticated synthetic status/history through the real protected gateway implementation. It fixes the destination, rejects other routes and disables proxy/redirect behavior. All 28 canaries passed directly, through the executor, and when the actual model called them. Positive controls established that denied repository/user canaries and an unrelated loopback service existed outside the boundary. A detached child also disappeared with its namespace after disconnect.

Checked startup evidence confirms `gpt-6-astra`, `max`, ChatGPT account type, the exact sole user prompt `Follow the instructions in RobotAgentPrompt.md.`, no automatic instruction sources, no local execution environment, a ready selected remote environment and no active MCP tools. Apps, browser, web, skills, memory, image and subagent capabilities were disabled. Source evidence maps registered command/file callbacks to the selected remote environment and rejects unknown environments; the API does not expose a complete live model-tool schema. No account credentials were read/copied, no API access or paid infrastructure was substituted, and Robot-Codex did not create subagents.

## Actual bootstrap evidence and remaining launcher issue

There were three actual model turns, all retained. Bootstrap-001 failed because Code Mode was disabled. Bootstrap-002 failed after a relay retained its short connect timeout; reconnection also exposed a cleanup-evidence filename collision. Both defects were corrected without changing the isolation policy.

Bootstrap-003 completed the requested task. Independent verification matches all eight required startup-read outputs to frozen input hashes. The actual canary command returned 28 passes. A successful Python command wrote both observation files and continuity, then read them back and asserted their contents. Recorded task, activation, generation, robot identifier, event and continuity marker all match the fixture. The saved boundary result matches the actual canary output. No actuation occurred. See [retained verification](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/isolation-session-9/wsl/records/bootstrap-003/retained-bootstrap-verification.json).

The outer runner nevertheless returned failure at shutdown: the Windows client closed its connection and the relay treated its reset as a fault. Original failure evidence remains, and all three relevant namespace retirements passed. Expected-shutdown handling is now explicit; later nonmodel HTTP/2 abort and retirement checks passed but did not reproduce the exact reset exception. The fully corrected model-launcher path was not rerun.

That shutdown failure bypassed the original raw output export. WSL temporary runtimes were absent on a later startup, so durable outputs are explicitly reconstructed from retained successful command output and the executed write/readback source, not labeled as later raw-file snapshots. The current launcher attempts export before runtime teardown even after client failure; that final change has no additional model-run validation. This limits release readiness, not the evidence that the bootstrap actually read and wrote within the enforced boundary.

## Next decision and continuity

I recommend retaining this WSL boundary instead of falling back to instruction-only monitored mode. Before robot integration, the next authorized engineering step should qualify a clean complete launcher run, durable runtime/artifact retention and the actual actuator gateway under the same boundary. Full-host restart, per-program resource limits, atomic continuity replacement and scored-release admission remain open. Randy must review before any recovery experiments. Earlier Batch 01 results, generic framework files and Session 8 evidence remain unchanged.

This session also resolves the Git continuity issue. Session 8 committed its report/summary/handoff but did not append a chat reply; the pre-existing local addition was Randy's 19:36 task. I preserved that complete append, pulled origin/main's 22:17 follow-up, mechanically reconciled their chat conflict without rewriting the original transcript prefix, and added this session's reply through the chat tool. The scoped closeout includes all three portions together. The preservation stash remains an extra backup.
