# V27 frozen source comparison

Source-only verification: dev082 (916 entries) to dev083 (930). Exact archive members, bytes, current sources and all624 original sources match their identities.

899 shared unchanged; 4 changed; 27 additions; 13 omitted entries remain on disk unchanged.

Harness/runtime behavior is byte-identical except the exactly checked inventory supplier. Assessment changes are confined to the prepared-result label parser and declared tests. New lineage, method and checks030 receipts are bound separately. This is not qualification.

[Complete receipt](v27-source-change-inventory-001.json)

Changed shared sources:

- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/prepared_result_segments.py` — prepared_result_label_parser
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_prepared_result_segments.py` — assessment_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_prepared_startup_segments.py` — assessment_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/raw_event_preflight_v2.py` — inventory_only_supplier
