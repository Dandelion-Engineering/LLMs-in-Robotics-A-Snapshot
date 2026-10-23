# Graceful process-drain candidate

[Implementation and evidence contract](IMPLEMENTATION.md) describes the
prospective ordering correction and its unchanged failure requirements.
[Fixture declaration](DECLARATION.md) predates the owned Windows comparison.

- `controls-001/receipt.json`: all8 fixed socket/process controls matched their
  declared expected outcomes; the pooled baseline timed out, whereas ordinary
  process shutdown allowed genuine EOF and exact bytes in the candidate case.
- `tests-001.txt`: all11 controller/bridge integration and adverse controls pass.
- `reader-tests-001.txt`: all9 full transport-reader and source/identity/order
  controls pass. Existing EOF, endpoint bytes and native requirements still fail
  corrupted fixtures. The real runtime overlay restores its methods on exit.
- `controller-derivation.json` and `reader-derivation.json`: exact substitutions
  from retained originals. Neither production file was changed.
- `readiness.json`: no-model result bindings and verification of all986 dev097
  inputs. Native behavior and full qualification remain unproven.

Next: one separately frozen Diagnostic006/dev098 under its own declaration.
Do not run a control or native attempt again under an existing identity.
