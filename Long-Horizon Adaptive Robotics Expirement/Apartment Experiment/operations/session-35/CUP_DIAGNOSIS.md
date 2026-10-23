# Session 35 cup motion diagnosis — October 8, 2026

The observed back-and-forth motion is real in the recorded simulation. The evidence points to an **unphysical contact-dynamics artifact**, rather than a viewer replay loop or ordinary passive coasting. The exact numerical mechanism within the contact solver remains unproven. No apparatus, robot input, learning, schedule, model turn or live state was changed.

Randy requested this read-only diagnosis in the current Codex conversation: “Either way, don't do any fixing. Just let me know what is going on and then continue the 30 min monitoring intervals. I'll decide if we need to do something.” Session 35 and its existing monitoring schedule remain active. This finding is an open physics anomaly, not authority to repair, reset, retry, skip, hibernate or relaunch.

The retained window contains 5,752 original samples from simulation time 9203.836 to 9383.804 seconds (about three minutes). Each original replay chunk was SHA-256 verified. The complete retained event prefix was hash-chain verified; there were no recorded commands or other controller events during this window. Live viewer positions agreed with corresponding recent original samples within 0.25 mm (sample ages 12–16 ms).

| Observation | Verified result |
| --- | --- |
| Travel between endpoints | Approximately 1.97 m |
| Reversals | Approximately every 50–51 simulated seconds |
| Maximum linear speed | 0.088 m/s, or 8.8 cm/s |
| Sideways deviation from the travel line | Approximately 0.059 mm |
| Reconstructed contacts at all recorded samples | 11,504 floor contacts; 11 brief cabinet-side contacts; no robot contacts |
| Later reversal-to-reversal interval | 1,631 samples / 50.984 seconds with only floor contact |

The cabinet contact near simulation time 9265 s can affect that particular reversal. It does not explain the later floor-only motion from 9316.432 to 9367.416 s. During that later interval the cup starts essentially at rest, accelerates, and returns essentially to rest. Its kinetic energy reaches approximately **0.585 mJ**, while gravitational potential varies by only **0.00373 mJ**. The floor is flat, the cup's cylindrical axis remains almost exactly horizontal, and the frozen source has no periodic cup reset or applied cup force during this assignment. This repeated energy gain is inconsistent with interpreting the motion as a freely coasting ideal cylinder on a level floor.

The compiled cup/floor contact dimension is `3`, with zero cup-joint damping and no fluid drag. MuJoCo documents that dimension 3 supplies sliding friction, while dimension 6 adds rolling resistance; the nonzero rolling-friction coefficient written in the default geometry does not enable that resistance with dimension 3. This explains the lack of a mechanism to bring pure rolling to rest, but **missing rolling resistance alone does not explain repeated reversal and reacceleration**. See the [official MuJoCo contact-dimension documentation](https://mujoco.readthedocs.io/en/stable/computation/index.html#condim).

Independent contact reconstruction also produces small offsets in the floor support points and rolling torques. Together with the recorded energy behavior, this implicates the cylinder/floor numerical contact dynamics. These forces are diagnostic reconstructions using `mj_forward` at recorded states, not original logged force telemetry: original solver warmstart and actuator history are not replayed. No `mj_step`, counterfactual run, solver change or intervention was performed. The same project venv/MuJoCo 3.14.0 used by the official host controller was used for readback.

This does not establish whether Robot Codex can pick up a moving object. It does establish a physics realism concern that should remain visible while Randy decides what to do. It is not a Baseline-versus-Maps comparison or a scientific condition result.

Evidence is preserved under `D:/Dandelion-Apartment-Experiment/official/apartment-v2/operator/maps-session35-001/cup-diagnosis-001/`: `result.json`, original replay-index snapshot, `cup-samples.npz`, sampled and full contact/energy reconstructions, `floor-only-half-cycle.json`, and the authenticated event-prefix copy. `cup-diagnosis.json` in this directory binds the report and evidence hashes. The original run recordings remain in place.
