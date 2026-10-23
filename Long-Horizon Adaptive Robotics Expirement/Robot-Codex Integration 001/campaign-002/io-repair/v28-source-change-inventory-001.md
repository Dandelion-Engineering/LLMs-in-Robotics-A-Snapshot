# V28 frozen source comparison

Source-only verification: dev086 (935 entries) to dev087 (944). Exact archive members, bytes, current sources and all624 original sources match their identities.

919 shared unchanged; 3 changed; 22 additions; 13 omitted entries remain on disk unchanged.

Harness/runtime behavior is byte-identical except the exactly checked inventory supplier. Assessment changes are confined to the pilot retirement inventory wrapper and its tests. Existing lifecycle/retirement criteria are unchanged. New lineage, method and checks031 receipts are bound separately. This is not qualification.

[Complete receipt](v28-source-change-inventory-001.json)

Changed shared sources:

- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/assess.py` — pilot_retirement_inventory_adapter
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/assessment/test_assess.py` — assessment_regression
- `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/raw_event_preflight_v2.py` — inventory_only_supplier
