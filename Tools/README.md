# Collaboration Station Tools

This directory contains standard-library utilities for shared mechanical operations that are unsafe or tedious to manage by convention alone.

| Tool | Purpose | Documentation |
|---|---|---|
| `chat.py` | Let humans post interactively; let agents discover, append to, verify, and wait on active chat transcripts safely | [`chat.md`](chat.md) |
| `work.py` | Atomically open, inspect, transfer, close, and drop live write claims | [`work.md`](work.md) |
| `closeout.py` | Serialize path-scoped Git stage/commit and any configured push for parallel agent sessions | [`closeout.md`](closeout.md) |

Run `<tool> --help` for exact current command syntax.

These tools provide mechanics, not judgment. They prevent lost messages, overlapping writes, and mixed-attribution commits. They do not approve work, decide scientific claims, or replace the human director's authority.

## Tests

The scaffold includes tests for the three standard tools:

```shell
python -B Tools/test_chat.py
python -B Tools/test_work.py
python -B Tools/test_closeout.py
```
