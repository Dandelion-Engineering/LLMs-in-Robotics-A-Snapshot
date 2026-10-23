# `work.py`

`work.py` manages active write claims atomically.

The tool exists because parallel agents can otherwise inspect the same empty `Work/Active/` directory and both create overlapping claims before either sees the other. This is a mechanical concurrency problem, not a teamwork or approval problem.

A claim reserves paths being actively written. It does not reserve ideas, subjects, read-only inspection, or permanent ownership.

## List active claims

```shell
python -B Tools/work.py list
```

## Open a claim

```shell
python -B Tools/work.py open \
  --agent Claude \
  --session 4 \
  --name "Build data loader" \
  --purpose "Create the loader used by the next pipeline stage" \
  --paths "src/loader.py" "tests/test_loader.py"
```

Add collaborators when useful:

```shell
  --collaborators Codex
```

The tool normalizes repository-relative paths and refuses absolute paths, `..` traversal, duplicate names, and overlap with an active claim.

Directory and file claims overlap when one path contains the other. To keep the rule mechanically reliable, the tool coordinates whole paths rather than line ranges. When two agents need the same file, use one live lead or work sequentially.

## Inspect one claim

```shell
python -B Tools/work.py show "build-data-loader"
```

The identifier is the Markdown filename stem shown by `list`.

## Transfer the live lead

```shell
python -B Tools/work.py transfer "build-data-loader" \
  --from-agent Claude \
  --to-agent Codex \
  --session 5
```

Transfer is coordination, not approval.

## Close completed work

```shell
python -B Tools/work.py close "build-data-loader" \
  --agent Codex \
  --session 5 \
  --outcome "Loader is integrated and available to the pipeline"
```

This appends the outcome and moves the record from `Work/Active/` to `Work/Done/`.

## Drop work

```shell
python -B Tools/work.py drop "build-data-loader" \
  --agent Claude \
  --session 4 \
  --reason "The project chose a different input format"
```

This moves the record to `Work/Dropped/` while preserving why.

## Verify the active set

```shell
python -B Tools/work.py verify
```

This checks metadata, path normalization, unique identifiers, and pairwise non-overlap.

## Git closeout for moved claims

When `close` or `drop` moves a record, pass both lifecycle paths to `closeout.py`, for example:

```shell
--paths "Work/Active/build-data-loader.md" "Work/Done/build-data-loader.md"
```

## Runtime lock

Mutations use `Work/.work-tool.lock`. The lock is ignored by Git. The tool never breaks a lock automatically; a stale lock must be inspected before manual removal.
