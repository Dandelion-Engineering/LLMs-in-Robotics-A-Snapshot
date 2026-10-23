# Session 19 queue accounting

`collect.py` reads the official shared queue's metadata for this repository and
project, limited to jobs submitted from 2026-09-30T16:54:00Z onward. Each named
snapshot is exclusive and immutable. It never opens queue logs or attempt
outputs, and it does not infer model-call counts, billing, task outcomes or
qualification from queue status.

[Checkpoint 001](checkpoint-001/summary.json), captured at 20:05 UTC, contains
25 jobs: 18 succeeded, six failed and one running. The 24 completed jobs occupied
4,209.753 seconds (70.16 minutes). The active job's duration is excluded and
remains unavailable. Summed child occupancy is distinct from session elapsed
time and model inference time. The original full job records are retained in
[official-jobs.json](checkpoint-001/official-jobs.json).

This is an ongoing-session checkpoint. A later snapshot must preserve it and
authenticate the then-current official state. Session15 accounting remains an
unchanged historical record with its original scope and model-count limits.
