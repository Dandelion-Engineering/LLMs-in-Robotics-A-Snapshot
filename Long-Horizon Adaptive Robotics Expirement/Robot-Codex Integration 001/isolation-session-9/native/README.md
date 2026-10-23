# Native boundary diagnosis and remote harness binding

This directory contains a bounded, nonmodel native refusal probe, a read-only
exec-server metadata probe, and a Windows app-server client. The parent session
owns the WSL executor, its isolation qualification, and any bootstrap invocation.
`bootstrap_client.py` defaults to preflight without a model call. Its only
inference gate is `--run-bootstrap`; the bootstrap text is exactly
`Follow the instructions in RobotAgentPrompt.md.`

Preflight-006 passed the settings, instruction provenance, remote execution, and
inert MCP inventory gates. Bootstrap-001 subsequently completed a model turn
but failed the requested bootstrap: its workspace tool reported that the Code
Mode host was disabled, so the agent could not read `RobotAgentPrompt.md`. No
completed command item established successful tool execution. The client's
`success` field means transport/preflight/model-turn completion, not successful
fulfillment of the robot bootstrap. Preserve the parent's separate assessment.

## Native result

The prior elevated root-deny sentinel did not reach a demonstrated child check.
The Windows sandbox log rejected effective root-deny in sentinel-001, failed to
apply a deny-read ACE to `C:\Users` with access denied in sentinel-002, and ended
at `setup refresh: spawning ... codex-windows-sandbox-setup.exe` for sentinel-003.
No subsequent setup completion or Python child evidence was present. The last
record localizes the timeout to setup refresh; it does not establish the helper's
internal reason for hanging. A parent result with exit code zero and an explicit
timeout termination is not a successful sentinel.

The one authorized strict unelevated refusal probe is retained under
`unelevated-refusal-001/`. It requested only `cmd.exe /d /c exit /b 0` inside the
original root-deny profile. Codex refused in 0.109 seconds with exit code 1:
`Restricted read-only access requires the elevated Windows sandbox backend`.
The requested child was not demonstrated to run. No broader native fallback,
privileged setup, model, or robot action was attempted by this helper.

This agrees with the supported distinction: the elevated Windows backend uses
separate low-privilege accounts and ACL/firewall enforcement, while the
unelevated restricted-token backend supports fewer policies. Unsupported split
read policies must be refused. [Official Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox)

## Why an external Linux executor is materially different

The parent's WSL qualification puts the complete Linux exec-server and its
descendants inside a separately constructed namespace. Codex's inner permission
profile is not the authority for host file or network access. The namespace must
already be qualified before using this client. See the parent's `wsl/records/`
for positive and negative controls, runtime hashes, actual filesystem/process
RPCs, and lifecycle cleanup evidence.

The pinned Codex 0.157.1 source has these relevant properties:

| Property | Primary implementation evidence |
|---|---|
| `CODEX_EXEC_SERVER_URL=none` includes neither local nor remote default execution | `exec-server/src/environment_provider.rs`, snapshot construction |
| A configured remote environment uses remote process **and** filesystem backends | `exec-server/src/environment.rs`, `remote_with_client` |
| `CODEX_HOME/environments.toml` supersedes the simple environment-variable selector | `exec-server/src/environment.rs`, `prepare_from_codex_home` |
| Windows `codex exec -C` resolves a local absolute path first | `exec/src/lib.rs`, CLI cwd setup |
| A Windows `file:///C:/...` URI cannot be converted into a native Linux path | `utils/path-uri/src/lib.rs`, `to_abs_path` |
| App-server environment metadata returns a file URI; thread/turn selections require target-native absolute paths | local generated 0.157.1 protocol schemas and retained preflight-004 rejection |
| CLI tables are layered recursively; `mcp_servers={}` cannot clear inherited entries | `config/src/overrides.rs`, `config/src/loader/mod.rs`, `config/src/merge.rs` |
| MCP status inventory can include disabled configured servers with zero capabilities | `app-server/src/request_processors/mcp_processor.rs`, runtime status union and response construction |

Sources are pinned to [openai/codex, rust-v0.157.1](https://github.com/openai/codex/tree/rust-v0.157.1).
`source-evidence.json` supplies full source hashes and exact excerpt ranges;
`source-excerpts.txt` retains the relevant lines. Upstream source is licensed under
[Apache 2.0](https://github.com/openai/codex/blob/rust-v0.157.1/LICENSE).

Mapping a Windows cwd into a Linux directory named `/C:/...` is insufficient:
`PathUri::to_abs_path` rejects foreign conventions before any filesystem lookup.
The app-server route instead selects `/workspace` explicitly in both
`thread/start` and `turn/start`; environment metadata reports that location as
`file:///workspace`. Preflight-004 rejected a URI passed in the selection field
before inference. The client now makes this conversion explicitly.

## Client contract and retained limits

The client starts the trusted Windows app-server in a kill-on-close Job Object
after suspended creation. It enforces a time and output bound, checks ChatGPT
login status without reading authentication files, requires the exact requested
model and `max` effort, and refuses API/provider fallback. Ambient config values
and account identity are not persisted. Only MCP table headers in the ordinary
user `config.toml` are enumerated, so those servers can be explicitly disabled.
Managed/project MCP entries still have to pass the filtered effective-config
check. An ambient environments file, instruction file, provider override, loaded
instruction source, active or unverified MCP inventory, or surviving local executor aborts
preflight. Unknown host/approval requests are rejected.

Disabled MCP catalog entries are permitted only when their names match an
independently disabled effective-config entry, their thread runtime status is
exactly `disabled`, their tools/resources/templates are empty, and they have no
server metadata, capabilities, discovery error, or further inventory page. The
status API deliberately includes these inert configuration records; treating
every record as an active tool was the preflight-005 assertion failure.

The client explicitly disables automatic project documents, skills instructions,
host skill discovery, apps, plugins, hooks, memories, browsers, image tools,
subagents and web search. Dynamic tools and selected capability roots are empty.
The user bootstrap is unchanged. Capability tokens supplied by the parent in
`args.redact_tokens` are redacted from every persisted event.

An optional `--code-mode-host-url` selects a separately qualified remote Code
Mode host over loopback HTTP/2 gRPC. This enables only `features.code_mode_host`;
the other disabled capabilities remain disabled and checked. The URL is omitted
from persisted launch metadata. App-server source selects a dedicated gRPC
provider when this flag is present and rejects startup if the corresponding
feature is disabled. Connection/session-open errors propagate from that
provider; the selected branch does not construct the local process provider.

`../wsl/codehost_canary.py` is the fixed, nonmodel stdio qualification script for
the code host. The caller must run it inside the qualified namespace. It supplies
no tools, rejects delegates, uses a 20-second bound, and checks that process,
require, fetch, Deno, Bun, WebSocket and XMLHttpRequest APIs are absent and that
Node, file and HTTPS module imports are denied. Source confirms a bare V8
runtime with an explicit helper/tool surface and a module loader that rejects
all imports. These are normal API and protocol checks; OS confinement remains
the outer namespace's responsibility. Unlike exec-server's line protocol,
code-host stdio uses a four-byte little-endian length followed by JSON.
The parent's codehost-canary-003 passed these checks and session shutdown inside
the outer boundary. Attempts 001 and 002 preserved a harness case mismatch in
the import-denial string, which was corrected against the observed exact
`unsupported import in exec` result. See `callback-inventory.md` for the separate
source-derived authority map of callbacks dispatched by the Windows harness.

App-server preflight results are runtime evidence, separate from source-based
expectations. The API does not expose the complete model tool schema through
`thread/start`. `codex debug prompt-input` returns prompt input, not the complete
tool specification or base system instructions, and uses a different config
loading path; it is not proof of complete inventory parity. Successful direct
executor canaries alone do not prove that the Windows model harness routes all
tools remotely. The client checks the available configuration, environment, and
instruction provenance before inference; the parent must preserve these limits
when interpreting the bootstrap trace.

The protocol is newline-delimited JSON on exec-server stdio, with one JSON
message per line; it is not Content-Length/LSP framing. The parent observed
premature EOF with its initial `--exit-on-stdin-close` attempts and later passed
without that option. Source does not establish a stdin watcher race: the flag
is consumed in the remote-registration branch, whereas the local `--listen`
branch uses independent lifetime. Preserve the observation without claiming an
unproven cause.

Codex network domain rules are not a single-port loopback boundary; hostname
matching normalizes away ports. The parent's separate fixed-purpose gateway
broker and outer network namespace must enforce the narrower requirement.
[Official permissions documentation](https://learn.chatgpt.com/docs/permissions)
