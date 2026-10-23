# Session-006 throwing evidence

Seven trials were performed through the existing learned program using public arm/gripper primitives. All seven had fresh `inside_bin=true` landing feedback. The base was near initial-frame (.002,.001–.003), throwing yaw 12.2456, equivalent -.3208 rad. These are noisy dead-reckoned estimates; the scene and acquisition were reobserved each time.

| Trial | Acceleration / release, s | Landing sim time | Forward / left displacement, m | Inside | Raw program output |
|---|---|---|---|---|---|
| 1 | .27 / .13 | 3859.860 | +.099 / -.029 | true | [trial 1](session-006-trial-1.jsonl) |
| 2 | .28 / .135 | 3916.388 | +.023 / -.003 | true | [trial 2](session-006-trial-2.jsonl) |
| 3 | .28 / .135 | 3969.120 | +.025 / -.004 | true | [trial 3](session-006-trial-3.jsonl) |
| 4 | .29 / .135 | 4016.600 | +.026 / -.004 | true | [trial 4](session-006-trial-4.jsonl) |
| 5 | .28 / .14 | 4061.464 | -.024 / +.013 | true | [trial 5](session-006-trial-5.jsonl) |
| 6 | .28 / .137 | 4106.208 | -.006 / +.008 | true | [trial 6](session-006-trial-6.jsonl) |
| 7 | .28 / .137 | 4154.464 | -.009 / +.009 | true | [trial 7](session-006-trial-7.jsonl) |

All trials retained the same commanded waypoints: prepare (.35,0,.90), pitch 0 in 1.2 s; accelerate toward (.76,0,1.12) at width .025; move toward (1.02,0,1.30) while opening to .15; retract to (.30,0,1.15). Only the two durations shown varied. Each program invocation used the then-current default or explicit arguments; the raw output does not itself record CLI arguments, so this table preserves them.

## Acquisition and sensing

- The orange object was on its pedestal when first observed during this assignment. No reset was needed before the first pickup. Resets occurred only after release and confirmed landing, between trials; no reset followed trial 7.
- Head observation 144, facing yaw approximately 10.9958 (south), showed the orange sphere on the pedestal. Pixel (240,221) projected to visible surface (.5638,-.0013,.9494). Geometry supported the same approximate grasp center (.60,0,.935) used historically. Subsequent fresh pedestal projections from observations 148, 152, 156, 160, 164 and 168 were consistent: surface x .5614–.5640, y -.0013, z .9465–.9478.
- Default position_grasp was invoked with (.60,0,.935). Its completion was polled and images 145,149,153,157,161,165,169 were viewed before closure. Desired width .025 produced bilateral contact and approximately .089 measured aperture, effort 19.173. Every pickup included an actual vertical lift to z=1.20 with secure-lift confirmation before retraction to (.30,0,1.15) and turning toward the bin.
- Prethrow images 146,150,154,158,162,166,170 showed the held orange sphere and target alignment. The overall path was clear in current observations and the unobstructed target views between trials. No people or moving obstacle were visible.
- Images 147,151,155,159,163,167 and 171 were viewed after respective throws. The orange object was clearly visible in the bin after trial 1; several later settled poses were partly or wholly occluded by the front wall. Final containment is established by fresh public landing feedback, not a claim that every settled sphere was directly visible.
- At preparation z=.90, secure_lift_confirmed became false while bilateral contact, measured aperture and effort persisted, matching the scoped historical memory. No acquisition failure or drop was observed.

## Interpretation and reusable change

The original .27/.13 default succeeded again but landed .099 m forward of center in this episode. Two .28/.135 repetitions were close to one another and to the historical session-001 .28/.135 success. Trial 4 changed only acceleration duration relative to trials 2–3 and gave a similar result. Trial 5 changed only release duration relative to trials 2–3 and landed on the near side. Interpolating the requested release duration to .137 yielded two near-center results, radial errors .010 and about .0127 m.

These results motivate updating the learned program default to **.28/.137**. Both values were executed successfully together twice through the same program before editing its default arguments. Python AST parsing confirmed the edited file's syntax; a static check confirmed those defaults. No trajectory logic or safety checks changed. The default invocation after the edit was not physically rerun because the practice window was ending; the identical explicit-argument path supplied physical evidence.

Seven successes and two repetitions of the selected timing do not establish a statistical reliability guarantee. Small timing differences, noisy geometry and settling may matter. The acceleration-only result does not prove acceleration is generally irrelevant. The much wider changes in session-001 trial 1 remain causally unresolved.

## Ending evidence

The arm was empty and stowed at (.22,0,.70). First recorded low warning was sim 4195.640; all subsequent physical commands were direct charger return, sensing, settling and docking. Dock request eb66098caa3145f69202e0cfff766982 completed at sim 4233.624. [Final status](session-006-final-status.json) confirms docked=true, action=null and the final inside-bin landing. General task_success remained false, as in earlier bounded practice; completion follows the deployment's practice-window/docking rule.
