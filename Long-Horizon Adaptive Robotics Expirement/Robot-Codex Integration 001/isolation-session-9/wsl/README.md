# WSL executor boundary qualification

This lane tests an OS-enforced boundary around the **entire credential-free tool executor**, including its file RPCs and spawned programs. The trusted Windows Codex harness retains subscription authentication. A model bootstrap is a separate gate; passing these nonmodel checks alone does not establish that Robot-Codex has launched.

## Demonstrated boundary

`Windows harness -> private local WebSocket bridge -> WSL bubblewrap -> Linux Codex exec-server`

The required Code Mode JavaScript host uses a second bubblewrap instance with the same mount/network policy. A short-lived Windows loopback HTTP/2 byte bridge reaches its private gRPC listener through stdio. The model cannot reach Windows loopback from either namespace. Code Mode delegates registered tool calls back to the trusted app-server; source-based routing evidence in `../native/callback-inventory.md` shows that command/file callbacks select only the remote turn environment. The outer sandbox, checked client configuration and callback routing are all parts of the boundary.

The outer bubblewrap instance creates fresh user, mount, PID, IPC, UTS and network namespaces. It disables further user namespaces, drops capabilities and clears the environment. Read-only system `/usr` and a fresh `/proc` and `/dev` support execution. The runtime is read-only except `Continuity.md`, `notes/` and `programs/`. `/tmp` is disposable process scratch. Windows drives, user homes, the development repository and protected evidence are not mounted. Windows interop `/init` is absent.

The namespace has no external route. A local HTTP listener exposes only a fixed Unix IPC broker. The Windows parent fixes its destination to the existing `HttpGateway`, with real capability authentication and `Supervisor` request processing, backed by synthetic public state. The broker admits only `GET /status` and `GET /history?...`; it accepts no arbitrary destination, actuator command or external URL. This is a non-actuating integration fixture, not a robot experiment or a complete production gateway bridge.

The executor reports `sandboxType: none` for a request because it adds no **inner** sandbox. The entire executor and its children are already inside the tested **outer** OS boundary. Both filesystem RPC and process-start canaries exercise that outer enforcement. Turning off redundant inner sandboxing does not expose a host execution path.

## Evidence progression

All attempt directories remain under `records/`.

| Attempt | Observed result |
| --- | --- |
| `canary-001` | Refused before execution: bubblewrap requires explicit `--unshare-user` with `--disable-userns`. |
| `canary-002` | All 28 direct namespace canaries passed after adding the required explicit user-namespace flag. |
| `executor-001` | Executor connection ended before initialization response. No model ran. Exact cause remains unproven. |
| `executor-002` | Initialization and direct filesystem RPC read denials passed. The redundant `--exit-on-stdin-close` option had been removed; source inspection does not establish it as the cause of the earlier EOF. |
| `executor-003` | Direct file read/write split and executor-dispatched 28-check process canary passed. |
| `executor-004` | Same tests passed with private WebSocket path, single active connection, origin policy, bounded streams and tracked Linux cleanup. |
| `lifecycle-001` | All executor checks passed; a sleeping process and detached child were positively located in the PID namespace. After disconnect, the entire namespace was empty in 0.078 seconds. |
| `client-preflight-001` through `006` | Early checks exposed an obsolete feature key, URI-versus-native cwd mismatch and an overly strict interpretation of inert MCP catalog records. The final preflight passed: ChatGPT, Astra Max, remote environment ready, local environment unknown, no automatic instruction sources or active MCP tools. No model ran in these preflights. |
| `bootstrap-001` | Actual Astra Max turn completed, but the task failed because Code Mode host was disabled. `bootstrap-assessment.json` explicitly records failure; transport completion is not bootstrap success. |
| `codehost-canary-001` / `002` | JavaScript APIs absent and imports rejected, but the test expected uppercase `Unsupported` while the actual fixed denial was lowercase. Exact error captured in 002. These attempts remain failed test records. |
| `codehost-canary-003` | Corrected exact-error comparison: all API/import/empty-tool checks and session shutdown passed inside the namespace, alongside all 28 OS checks. |
| `lifecycle-002` | Stronger retirement gate passed: bwrap records the guest namespace before execution, original PID/start identity retires, namespace is empty and Windows wrapper exits. Detached-child disconnect test also passed. |
| `bootstrap-002` | The raw gRPC relay retained its 0.2-second connect timeout during reads and disconnected mid-tool. A reconnect also exposed a fixed cleanup-evidence filename collision. Failed task/transport preserved. Neither fix changes filesystem or network policy. |
| `codehost-probe-001` | All namespace/Code Mode checks passed; HTTP/2 ping after a one-second idle interval passed after clearing the connect timeout. Namespace retirement verified. Each connection now has its own cleanup record. |
| `bootstrap-003` | Actual ChatGPT/Astra/Max exact bootstrap task demonstrated: eight startup reads hash-match frozen inputs, 28 canaries passed, observation/continuity writes and readback assertions succeeded. Outer runner returned failure on the trusted Windows client's shutdown reset. All three executor/codehost namespace retirements passed. Original runner failure remains; `retained-bootstrap-verification.json` gives the narrower successful task finding. |
| `codehost-reset-probe-001` | Corrected expected-shutdown handling passed without inference: all 28 OS checks, Code Mode API/import checks, idle HTTP/2 ping, intentional client transport abort and verified namespace retirement. This does not claim a new full model-launcher pass. |
| `codehost-reset-probe-002` | Added zero-linger to request a TCP reset; transport/retirement passed, but both abort probes recorded zero caught reset exceptions. They exercise closure and retirement without reproducing the exact Windows error branch. |

The 28 checks cover workspace reads; synthetic canaries in actual Windows repository/user paths and protected evaluator/development locations; absent Windows/home/interop paths; read-only authority files; allowed writes; symlink escape; direct IPv4/IPv6/UDP egress; a reachable-outside but hidden-inside loopback service; approved gateway access; route and authentication rejection; child inheritance; and disabled nested user namespaces. Outside positive controls confirm the protected canaries and decoy listener existed before the test. Error 2 denotes a deliberately unmounted file, error 101 denotes no network route, and error 111 denotes no listener in the private network namespace.

`lifecycle-disconnect.json` records host-visible namespace membership before and after disconnect. This is stronger than merely observing that Windows `wsl.exe` exited. It does not test recovery after a full host crash.

## Reproduction

Use the project Python environment from the repository root. Choose a **new** evidence directory; the script refuses to overwrite a prior attempt.

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/isolation-session-9/wsl/qualification.py' --mode lifecycle --evidence '<new-evidence-directory>'
```

Prerequisites measured here: Windows 11 Home, existing `Ubuntu-24.04` WSL2, Linux Python 3.12.3, bubblewrap 0.9.0, project Python 3.12.10 and existing `websockets` 17.1. No package was globally installed. The exact official Linux Codex 0.157.1 download, archive digest, binary hash and packaged-app physical path are recorded in `../options/`. The Windows client is the existing pinned daemon CLI 0.157.1.

The script creates a fresh Linux workspace under `/tmp/robot-codex-session9/<uuid>`, synthetic public files and a temporary unrelated-user canary. It removes the temporary user canary, closes listeners, retires executor descendants and revokes the runtime gateway capability. **WSL `/tmp` is not durable storage:** completed runtime directories were absent on a later startup. Retained repository evidence is durable. No account credential is copied into Linux or the runtime.

Bootstrap-003's shutdown exception bypassed its original raw-file export. `retained-tool-artifacts/` therefore contains observations from actual successful command output plus the exact executed write/readback source, clearly labeled as trace-derived. It does not claim a later physical-file snapshot. The current launcher also attempts artifact export in `finally` before closing the broker/runtime, including failed client attempts; that final export correction has not received another model run.

`--mode codehost-probe` tests the Code Mode protocol/transport without inference. `--mode client-preflight` checks client startup without inference; `--mode bootstrap` additionally makes exactly one model-turn request using the fixed prompt. Do not run further bootstrap or recovery attempts merely because this reproduction command exists; follow the current human-directed scope.

## Limits

This is bounded enforcement evidence, not proof against every kernel vulnerability or a resource-exhaustion qualification. Read-only `/usr` remains visible as the operating-system/tool runtime. The bridge is limited to synthetic read operations; actual actuator integration, robust per-program resource limits, full-host restart recovery, atomic continuity replacement and a scored release are outside this session. Completed Batch 01 and Session 8 evidence are unchanged.

Do not infer successful subscription inference, effective Astra Max, loaded tool inventory or model compliance solely from the canaries. The separate client startup and bootstrap records must establish those facts.
