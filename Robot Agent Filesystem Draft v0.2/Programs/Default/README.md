# Default Programs

This folder is reserved for reusable higher-level programs supplied with the robot or prepared during deployment setup.

For current experiments, Development Codex can populate it from the robot/simulator's supplied reusable routines when those programs are intended to live in the agent filesystem.

This folder does **not** contain the implementation of low-level controllers, device drivers, joint servos, simulator internals, or other primitive robot-control code. Those implementations belong to the robot or simulator software stack. Their agent-facing contracts are documented in `RobotDetails.md`.

Each reusable default program should have a corresponding semantic description in `Playbooks/Default/` and an entry in `Playbooks/Index.md`.
