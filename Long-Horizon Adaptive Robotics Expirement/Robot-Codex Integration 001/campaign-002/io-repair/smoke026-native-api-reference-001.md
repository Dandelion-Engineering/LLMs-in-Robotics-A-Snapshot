# Native lifecycle API reference — diagnostic context only

Checked 2026-09-29UTC using the OpenAI Docs skill. [The official App Server documentation](https://learn.chatgpt.com/docs/app-server#unsubscribe-from-a-loaded-thread) describes thread/unsubscribe as removing a connection subscription; a subsequent thread/closed notification concerns thread unloading after inactivity. The documented lifecycle is not a socket-level receipt of all bytes or TCP FIN. The searched page exposes no dedicated graceful socket shutdown method. That bounded search result is not a claim that no internal API exists.

The existing experiment explicitly sets its previously declared zero unload delay; current general documentation's default grace period does not supersede frozen installed-source/configuration evidence. No model, configuration, RPC or deadline was changed here. No new credentials or platform API were used.

Smoke026's independent admission is unavailable because the official queue failed. The native source packet and retained thread/closed receipt can inform a diagnostic hypothesis only; they do not establish the installed binary's exact socket closure cause. Preserve genuine EOF and all existing acceptance criteria. Prospective bounded socket-operation metadata and a synthetic Windows loopback control can resolve more than another unchanged qualification run.
