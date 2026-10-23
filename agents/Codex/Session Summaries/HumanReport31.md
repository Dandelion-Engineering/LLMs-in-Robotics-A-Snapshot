# Session 31 — repaired apartment baseline launched

The repaired official baseline is running. Randy explicitly authorized launch in the current Codex chat: "I'm here btw so you could launch the fixed baseline". The single queue submission started at **08:28 PDT on October 7, 2026**, using the prepared frozen repository on D:. The live observer was opened, visually verified, and retained for Randy at [http://127.0.0.1:55582](http://127.0.0.1:55582).

## Running state

- Run: `APARTMENT-v1-restart001-baseline`; revision: `APARTMENT-v1-storage2-frozen`.
- Root: `D:/Dandelion-Apartment-Experiment/official/apartment-v1-restart001/baseline`.
- Queue job: `20261007T152810664605Z-1b6c57b1`.
- First native thread: `01a116fa-d873-7761-8113-81f8419778cf`; effective model/effort: `gpt-6-astra` / `max`.
- Maps remains pristine and unlaunched. The failed October 6 baseline remains excluded and was not resumed.

The queue worker owns ongoing execution independently of this Development Codex session. Do not submit another initial launch. Closing the viewer stops observer rendering and polling, while the experiment continues.

## Verification and evidence

`main` was clean and already current after `git pull --ff-only`. The session followed AgentPrompt, Project Details, the Codex-only overrides, the Session 30 repair handoff and the Architecture Map playbook. There were no competing claims or new file-chat instructions.

Before submission, all 254 frozen source files matched their recorded byte lengths and hashes. The certificate and installed-runtime launch guards passed. Baseline and Maps initial inventories exactly matched their original preparations, with no sessions, checkpoints, running locks or pending hibernation. The original matched schedule and configuration were exact. D: had about 413 GiB free. The frozen source, templates, parameters and evaluation plan were not edited.

All fifteen startup checks passed. Both namespace canaries qualified with integer exit 0. The native preflight established the effective model and effort; observable events independently showed a started turn and tool use. Physics time advanced between two reads. At the saved startup observation, session 1 was active at approximately 105.49 simulation seconds, with 17 physical events, 84 protected-filesystem records, 207 native records, and 27 replay files. Prefix byte lengths and SHA256 hashes bind these changing logs without claiming that their later bytes were already checked. The viewer visibly rendered the apartment and filesystem reads.

This is startup verification only. The queue was running with no terminal exit status. No clean session boundary, checkpoint, task success, terminal validity, learned throwing skill, or condition comparison was assessed. No hibernation request was issued. Ordinary runtime errors must remain explicit; do not silently retry, extend battery windows, alter the frozen comparison or resume the excluded original root.

The compact evidence is under [operations/session-31](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-31/): direct authorization and prelaunch checks, exact submission argv and queue receipts, startup observations, and the append-only chat proof. Architecture Map event `APARTMENT-v1-restart001-baseline-launch-001` records actual launch while preserving the original preparation manifests. The map catalog was rebuilt and validation passed.

## Operator handoff

The updated [operator README](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/README.md) contains the exact current status, viewer, hibernation and eventual resume commands. Hibernation becomes pending, allows Robot Codex to finish its ordinary work/return/dock/closeout, then retires and validates a checkpoint before stopping. A pending request alone is not successful hibernation.

Future continuation must first inspect the existing queue and run. Resume is appropriate only after a clean validated hibernation. Maps stays gated on the baseline's verified 21-assignment endpoint. This session ends after its scoped commit/push while the independent experiment worker continues.
