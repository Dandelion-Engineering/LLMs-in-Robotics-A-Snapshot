# Prospective report compatibility for diagnostic003

This bookkeeping-only change extends the report reader and its independent QA with the exact declared single-interrupt-diagnostic-v3 / shutdown-diagnostic-003 / dev091 identity, dispatch paths and frozen source bindings. It preserves the existing v1/v2 contracts and every production assessment, model, task and launch rule. A failed diagnostic remains unassessed, task-unknown, non-scorable, with no model-call count or qualification inferred from its outputs.

Scope: investigation/qualification_report.py, test_qualification_report.py, qualification_qa.py and test_qualification_qa.py only, plus this development packet. Read SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md before implementation; wait for stable wrapper identity pins. These report files are outside the frozen runtime inventory. No history append, report generation, empirical output access, queue/native/model invocation or source freeze is performed here.

Retain exact before sources, canonical history121 and all19 existing exports. Run synthetic positive and adversarial metadata fixtures plus the existing report/QA regression suites. Preserve any failed check and each subsequent material correction under distinct records. Validate the unchanged legacy dispatcher after removal of only the additive v3 branch.
