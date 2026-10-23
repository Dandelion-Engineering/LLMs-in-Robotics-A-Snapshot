# Project candidate userland preparation

The original14 synthetic checks passed in official job781cc0f8. Build6ba3a543 then failed before copying or creating its output directory: the packaged Python sitecustomize link required `/etc/python3.12/sitecustomize.py`. This version adds only that package-owned configuration and two focused tests; these changes have not been executed. Root retains the failed attempt's official log/receipt and retired r2 evidence; the next fresh build uses candidate-linux-002. `source-version-001` retains the exact tested/failed-build Python/config bytes, reconstructed after the narrow edit and verified against every pre-edit hash. The active source guard uses only top-level `*.py`, so this historical subdirectory is not a live implementation dependency.

`package_userland.py` is the Windows queue entry point. It checks the installed queue child through the unchanged `release_runner.queued_job`, then launches Linux `userland.py`. It never submits or polls queue jobs, imports/unregisters a distro, runs apt, or changes host update settings. Build, verify and synthetic tests are separate queued invocations. A successful printed invocation is still subject to its official receipt.

`source-config.json` uses the completed inventory `ff805a67`: source `Ubuntu-24.04`, non-root `dandelion`, UID/GID1000, home `/home/dandelion`, shell `/bin/bash`. Build independently checks this account. The fresh target name selected by root is `LLMs-Robotics-Candidate-001`.

## Contents and identity

The installed dependency resolver selects the declared packages, recursively resolves installed `Depends`/`Pre-Depends` and alternatives/versioned providers, and includes native installed `Essential: yes` packages because Debian dependencies can assume them. Unsupported dependency syntax fails. Seeds include Python3.12, bubblewrap, libseccomp, bash/dash, coreutils, mount/util-linux and tzdata. No download or package configuration occurs.

Only selected package-owned `/usr` paths (including normalized `/bin`, `/sbin`, `/lib`, `/lib64` paths), their parent directories, and their license/copyright material enter the tar, with one explicit configuration dependency: `/etc/python3.12/sitecustomize.py`, owned by selected `libpython3.12-minimal`. The observed `/usr/lib/python3.12/sitecustomize.py` symlink points there; its exact package bytes are retained and hashed. This does not copy other `/etc` files. Source home, `/usr/local`, and `/usr/lib/wsl` are never copied. Every package must retain its copyright file. Links resolve lexically within the image and dangling/cyclic targets fail. All regular-file hashes, types, links, relevant modes and owners are retained. Tar member times are normalized to zero; actual installed package bytes are authoritative, not a promise of reproducibility from package version strings alone.

Generated minimal `/etc` fixes the non-root account, nss files, empty fstab/resolv, localhost hosts, and UTC timezone. `wsl.conf` disables systemd/custom service startup, Windows interop/path injection, GPU library injection/appendLibPath, automount ldconfig, generated hosts/resolv and Windows timezone injection **only in the project distro**. C/D remain automounted under `/mnt`. Linux candidate execution stays on CPU; the Windows-hosted model/GPU configuration is unchanged. No host update setting changes.

There is no opaque copied `ld.so.cache` or `ld.so.preload`; both must remain absent. Library loading relies on the coherent standard `/usr/lib` layout and must pass the actual sandbox tests. UTC comes from the selected tzdata package. The declared symlinks preserve the usr-merge layout.

Source package metadata, selected package listings, source contents/modes/links/owners, config, and host tool sources are compared before/after. Each file is also checked against its pre-copy hash while placed in the archive. Changes retain a failed/partial output and require a new output path. A change and restoration between observations cannot be ruled out. The builder does not stop apt or lock the host package manager.

The live verifier checks exact path sets and identity under `/usr`, `/etc`, `/bin`, `/sbin`, `/lib`, `/lib64`, `/home`, and `/root`; extra files fail. No WSL injection is silently excluded. The observed source `/usr/lib/wsl` is about10GB and is excluded from the package artifact; if it appears in the imported static scope, verification fails. Runtime `/proc`, `/sys`, `/dev`, `/run`, `/tmp`, `/mnt` contents and WSL root-level infrastructure are outside these static userland scopes. The shared WSL kernel/host remains a separately checked dependency. Verification runs as project-distro root solely to read root-owned0700 paths; candidate startup, shutdown, Python identity and sandbox tests continue as the non-root account.

## Queue payloads

From the project root, root can submit these payloads through its existing queue workflow. They have not been executed:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Environment Repair 001/userland-tools/package_userland.py" test --distribution Ubuntu-24.04

.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Environment Repair 001/userland-tools/package_userland.py" build --distribution Ubuntu-24.04 --config "Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Environment Repair 001/userland-tools/source-config.json" --output-dir "Long-Horizon Adaptive Robotics Expirement/Evidence/runtime-environments/candidate-linux-002"
```

The output parent must exist; the output directory must not. Expected files are `started.json`, `rootfs.tar`, `manifest.json`, and `host-invocation.json`; an interrupted or failed attempt may have a partial archive and `failure.json`. The manifest binds the archive, complete image entries, static scopes, selected packages/dependency choices/copyrights, source-copy hashes, explicit config and owning queue job. The official receipt must succeed and `sources_unchanged`/`inputs_unchanged` must both be true before using the artifact.

After successful build and exact archive hash verification, root verifies the target distro name and its chosen install directory are absent, then uses a separate controlled import of **that archive**:

```powershell
wsl.exe --import LLMs-Robotics-Candidate-001 "<fresh-project-owned-install-directory>" "<absolute-candidate-linux-002-rootfs.tar>" --version 2
```

Do not overwrite an existing distro/directory or unregister one to retry. Import is intentionally not automated here. WSL configuration and import behavior are documented by [Microsoft import guidance](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro) and [per-distro configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config).

Then queue, with the actual manifest SHA from the successful build:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Environment Repair 001/userland-tools/package_userland.py" verify --distribution LLMs-Robotics-Candidate-001 --manifest "Long-Horizon Adaptive Robotics Expirement/Evidence/runtime-environments/candidate-linux-002/manifest.json" --manifest-sha256 <exact-manifest-sha256>
```

The existing freezer `--probe-spec` can retain the same verifier as an additional probe (direct Linux invocation inside its owning queued freeze, not nested queue ownership):

```text
C:\Windows\System32\wsl.exe --distribution LLMs-Robotics-Candidate-001 --user root --exec /usr/bin/python3 -I -B <absolute-/mnt/c/.../userland.py> verify --manifest <absolute-/mnt/c/.../manifest.json> --manifest-sha256 <exact-sha256> --seconds 25
```

Use probe timeout30s; the verifier has an internal25s deadline and stable successful JSON. If it cannot finish, it fails rather than skipping files. Retain exact tool/config/archive/manifest refs in the new release closure. Required `candidate_python` must target the project distro as dandelion; `candidate_isolation` must hash actual bubblewrap bytes and report its version, because0.9.0 did not distinguish the observed patch update. Keep the GPU probe on Windows. Full userland verification binds libc, loader, stdlib, extensions and seccomp as well.

## Required validation, still pending

The16 synthetic tests cover dependency alternatives/providers/versions/Essential closure, usr-merge and private exclusions, image link containment/cycles, the one package-owned Python configuration link and target tampering, generated config, exact live tree and content/mode/link/owner/path mutations, cache/WSL additions, manifest tampering and the deadline. They do not execute apt, build/import a rootfs or run robot physics.

After import, run actual Runtime sandbox/adversarial/rlimit/persistence/termination tests as dandelion, compare unchanged candidate policy/IPC fixtures, and measure actual persistent/ephemeral restart timing and a representative full-cell timing check. A changed launch environment does not inherit old restart timings. Preserve all physical-class sources, qualification loader dependencies, model assets and the original Windows Runtime location; a fresh code/environment release is required, but unchanged geometric qualification is not automatically invalidated by this environment-only repair.
