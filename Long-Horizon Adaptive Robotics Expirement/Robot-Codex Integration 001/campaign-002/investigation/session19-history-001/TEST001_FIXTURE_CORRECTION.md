# Initial synthetic test fixture failure

The first local synthetic-only run executed 114 tests in 8.456 seconds and
failed one new test. Importing `CompanionIntegrity` directly exposed its 107
existing tests to discovery. The new three-branch loop also retained a
`queue_completion_contract` field from its previous Diagnostic006 fixture when
constructing the failed-boundary fixture. The strict report reader correctly
rejected that contradictory row as an unsupported completion.

Use a module import for the reused fixture methods and reset row metadata at
each construction. No report predicate, runtime or empirical verdict changes.
The initial failed test result remains recorded here; fresh output is separate.
