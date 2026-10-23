# Boundary031: missing assessment helper import

The sole queue job `20260930T194104177341Z-36f033a5` failed with integer
exit 1. V31 and its wrapper terminated without launching Smoke029 or either
Pilot028. Native030 passed its separate 66 checks. No scored slot started.

Bounded diagnostic inspection found `ModuleNotFoundError: No module named
'completion_chronology'` when the boundary runner loaded `retained_reads.py`
by file path. The V31 reader had added this sibling-module dependency, while
the standalone boundary runner configured only its harness import path. The
combined regression process had assessment imports available; it did not
exercise this fresh-process entry condition.

The synthetic guest control and handback processes each retained exit 0.
All four executor namespaces reported qualified retirement; the codehost
probe had not begun. Runtime cleanup and retention were recorded clean.
These failed-queue records are diagnostic only. Boundary031 remains invalid
with task outcome unknown; they do not qualify any stage.

Repair the standalone boundary import context and test it in an isolated
Python subprocess. No protocol or model change is indicated. V31 stays
stopped, and a new source revision requires fresh complete qualification.
