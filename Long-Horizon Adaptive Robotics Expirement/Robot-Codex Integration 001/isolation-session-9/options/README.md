# Windows and WSL isolation options: observed inventory

Development helper `isolation_options`, September 26-27, 2026. This is a bounded machine inventory and namespace probe, not qualification of a Robot-Codex launch. No model or robot ran, no credentials were inspected/copied, and no accounts, Windows ACLs, firewall rules, optional features, or existing WSL configuration were changed.

## Strongest prospect

The existing WSL2 environment can enforce a private filesystem and network namespace using installed bubblewrap. A no-model Python process launched successfully with only read-only `/usr`, fresh `/proc` and `/dev`, and ephemeral `/tmp`. It could not resolve Windows mounts, the Linux home, `/init`, or `/proc/1/root/mnt/c`; direct external TCP failed with `ENETUNREACH`.

Both existing distributions can execute the exact official Linux Codex 0.157.1 binary acquired during this session. Its `exec-server` help supports local WebSocket and stdio transports. This permits investigating a trusted Windows Codex harness, retaining its current subscription authentication, with tool execution in a WSL sandbox. The installed Windows protocol's `environment/add` and thread environment fields were independently found by `native_diagnosis`; inspect that helper's compact selected schema record in `../native/schema-evidence.json`.

The remaining integration work is to demonstrate that **all** model-accessible filesystem/execution surfaces use the isolated executor, and to broker only the approved robot gateway across its otherwise disconnected network. Root owns those probes. Neither native Linux authentication against the Windows home nor a model turn was attempted by this helper.

## Current machine observations

| Surface | Observation | Implication |
| --- | --- | --- |
| Windows edition | `Win32_OperatingSystem`: Windows 11 Home, build 26200, x64. Registry `EditionID=Core`, UBR 9457; historical registry ProductName says Windows 10 Home. | Use the actual Home edition when assessing optional features. |
| Current token | Medium integrity; Administrators SID deny-only. No `SeAssignPrimaryToken`, `SeIncreaseQuota`, `SeDebug`, or `SeImpersonate` privilege in `whoami /priv`. | The current process is not elevated. A read-only optional-feature query returned “The requested operation requires elevation.” |
| Hypervisor/WSL | HypervisorPresent=true. WSL 2.7.12.0, kernel 6.18.33.2. Both `Ubuntu-24.04` and `LLMs-Robotics-Candidate-001` are WSL2. | An existing Linux isolation substrate is available without installing Windows features. Inventory calls started these previously stopped distributions. |
| Installed Ubuntu tools | Python 3.12.3, bubblewrap 0.9.0 (`0.9.0-1ubuntu0.3` package), util-linux 2.39.3, socat 1.8.0.0, iproute2 6.1.0. | No need to install a container manager to try namespaced execution. |
| Native Linux Codex before this session | Not found in PATH/common Linux installation locations. Ubuntu's PATH resolved only the Windows npm shim. Linux `node` absent. | A real Linux executable was needed; the Windows shim is not evidence of Linux installation. |
| Windows Codex | Project launcher targets daemon CLI 0.157.1. Separate desktop binary at `.../OpenAI/Codex/bin/247581e40ee272fb` is 0.155.0-alpha.9.2; npm package is 0.147.0. | Pin the actual 0.157.1 binary; PATH is ambiguous. |
| Existing sandbox users | `CodexSandboxOffline` and `CodexSandboxOnline` enabled; both members of `CodexSandboxUsers`. | These are pre-existing identities, not newly provisioned robot users. No passwords or identity credentials were read. |
| Repository NTFS ACL | Inherited `CodexSandboxUsers` allow `ReadAndExecute, Synchronize`. | Merely launching as either existing sandbox user does not deny repository reads. Additional restrictions are required. |
| Main user profile ACL | Protected ACL allowing SYSTEM, Administrators, current user; separate capability entry grants traverse/synchronize only. | A genuinely separate unprivileged identity could benefit from existing NTFS separation, subject to exact child ACLs and canary tests. |
| Firewall | Active domain/private/public profiles enabled; effective inbound Block, outbound Allow. | A dedicated identity alone does not limit outbound network destinations. |
| Other VM/container tools | No `docker`, `podman`, `WindowsSandbox`, or `Get-VM` command; no executable at the standard Docker Desktop, VirtualBox, VMware Workstation, or QEMU locations checked. | These are negative bounded inventory checks, not an exhaustive disk scan. |

## Materially different approaches

1. **Existing native Codex sandbox/restricted token.** Windows supports restricted tokens and AppContainers. Their compatibility with this installed client and the required loopback route must be tested; availability of the primitive does not establish the requested boundary. `native_diagnosis` owns the current native investigation.
2. **Dedicated Windows identity with NTFS policy.** A distinct SID plus carefully scoped permissions can protect files, but account creation/alternate-identity startup and network enforcement are additional requirements. Existing Codex sandbox accounts already inherit repository read permission. No account was created or borrowed, and no credential was retrieved. Current non-elevated execution is a practical provisioning limitation, not proof that this approach is impossible.
3. **WSL2 plus bubblewrap.** Already installed and exercised. A private mount/PID/user/network namespace removes broad Windows mounts and process visibility. The existing project runtime already uses a related bubblewrap worker. A restricted gateway broker and tool routing need separate qualification.
4. **Windows Sandbox/full Hyper-V VM.** Microsoft explicitly excludes Windows Home from these features. They were absent in bounded command/path inventory. This is not an immediately usable installed route on this machine.
5. **Docker/Podman/third-party VM.** No installation found in the checked surfaces. Installing or developing a separate stack was not necessary before testing the available WSL primitive.

## WSL configuration and probe limitations

`LLMs-Robotics-Candidate-001` defaults to the unprivileged `dandelion` user. Its `wsl.conf` disables Windows interop and Windows PATH injection, but **enables automount**; `/mnt/c` and `/mnt/d` were read-write DrvFS mounts. Ubuntu retains ordinary Windows interop/PATH behavior. Either distro used directly therefore exposes substantially more than the intended runtime.

`unshare -Urnm --fork` succeeded as the default user in both distros, showing distinct user/mount/network namespaces with an empty route table. The more representative bubblewrap/Python probe also used `--unshare-all --cap-drop ALL --clearenv --die-with-parent --new-session`, read-only `/usr`, fresh `/proc` and `/dev`, and tmpfs `/tmp`.

Observed probe results:

- `/mnt/c`, `/mnt/d`, `/home`, `/init`, `/proc/1/root/mnt/c`: `FileNotFoundError`, errno 2.
- `/usr/bin/python3`: available; the root contained only bin/dev/lib/lib64/proc/tmp/usr.
- TCP `1.1.1.1:443`: errno 101, `Network is unreachable`.
- TCP `127.0.0.1:54321`: errno 111, `Connection refused`.

These are namespace observations, not a complete file-canary/gateway/Robot-Codex test. No approved loopback service was included in this helper's probe. The initial shell-based probe printed an unreliable exit-status value due to nested command quoting; the later Python-based checks above supersede that status, and the original attempt is not counted as a canary pass.

## Exact Linux binary acquisition

The public OpenAI release `rust-v0.157.1`, published 2026-09-26 01:02:31Z, supplied `codex-x86_64-unknown-linux-musl.tar.gz` (107,868,387 bytes). The downloaded archive matched the release API's SHA-256 digest before extraction:

`e98c1e8e028e8137fa2d2415c82ec58e7b3701a627e3554aace5b3ca31454af2`

Extracted binary SHA-256:

`3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970`

Logical Windows scratch directory:

`C:\Users\cresp\AppData\Local\RobotCodex\Integration001\isolation-session9-linux-01571`

The packaged desktop environment virtualizes that path. The real WSL path, obtained through `GetFinalPathNameByHandleW`, is:

`/mnt/c/Users/cresp/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/RobotCodex/Integration001/isolation-session9-linux-01571/codex-x86_64-unknown-linux-musl`

The first attempt using the logical `/mnt/c/.../Local/RobotCodex` path failed `No such file or directory`. Using the physical path succeeded in both distros with `codex-cli 0.157.1`. `exec-server --help` confirms `--listen ws://IP:PORT`, `stdio`, `stdio://`, and `--exit-on-stdin-close`. No server or model was started by those checks. Provenance/help/version records reside with the download; this folder contains copies of the small records only.

## Primary sources consulted

- [Microsoft: Windows Sandbox](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/) — Home exclusion and virtualized isolation.
- [Microsoft: Install Hyper-V](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/get-started/Install-Hyper-V) — Home exclusion and elevated installation requirements.
- [Microsoft: WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) — automount, interop and networking settings.
- [Microsoft: WSL file permissions](https://learn.microsoft.com/en-us/windows/wsl/file-permissions) — DrvFS requests retain Windows-user permission constraints.
- [Microsoft: Restricted tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens) — restricting SIDs, access checks, ordinary-application restricted process support.
- [Microsoft: AppContainer for legacy apps](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-for-legacy-applications-) — unpackaged applications and inherited AppContainer restrictions.
- [Microsoft: CreateProcessAsUserW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw) — alternate-identity process requirements and restricted-token exception.
- [Official OpenAI documentation: configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) and [developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli) — distinguish remote app-server control and tool configuration from an isolated executor.
- [Official OpenAI documentation: self-hosted sandboxes](https://developers.openai.com/api/docs/guides/agents-api/environments/self-hosted) — its documented remote-registration example uses API keys. It was not used; the proposed local executor connection is a distinct installed-client protocol.
- [Official OpenAI release 0.157.1](https://github.com/openai/codex/releases/tag/rust-v0.157.1) — exact Linux binary and release API asset digest.

## Later bounded Code Mode host acquisition

After the root agent's first bootstrap identified a required Code Mode host, this helper acquired the **exact same official release's** `codex-code-mode-host-x86_64-unknown-linux-musl.tar.gz` (27,470,020 bytes). Its archive SHA-256 matched the official release asset digest before extraction:

`3516f9b8bbe6bc06ee7bdb92b293a17eab194b3f10b9b9ea10c5b839e972d7fc`

Extracted binary SHA-256:

`67b86142bac5cead11b8420cf32d3a2bf88c8868d71733f351ed7c5d95a953e0`

The binary is alongside the Linux CLI in the same task scratch; its filename is `codex-code-mode-host-x86_64-unknown-linux-musl`. The actual help lists `--listen stdio`, `stdio://`, or `grpc://IP:PORT`. It has no version flag, so version provenance is the exact release asset and verified digest. Help also runs successfully inside a fresh bubblewrap root with read-only `/usr`, private `/proc`/`/dev`/tmpfs, empty environment, dropped capabilities and nested user namespaces disabled. This establishes executable compatibility only; no Code Mode server, inference, or credential operation was started by this helper. The three `code-mode-host` provenance/help files here preserve the small records.
