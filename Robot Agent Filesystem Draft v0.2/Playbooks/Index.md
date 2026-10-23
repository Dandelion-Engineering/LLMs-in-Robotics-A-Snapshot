# Playbook Index

This is the canonical compact catalog of reusable higher-level procedures and capabilities available to the robot.

Read this index at the beginning of every agent invocation. Do **not** load every playbook or program into context at startup. Use the index to know what higher-level capabilities exist, then open only the relevant playbook and program when the current task calls for them.

Primitive low-level controls are not cataloged here; their agent-facing contracts live in `RobotDetails.md`.

## Default playbooks

Default playbooks are prepared during deployment setup by the operator or deployment agent (for current experiments, typically Development Codex). They describe reusable higher-level procedures that ship with the robot or deployment.

A default playbook may point either to a filesystem-resident program in `Programs/Default/` or to a built-in higher-level capability implemented inside the robot software stack.

| Playbook | Purpose | Playbook path | Program / implementation | Scope | Status |
|---|---|---|---|---|---|
| _None populated yet_ |  |  |  |  |  |

## Learned playbooks

Learned playbooks are created when Robot-Codex develops a procedure or program during operation and judges it reusable beyond the current episode.

| Playbook | Purpose | Playbook path | Program / implementation | Scope | Evidence / status |
|---|---|---|---|---|---|
| _None populated yet_ |  |  |  |  |  |

## Index maintenance

- Keep this file compact. It is a discovery layer, not the full procedure.
- Add an entry only when a playbook has been created or materially revised.
- Do not index throwaway scripts merely because they exist.
- Preserve whether the playbook is default or learned.
- A learned playbook should point to the session evidence that justified promoting it.
- If a playbook becomes obsolete, mark or supersede it rather than silently erasing provenance.
