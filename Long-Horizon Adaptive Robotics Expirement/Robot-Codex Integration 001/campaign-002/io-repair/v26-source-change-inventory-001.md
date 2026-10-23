# V26 frozen source comparison

Source-only verification passed: dev078 (905 files) to dev079 (911 files). Both archives have exact member sets, no duplicates, and every member matches its snapshot. All new current sources and all 13 omitted old entries were checked.

- 878 shared sources unchanged; 14 changed; 19 inventory additions.
- All 624 original protected sources match both snapshots, both archives and current files.
- The mirror runtime changed for request capture and epoch revocation. Its successful publication script, file mapping, Linux publication call and setup/restore method remain AST-identical.
- Named native/physical sources, model templates and requested model/effort/authentication/bootstrap metadata remain unchanged.
- Publisher parity, final lineage, root integration, operator checks and dev079-bound checks029 plus its complete production source state are separately bound.

This is not qualification, a task outcome or an empirical reassessment. Inventory membership is not evidence of file creation or deletion. Historical artifact/prefix preservation remains a separate command.

[Complete hash-bound receipt](v26-source-change-inventory-001.json)

Changed shared sources:

- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/assess.py` — independent_assessment
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/assess_smoke_v2.py` — independent_assessment
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/literal_read_segments.py` — independent_assessment
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/prepared_result_segments.py` — independent_assessment
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/retained_reads.py` — independent_assessment
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_assess.py` — test_fixture_or_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_prepared_result_segments.py` — test_fixture_or_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_prepared_startup_segments.py` — test_fixture_or_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_retained_reads.py` — test_fixture_or_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_smoke_v2.py` — test_fixture_or_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/raw_event_preflight_v2.py` — source_inventory_or_qualification
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/runtime.py` — protected_mirror_request_and_epoch_revocation_evidence
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/test_native_owner_bootstrap.py` — test_fixture_or_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/test_transport.py` — test_fixture_or_regression
