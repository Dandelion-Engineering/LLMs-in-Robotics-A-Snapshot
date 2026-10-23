# Work Coordination

`Work/` prevents simultaneous agents from writing overlapping paths.

It is deliberately small. It is not a project manager, approval system, issue tracker, or permanent ownership registry.

## Lifecycle

```text
Work/
├── Active/    current write claims
├── Done/      completed claims and outcomes
└── Dropped/   abandoned claims and reasons
```

Use `Tools/work.py` for claim operations. Detailed commands are in `Tools/work.md`.

## The claim rule

- A claim reserves repository-relative paths currently being written.
- Read-only inspection needs no claim.
- Claims do not reserve ideas, subjects, or permanent ownership.
- Two active claims may not overlap.
- One agent is the live lead for a claimed scope; collaborators may be named.
- Chat transcripts are outside work claims and are appended through `Tools/chat.py`.
- A claim grants no human-only, safety, legal, financial, credential, publication, external-action, or other project authority.

The tool coordinates whole paths. If two agents need to change the same file, use one live lead, transfer the claim, or work sequentially.

When work completes, close it. When the project no longer needs it, drop it with a reason. Preserve the record either way.
