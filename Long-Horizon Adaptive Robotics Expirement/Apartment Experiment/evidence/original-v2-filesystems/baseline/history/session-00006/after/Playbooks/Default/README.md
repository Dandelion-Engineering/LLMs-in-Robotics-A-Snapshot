# Default Playbooks

This folder contains semantic playbooks for reusable higher-level capabilities supplied with the deployed robot or prepared during deployment setup.

For current experiments, Development Codex can populate this folder after inspecting the robot or simulator, its supplied reusable programs, and its documented capabilities.

Default playbooks are **not** low-level controller implementations. Primitive robot actions and their usage contracts are documented in `RobotDetails.md`.

A default playbook may point to:

- a reusable program in `Programs/Default/`;
- a stable higher-level capability exposed by the robot software stack;
- supporting files required to invoke that capability correctly.

Use `../PlaybookTemplate.md` for new playbooks and register them in `../Index.md`.
