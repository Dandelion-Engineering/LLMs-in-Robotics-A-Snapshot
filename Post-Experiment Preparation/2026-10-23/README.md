# Post-experiment diagnosis and potential video highlights

Created October 23, 2026, Development Codex Session 75, in the private Session-74 snapshot. This folder is separate from the historical apparatus and evidence. It fulfills Randy's two requests in the [Public Release Preparation conversation](../../chats/Codex-Human/Public%20Release%20Preparation/Public%20Release%20Preparation%20-%20Active.md).

- **[Arm diagnosis](DIAGNOSIS.md):** model/source analysis, original saved states, native reconstructed frames, interpretation limits and the distinction from filesystem continuity.
- **[Ranked video candidates](HIGHLIGHTS.md):** six ranked sequences plus five additional candidates, with exact available times, original image IDs, file links and caveats. No video was created.
- **[Nine cross-session connections](reuse-links.json):** exact-byte write → checkpoint → later full-file read evidence. These demonstrate persistence/access, not a causal memory benefit.
- **[Original images](selected-images.json)** and **[export identities](selected-exports.json):** byte-identical selected sensor images, reports, trial logs and checkpoint-file versions under `evidence/`.
- **[Geometry readback](geometry-inspection.json)**, **[history catalog](history-catalog.json)** and **[verification](verification.json):** machine-readable supporting records. The catalog covers all 69 accepted sessions; it is a navigation aid, not a new performance analysis.

## Historical access

Baseline was located at `D:/Dandelion Engineering/LLMs in Robotics/Dandelion-Apartment-Experiment/official/apartment-v4/baseline`. Embedded old `D:/Dandelion-Apartment-Experiment/...` pointers are unchanged. Maps was inspected at `C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Local Experiment Data/apartment-v4-maps/recovery-session63/recovered-run`. This work reads historical sources only, never the later VLA work or active robotics implementation.

The exports make selected evidence inspectable in this snapshot. Full raw replay chunks, journal/content stores and native transport remain off Git. Their actual locators, sizes and SHA-256 identities are recorded in `inputs.json`, `geometry-inputs.json` and `selection-inputs.json`. No global relocation or complete-root re-audit is claimed. The final Baseline/Maps checkpoint manifests and states match their recorded final-checkpoint receipts; selected final reports/artifacts match their checkpoint manifests.

Files under `evidence/` are exact historical bytes. Their embedded relative links retain their original guest-filesystem context and may not resolve inside this export folder; use `selected-exports.json` for source locations. Main report links point directly to available exports or preserved repository sources. Checkpoint code copies end in `.py.txt` and were never executed. Folder-local Git attributes preserve exact exported bytes.

## Method and reproducibility

`inspect_history.py` authenticates the six relevant apparatus/viewer sources against both run identities, verifies complete event/journal/clock chains, inventories session boundaries/images and reads all 69 reports. Its broad derived working indexes live under ignored `.local/`; no original source is written. `select_evidence.py` exports the selected version links, original RGB frames, report and trial evidence. `inspect_geometry.py` compiles the preserved scene directly, restores two selected original `qpos`/`qvel` samples, calls `mj_forward` and renders. It never constructs a `World`, steps physics, starts a controller, or executes a historical program. The native diagnostic views hide wall display group 1 only; these are new reconstructions, not original video frames.

`verify_inspection.py` independently rehashes every consumed input and export, checks selected journal records and clock brackets against original files, checks checkpoint/read content identities, reloads original state samples, verifies native geom transforms and the observer's box-vertex arithmetic, and inventories common movie/animation formats within the two run roots. It does not repeat endpoint scoring. A separate failed reader log, two interrupted queue receipts and the initial wall-occluded render examples are retained. The first two interruptions had no completed outputs. The failed reader's `packet['sequence']` lookup was corrected to `payload['sequence']`; historical data did not change.

The snapshot's local `venv` was created without pip after `ensurepip` failed. It explicitly references the existing verified historical environment's site-packages read-only, through ignored `venv/Lib/site-packages/historical-readonly-packages.pth`. NumPy **2.5.3** and MuJoCo **3.14.0** match this snapshot's requirements. No package or file in the original active project was installed or edited. A new host should create its own environment from `requirements.txt` rather than relying on that local path.

Submit sustained inspection through the installed shared queue, with this snapshot as project/cwd and its local Python. The successful history reader is `20261023T183233714208Z-2982134b`. Static geometry first passed as `20261023T183204255816Z-62d6160e`; the wall-hidden display revision passed as `20261023T183344003886Z-f90a8a2b`. Their terminal receipts are stored here. `verification-queue.json` records independent readback completion. Only a queue state of `succeeded` and integer exit 0 licenses use of that job's outputs.

No experiment, model, original viewer, checkpoint, prior report, result or evaluation rule was changed. No comparison, video, publication, license selection, public README rewrite or other release work was performed. This folder does not authorize any follow-on action.
