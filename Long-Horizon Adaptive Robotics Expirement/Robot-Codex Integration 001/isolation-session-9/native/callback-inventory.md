# Code Mode callback authority, Codex 0.157.1

This is a source-derived routing inventory under this client's checked settings,
not a claim that app-server supplied a complete live tool-schema export. The
parent's actual bootstrap trace must separately establish usable remote tools.
The Code Mode host executes JavaScript; named tool callbacks are dispatched by
the trusted Windows app-server. Its namespace alone does not confine callbacks.

| Callback family | Available authority and routing |
|---|---|
| `exec_command` | Selected turn environment only. The handler resolves an optional environment id against the turn snapshot, then resolves workdir against that environment's cwd and obtains that environment's filesystem. Runtime remote execution uses the remote process backend. This client has exactly one selected remote environment and no local environment. |
| `write_stdin` | Uses the thread/session's existing unified-exec process manager and internal process id. It is transport for an existing exec session, rather than an arbitrary host process or a new shell selector. |
| `apply_patch` | Handler resolves the turn environment and gets its filesystem. Runtime calls `apply_patch_with_options` with that same filesystem. A single-environment patch rejects an explicit environment-selection field; the client's sole environment is remote. |
| Planning, clock, sleep, context-budget helpers | Conditional builtins in the registry; these manipulate plan/session metadata, report time/context, or wait. They do not expose a filesystem, network, or process selector. User-interaction helpers may be directly exposed depending on model metadata; this client rejects unexpected server requests. |
| Image, browser, apps/plugins, permission request, subagents, web, dynamic tools | Disabled or absent under the verified client feature/config/selection gates. Code Mode exposure is generated from registered tools; it is not a separate unrestricted host-tool namespace. |
| MCP resource helpers | Conditional on the MCP snapshot's `has_servers()`. All configured entries must be independently disabled, have `runtimeStatus=disabled`, and expose zero tools/resources/templates with no server metadata or discovery error. This is not an active MCP server capability. |

`resolve_tool_environment` chooses the snapshot's primary environment when no
id is supplied. If an id is supplied, it searches **only that turn's selected
environments** and returns `unknown turn environment id` when absent. It does
not fall back to a local environment. `exec_command` returns an error if no turn
environment is available. Arbitrary workdir/path arguments cannot broaden the
outer namespace's mount or network access.

Code Mode tool names are assembled by iterating the existing registry and
filtering exposure. The trusted dispatcher resolves the named registered tool;
unregistered names return an unsupported-tool error. Enabling only the remote
Code Mode host does not by itself register local filesystem/network tools.

Evidence in `source-evidence.json` and `source-excerpts.txt`:

- `core/src/tools/spec_plan.rs`: shell tool construction 1036-1074, MCP helper
  gate 1089-1095, utility/patch/image gates 1099-1241, Code Mode inventory 786-837.
- `core/src/tools/handlers/mod.rs`: environment resolution 159-177.
- `core/src/tools/handlers/unified_exec/exec_command.rs`: selected environment
  and cwd/filesystem resolution 179-210.
- `core/src/tools/handlers/unified_exec/write_stdin.rs`: existing process manager
  dispatch 83-95 and transport-only comment 130-132.
- `core/src/tools/handlers/apply_patch.rs`: explicit environment rejection 626-636.
- `core/src/tools/runtimes/apply_patch.rs`: filesystem used for mutation 175-197.
- `core/src/tools/registry.rs`: registered-name lookup/error 537-556.

The selected remote executor constructs `RemoteProcess` and `RemoteFileSystem`.
The selected remote Code Mode host constructs `GrpcCodeModeSessionProvider`;
connection errors propagate in that branch. Local execution and local Code Mode
providers are separate branches that the client does not select. Source-backed
routing and negative-control canaries support this boundary; they are not a
proof against implementation defects in the pinned executables.
