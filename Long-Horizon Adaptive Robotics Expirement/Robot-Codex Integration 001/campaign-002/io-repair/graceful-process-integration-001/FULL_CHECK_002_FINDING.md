# Preserved second regression failure

The harness passed all 457 tests. The assessment suite ran 567 tests with 14 errors, all because two synthetic source-archive builders omitted the three shutdown helper files now required by the exact new bootstrap identity. The production reader rejected the incomplete archives as designed. Add those exact helper files to those test archives; preserve the reader and all missing/changed/duplicate rejection tests. This failed queue receipt remains failed.
