# Session10 enforced runtime boundary

This additive copy leaves all Session9 implementation and failures unchanged.
The trusted Windows parent owns existing ChatGPT authentication, a fixed host
destination and one frozen robot capability per invocation. It must validate
`gateway_policy.validate_request` and `validate_response` too, refuse redirects,
and read one byte beyond the response bound to detect truncation. The guest gets
no operator credential or lifecycle route. Restart creates a new broker/token;
retired brokers never load current credentials from a mutable endpoint file.

## Parent interfaces

- `runtime_layout.prepare_workspace(run, files)` creates a fresh Linux runtime
  beneath `/var/tmp/robot-codex-session10/<run-id>`. It refuses existing runs.
  `files` is the trusted mapping of relative POSIX names to text. Reuse the
  resulting workspace across invocations; preserve notes/programs/continuity.
- `linux_entry.py MODE --workspace PATH --socket PATH [--codex BIN]
  [--codehost BIN] [--identity-file PATH]` preserves the Session9 call shape.
  Socket and process identity must be direct children of the same dedicated run.
- `unix_broker.py SOCKET --workspace PATH` prints ready JSON then one validated
  request line at a time to the trusted parent; parent replies with exactly
  `{status, body}`. Request body max 64 KiB, response body max 1 MiB, encoded IPC
  request/response frames max 512 KiB/8 MiB. Destination is absent from the wire.
- `retirement.retire(process, identity_path, evidence_path)` preserves the
  existing async interface and requires recorded PID/start-tick and namespace
  retirement evidence. Only the new durable runtime root is accepted.

`gateway_policy.py` permits exact status/history/command/observation/continuity
reads and command/observe/handback/continuity writes. History has canonical
nonnegative integer cursor and 1..200 limit. Images are only
`/observation/overhead-<positive integer>.png` JSON with base64 data. Every
operator, restart-agent, run-program, unknown or encoded path is denied before
forwarding. The WSL broker repeats the policy even for direct socket callers.

## Atomic continuity and retention

The public `Continuity.md` is a fixed read-only-root symlink to
`.continuity/Continuity.md`. Only the `.continuity` directory, `notes` and
`programs` are writable persistent mounts. To update locally, resolve the public
symlink, create a sibling temporary file in `.continuity`, fsync it, replace the
backing filename and fsync the directory. Replacing the public symlink remains
denied, and the workspace root remains read-only.

Prefer protected `POST /continuity`: the host commits its protected durable note
first; WSL mirrors it with descriptor-relative non-following atomic replacement,
verifies bytes/hash, then returns success. An interrupted mirror is an unknown
receipt, recoverable using authenticated `GET /continuity` and trusted parent
reconciliation. This preserves both local atomic edits and protected restart
authority without making instruction files writable. No helper follows a
guest-created backing-file symlink while writing. Exporters must likewise reject
or explicitly handle guest symlinks; this module does not implement export.

`/var/tmp` avoids Session9's boot-cleared `/tmp`; raw workspace survives ordinary
namespace exit and broker teardown. The parent must still export and hash files
in `finally` and verify persistence; this layout alone is not retention evidence.
Full-host power loss, disk-full, administrator changes and whole-machine resource
exhaustion remain outside these checks.

## Bounded generated Python path

`python3 /program_runner.py programs/name.py --timeout 30` snapshots at most
64 KiB into a kernel-sealed memfd before Python starts. It permits at most 60
seconds wall time, retains at most 1 MiB combined stdout/stderr, sets per-child
512 MiB address-space/8 MiB file/128 descriptor/60 CPU-second limits. Before
`Popen`, it creates and fsyncs an append-once `<id>.admitted.json` containing exact
source bytes/hash and limits, then fsyncs the directory entry. Its separate
`<id>.json` final record retains output, disposition, descendant retirement and
the admission-file hash. Admission with no final record means execution outcome
unknown after interruption; it never establishes completion or even process
launch. Notes remain agent-writable, so mode0400/append-once behavior prevents
accidental runner rewrites rather than certifying resistance to same-identity
tampering; trusted parent retention must preserve evidence. As a Linux subreaper
it also captures detached descendants;
signals use pidfds matched against process start ticks. Failure to establish
retirement is a failed run requiring whole-invocation retirement by the parent.

This runner is a bounded execution convenience within the enforced invocation,
not a second permission boundary. Agent shell/Python access remains available
and can execute code with the same restricted filesystem, network and bounded
robot gateway. There is no privileged `/run-program` service. Invocation-wide
parent deadlines and namespace retirement remain necessary. Entry sets inherited
64 MiB file/1024 descriptor/1800 CPU-second per-process limits; no claim is made
of aggregate fork, memory or per-program accounting across arbitrary raw shells.

## Validation

`python -B test_boundary.py` runs pure policy/mount tests everywhere and short
Linux tests for atomic continuity, backing-symlink safety, sealed program output,
output overflow, a timeout with detached child retirement and forced SIGKILL at
the Popen boundary proving admission survives with no false final. `canary.py` keeps
the previous read/write, protected paths, IPv4/IPv6/UDP, child inheritance and
nested-userns coverage, and adds atomic continuity, root/public-link denial,
operator/alias/method denial and direct IPC denial. It issues only status reads;
no actuator command is submitted. Actual gateway/model/namespace qualifications
are retained by the parent outside this source directory.
