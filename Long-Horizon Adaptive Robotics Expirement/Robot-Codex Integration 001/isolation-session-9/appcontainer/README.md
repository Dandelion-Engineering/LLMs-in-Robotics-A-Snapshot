# AppContainer synthetic canary, Session 9

**A real, zero-capability Windows AppContainer enforced the tested file permissions and returned network access denied for an outbound TCP attempt. A credential-free host broker delivered one approved synthetic localhost operation. This does not qualify Robot-Codex or a production broker.**

The final bounded attempt is [attempt-20260926-230601/events.jsonl](attempt-20260926-230601/events.jsonl), with [child observations](attempt-20260926-230601/child-observations.tsv) and frozen source copies beside it. Windows reported build 26200; Python was 3.12.10. Source and compiled-executable SHA-256 hashes are in the event log. No model, robot, evaluator, credential, or personal-document contents were accessed.

| Check | Actual observation | What it establishes |
|---|---|---|
| Container token | `TokenIsAppContainer = 1` inside child | The child really ran in AppContainer. |
| Allowed read | Read task-created `SYNTHETIC-READ` | The explicit read grant worked. |
| Allowed write | Task-created mailbox write succeeded | The explicit modify grant worked. |
| Write to read-only runtime | `UnauthorizedAccessException`, Win32 5 | Tested read-only boundary enforced. |
| Protected synthetic file read and write | Both Win32 5; original file unchanged, no new protected write | Tested no-package-grant boundary enforced. |
| Outbound TCP to `192.0.2.1:443` | `SocketException:10013:AccessDenied` | OS denied this network attempt; this is not a mere timeout. No application payload sent. |
| Direct loopback to two IPv4 services and one IPv6 service | Each timed out after 1.5 seconds; zero corresponding host accepts | Bounded non-connectivity with positive controls, **not** a returned access-denied error or all-network proof. |
| Host positive controls | All three loopback services returned HTTP 200 immediately before launch | Services existed and accepted connections from the host. |
| Approved broker operation | Fixed `synthetic_ping` request returned `SYNTHETIC-LOOPBACK-REPLY` | AppContainer can reach one approved host operation without direct networking or copied credentials. |
| Arbitrary URL request | Broker returned `operation_not_allowlisted`; no extra service connection | The demonstrator refused its tested unapproved operation. |
| Process and profile cleanup | Child exit 0; `DeleteAppContainerProfile` HRESULT 0 | The completed attempt cleaned up its task profile. Process started suspended and entered a kill-on-close job before resume. |

The final run's 11 bounded checks passed. `loopback_bounded_no_accept` has its deliberately limited meaning above. The host observed exactly four connections: the three positive controls and one approved broker request. The executable had a single-process job limit and a 15-second lifetime bound; no child processes were permitted.

## Preserved attempts

1. [23:03:49](attempt-20260926-230349/events.jsonl): console executable; minimal scrubbed environment; `CreateProcessW` returned Win32 203 (`ERROR_ENVVAR_NOT_FOUND`). No child ran. Profile deletion succeeded.
2. [23:04:26](attempt-20260926-230426/events.jsonl): changed compiler target to `winexe` to avoid requiring console configuration. Same 203 failure; profile deletion succeeded.
3. [23:04:42](attempt-20260926-230442/events.jsonl): added explicit scratch-valued `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, actual `SystemDrive`, and case-insensitive environment ordering. Child ran and file/outbound/broker checks worked. Direct loopback probes timed out. This combined change resolved launch; the responsible individual variable or ordering change was not isolated.
4. [23:06:01](attempt-20260926-230601/events.jsonl): added reachable IPv4/IPv6 positive controls, server-side connection counters, source snapshots, executable hash, and explicit result predicates. Result is the table above.

The first two launch failures and the first successful run are retained; they are not silently promoted to the stronger final result. Initial console target did not prove a console incompatibility, because switching the target alone did not resolve its error. No global console registry configuration was changed.

## What was changed on the machine

Each attempt created a uniquely named, zero-capability per-user AppContainer profile, then deleted it with Microsoft's API. This is a Windows application profile, not a new Windows user account. Only directories/files newly created under that attempt received ACL and low-integrity-label changes. Existing repository ancestors, user files, and other applications' ACLs were untouched. No elevation, firewall changes, loopback exemptions, system settings, or credential copies were used. Only the task's synthetic HTTP listeners were started, and all were closed.

The parent prepared a read-only executable/data directory, a modifiable mailbox, and a protected sibling. It supplied an explicit environment containing OS paths and task scratch paths, rather than inheriting arbitrary parent environment contents. The child inherited no handles.

## Practical integration boundary

Direct AppContainer TCP to the existing unpackaged robot host is not established here. Microsoft documents administrator-managed loopback exemptions for packaged-to-unpackaged loopback; that route was not used. Granting general network capabilities would widen the boundary and would still not prove port-specific isolation.

The successful demonstrator instead uses this flow:

`AppContainer -> task mailbox -> trusted host broker -> fixed synthetic 127.0.0.1 endpoint`

The broker accepts exactly one operation with one fixed request identity and destination; it does not accept a URL supplied by the child. This makes a no-network robot client transport technically plausible without copying authentication material into the robot filesystem. It is only a transport feasibility result: the existing client and lifecycle integration have not been changed, and no real robot endpoint was used.

**The filesystem mailbox is not a hardened production broker.** It has no hostile reparse/hardlink/TOCTOU defense, durable replay protocol, authenticated session lifecycle, or capability negotiation. A production implementation should use a narrowly ACLed IPC channel or validated object handles and preserve the host's existing operation, epoch, ownership, and safety checks. The synthetic request comparison does not establish those protections.

Normal AppContainer also retains access to some OS resources granted to all application packages and to its own profile. This test does not establish a filesystem allowlist consisting exclusively of the two scratch directories. It does not test access to real protected files, runtime Python/tool descendants, registry/process/object namespaces, Codex daemon authentication, exact model selection, or the actual launcher's same-policy sentinel. Less-Privileged AppContainer is a distinct option and was not tested.

## Reproduce within the same bounded scope

From the repository root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/isolation-session-9/appcontainer/probe.py'
```

This creates a fresh attempt directory and profile; it does not reuse a prior profile. It compiles the small C# canary using the installed .NET Framework compiler, with a 20-second compiler timeout. No downloaded code or packages are needed. The observed compiler/runtime availability is host-specific. Binary scratch artifacts are ignored by the local `.gitignore`; source, hashes, canaries, and event logs preserve the result.

## Official sources checked

- [Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer): token capability/package-SID access model, creation attributes, and distinction between regular and less-privileged AppContainer.
- [CreateAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile): per-user profile creation API.
- [Microsoft launch example](https://github.com/microsoft/SandboxSecurityTools/blob/main/LaunchAppContainer/LaunchAppContainer/LaunchAppContainer.cpp): process attributes and profile lifecycle. Our harness does not apply the example's global console registry setting.
- [Windows IPC guidance](https://learn.microsoft.com/en-us/windows/apps/develop/communication/interprocess-communication): IPC options and packaged/unpackaged loopback constraints. This source distinguishes full-trust desktop applications from constrained applications; its unrestricted desktop IPC statements are not evidence of unrestricted AppContainer IPC.
- [Windows Firewall UWP connectivity](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/troubleshooting-uwp-firewall): loopback troubleshooting/exemption mechanism; no exemption was applied.

Sources checked September 26, 2026. This is local engineering evidence, not Robot-Codex recovery performance or permission for a scored campaign.
