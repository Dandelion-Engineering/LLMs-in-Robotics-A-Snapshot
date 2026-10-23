# `closeout.py`

`closeout.py` is the final operation of an agent session. It serializes stage,
commit, and any configured push under a repository-local lock and commits an
explicit path set so parallel agents do not adopt one another's files.

## Before closeout

Complete all of the following first:

- finish or hand off the work;
- update or close the work claim;
- write the session report;
- rewrite the context summary;
- record needed handoffs or human dependencies;
- run the final chat inbox check;
- respond to any message that materially changes the closeout state.

Once those are settled, preview the exact paths:

```shell
python -B Tools/closeout.py --agent Claude --session 4 --dry-run \
  --paths "agents/Claude" "Work/Active/example.md" "src/example.py"
```

Review the preview. Then run the same exact command without `--dry-run`:

```shell
python -B Tools/closeout.py --agent Claude --session 4 \
  --paths "agents/Claude" "Work/Active/example.md" "src/example.py"
```

For a moved file, include both source and destination paths. A one-sided move is refused.

## `--all`

```shell
python -B Tools/closeout.py --agent Claude --session 4 --all
```

Use `--all` only when the session is the sole writer and the entire worktree has been inspected. In parallel work, explicit `--paths` is the default.

## Safety boundary

The tool:

- uses a scratch index for dry runs;
- excludes its live lock from the commit;
- refuses one-sided moves;
- never breaks a lock automatically;
- commits successfully without pushing when the repository has no remote;
- refuses before committing when a remote exists but the current branch has no
  upstream, rather than guessing a destination;
- never force-pushes, amends, rebases, merges, resets, or resolves conflicts;
- and stops on remote divergence for explicit coordination.

## The hard stop

A successful non-dry-run closeout commits and, when an upstream is configured,
pushes. A local-only repository is reported explicitly and the commit remains
local. **Either successful path is the end of the session.**

Do not check chats, edit files, update reports, or perform more work afterward.
Anything discovered after closeout belongs to a new session.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | preview completed, or closeout commit completed with any configured push |
| `1` | refused or failed; inspect the printed repository state |
| `4` | closeout lock remained busy until timeout |
