# Proposed programs

This directory is writable for proposed code. Do not execute agent-written programs in this binding until separately authorized: a version-pinned bounded program runner and its qualification are unavailable. Shell/Python can technically execute files; this instruction is not an interpreter restriction. The common gateway checks actuators; launcher isolation needs separate qualification before operational use.

`observe_once.py` demonstrates the read-only stdlib client API. It reads public status once with no actuation. Its calls are exercised against a fake HTTP service in `client-tests/`; this is not live program execution, rehearsal or physical outcome evidence.

Future programs may use loops and conditions through the common gateway. Do not modify a running program in place. A real executor must pin code/dependencies, record program/action links, bound resources and implement cancellation. Preserve version, reason, inputs and evidence; code checks do not establish recovery performance.
