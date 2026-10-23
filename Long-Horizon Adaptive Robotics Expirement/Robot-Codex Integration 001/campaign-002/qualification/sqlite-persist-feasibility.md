# Conditional rollback-journal repair option

This is a prospective design note written while host-probe-004 runs. No new diagnostic output has been read and no database setting has been changed. It is not a qualification result.

The existing recorder uses one connection, `journal_mode=DELETE`, `synchronous=FULL`, and the owning `FutureEvidence` lock. An image call commits its availability record and any selected blobs before returning. The prospective option is to retain these transaction and visibility boundaries while changing only journal management, if probe-004 actually localizes the delay there.

SQLite documents `PERSIST` as zeroing the rollback-journal header at commit rather than deleting the file. This can avoid metadata work; it does not promise a latency bound. `FULL` must remain verified. SQLite's general rollback/FULL durability caveat also prevents claiming universal power-loss durability for either the current or proposed path. `journal_size_limit` bounds the file left after a transaction, not its peak. [Official journal and synchronization documentation](https://www.sqlite.org/pragma.html#pragma_journal_mode).

SQLite says a persistent journal must be retired through its own DELETE-mode transaction, not by manually deleting a possibly hot journal. A crash may leave recovery dependent on that sidecar. [Atomic commit and journal reuse](https://www.sqlite.org/atomiccommit.html#persistent_rollback_journals).

Project-specific requirements for any later implementation:

- Set and read back the mode before measured physics, without altering SQL contents, transaction grouping, lock ownership, encoding, image selection, quotas or sensor publication order.
- Retain FULL synchronization and fail on unsupported or changed settings. Keep the existing single connection; do not introduce concurrent writers or checkpoints.
- Account for main database, rollback journal and finalization overlap in the existing evidence budget. Add bounded sidecar accounting without placing a recursive directory walk on the physics path.
- Keep main database plus journal together on failure. Before normal compression, use SQLite to finish a DELETE-mode transaction and verify a clean standalone database. Preserve the original hash, gzip restore verification and durable manifest publication.
- Test exact logical contents and retained bytes, reader compatibility, settings readback, error propagation, capacity and crash recovery before a new frozen full-duration diagnostic.

Unlike WAL, this option does not introduce a WAL-format database header or checkpoint pipeline. That is an implementation-scope inference from the original recorder and SQLite documentation, not evidence that PERSIST fixes the observed host stall. If probe-004 instead identifies locking, compression or another operation, this option is irrelevant.
