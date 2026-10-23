# Native display-only build feasibility

A same-version Windows display repair is plausible from the pinned source, but **the required native build environment is not currently available in the checked locations**. This is a setup gap, not permanent impossibility. No installation, clone, dependency resolution, build, patch, model invocation or queue job was performed. The existing-native raw-output observability investigation can proceed without this setup and is the narrower current alternative.

The official `rust-v0.157.1` annotated tag resolves to commit `36650394c5b38c2990ccf2a3457165ca3e9d9726`. Its workspace version is `0.157.1`, Rust toolchain is **1.95.0**, and edition is 2024. The tag/version relationship does not attest the installed executable's source bytes. See the retained [source receipts](source-receipt.json), [dependency and tag receipts](source-receipt-002.json), [tag object](tag-object-receipt.json) and [native Windows release workflow](.github__workflows__rust-release-windows.yml).

| Prerequisite | Current observation |
|---|---|
| Cargo, rustc, rustup | Absent from PATH; `.cargo` and `.rustup` roots absent |
| Native MSVC/SDK environment | `cl`, `link`, `clang-cl`, VS roots, `vswhere`, standard Windows SDK Lib and `C:/BuildTools` absent |
| Dependency caches | Standard Cargo registry and git caches absent |
| CMake, Ninja, compiler helpers | Not found; exact minimal transitive needs not resolved |
| Standalone protoc | Absent, but protocol build uses a vendored protoc dependency |
| just, dotslash, nextest | Absent; convenience/test tools are secondary to compiler availability |
| Git, Node, Python | Available |
| Hardware | 8 cores/16 threads, ~31.67GiB visible RAM; 15.76GiB free memory and 394.32GiB free disk at observation |

The full workspace lock has **1,468 package entries**, including 1,297 registry and 16 git-sourced entries. Those are workspace counts, not a resolved minimal app-server dependency count. No cold-build runtime or peak-disk estimate is established. The official Windows workflow notes builds can exceed an hour; that is not a prediction for this computer.

The [pinned build guide](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/docs/install.md) describes Cargo-based builds and recommends focused tests. It is generic and lists Windows via WSL2. The [Windows release workflow](https://github.com/openai/codex/blob/36650394c5b38c2990ccf2a3457165ca3e9d9726/.github/workflows/rust-release-windows.yml) independently confirms a native `x86_64-pc-windows-msvc` Cargo build using an MSVC SDK environment. A Linux/WSL binary would be a different deployment.

## Binding a later candidate

A few changed display-source lines still require a compiled binary and its dependency graph. If separately declared later, pin commit, lockfile, dependencies, compiler/linker/SDK, target, flags and features; retain exact build/test records and output hashes. Give the custom variant a distinct identity. Keep instruction templates, model settings, bootstrap, permissions, isolated remote route, canaries and thresholds unchanged and byte-checked. Match the campaign launcher: `codex-cli` builds `codex`, while standalone `codex-app-server` is a separate target and is not automatically interchangeable.

Focused tests should cover output preceding display subscription, short nonempty transcript versus complete fallback, complete/equal transcripts, truncation, and exit/closed ordering. An isolated no-model remote-route parity check and complete fresh qualification would still be necessary. Dependency build scripts execute code, so a prospective bounded build environment must avoid campaign credentials and automatic model launches. The current inspection did not execute them.

The repository declares Apache-2.0; its retained [LICENSE](../native-output-source-001/LICENSE) and [NOTICE](NOTICE) include the applicable upstream and Ratatui attribution. Preserve notices and identify modifications in a derivative. SDK licensing, third-party notices and official code-signing provenance are separate considerations; no redistribution or signing bypass is proposed.

## Alternatives and limits

Continue examining prepared native tool-result events and exact call/result binding on the existing code-mode path. This may improve observability without a binary change, but it is not yet proof of a complete qualifying read and cannot promote smoke008 retroactively. A later controlled CI/native build is another possibility if its source, environment and binary identity can be bound. A newer release or Linux binary broadens the change and does not establish this same-version one-fix candidate.

Only named commands and known tool/cache locations were checked. Nonstandard or remote toolchains remain unknown. No WSL compiler inventory or source/dependency build was attempted. Smoke008 remains failed. The [machine observations](machine-observations.json), [path observations](local-path-observations.json) and [full hash-bound analysis](analysis.json) record the exact scope and inputs.
