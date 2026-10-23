# Engineering Investigation 006

This presentation entrypoint repairs a compatibility error in the frozen 005 analysis-provenance reader. The production collector records the adopted annex as a path and SHA-256; the analyzer also records its measured byte count. Reader 005 compared the whole dictionaries and rejected those different shapes even though they identify the same file. Both old comparisons and the failed official build are retained.

Reader 006 independently verifies each annex reference and compares its resolved file identity. Declared byte counts remain checked. Changed paths, hashes, file contents, absent references and false byte counts remain errors. The original statistical report and its source/receipt checks are unchanged.

The 006 builder imports the original 005 evidence readers from their original locations. Their method inventories and expected producer receipts still identify **Engineering Investigation 005**, **Release Analysis 005** and **Runtime Recovery 001**. It does not relabel old evidence as produced by 006. `upstream-source-bindings.json` fixes all original 005 source files; the builder checks them before importing and again before writing the page. New presentation source references are embedded separately in the snapshot and shown in its provenance panel.

Rendering reuses the original 005 assets. Three static navigation links are resolved relative to the generated page so that a nested site directory reaches the actual experiment documents. No trace, outcome, denominator, exclusion, unknown value, numerical method or candidate is changed.

`validate_reader.py` is a queue-only validation entrypoint. It runs the unchanged 005 regressions and new 006 regressions in separate processes, reproduces the old refusal against the completed analysis, then verifies that the new reader accepts the same authenticated inputs without changing estimates. Passing validation and a separate official build receipt are required; browser verification remains a separate step. Validation and build artifacts, receipts and completion records live under the original r4 manual-series journal and fresh Evidence output directories.

The presentation repair authorizes no physical rerun, new architecture, policy tuning, alteration of the adopted annex or rewriting of an earlier source. The fixed twelve trace slots and their 2 Hz observation / 5 Hz motion display rates remain in force.
