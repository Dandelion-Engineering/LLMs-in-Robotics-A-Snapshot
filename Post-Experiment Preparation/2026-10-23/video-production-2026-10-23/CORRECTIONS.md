# Script correction and presentation boundaries

Production began October 23, 2026, after Randy authorized the video in the existing Public Release Preparation conversation. `../VIDEO-SCRIPT.md` remains unchanged.

One factual correction is applied to the caption at 97–103 seconds:

- Script: “Randy directed a restore to checkpoint 5. The abandoned continuation was excluded.”
- Rendered: “Randy directed a restore to checkpoint 5. The failed original session-6 tail was excluded.”

The abandoned invocation belonged to the failed original Maps run. The checkpoint-5 continuation was accepted and retained. Calling that accepted branch “abandoned” would obscure the distinction. The corrected sentence preserves the intended meaning without strengthening the result. This was flagged in the production commentary before rendering. All other main caption wording follows the supplied script verbatim.

The movie is a nonlinear editorial presentation. Every cut names its session, held state/frame, or time jump. A “Recorded-state replay” is a new native rendering of an original sampled state, never a new dynamics run. The camera and wall display are derived presentation choices; apartment wall group 1 is hidden for visibility, while robot geometry remains unchanged. Sparse original sensor images are held still and labeled “Robot camera • recorded frame.” Editorial diagrams and the interruption card have their own explicit labels.

Feedback is displayed only when the shown original sample is at or after the retained supporting status/landing time. File read/write panels use the upper bound of their recorded clock brackets. Program requests are joined from the original executor capture's wall timestamp to adjacent original world events; those brackets and record identities are retained in the manifest. No process-start simulation time is invented. Source excerpts are labeled as excerpts; no private deliberation, account data, host paths or credentials are included in the movie.

## Retained production QA failures

The first video render, `outputs/v1/three-sessions-later-session76-v1.mp4`, completed successfully as an encoding job but did not pass source-timing acceptance. The independent verifier found that the held world sample underneath the session-3 summary-read panel was 1694.692 s, 16 ms before the read bracket's upper bound, 1694.708 s. The requested seek had been slightly later, but the nearest retained predecessor was earlier. Version 2 moves the relevant held samples safely after their upper bounds; it changes no original event, file or physical state. Version 1, its source snapshot/manifest/frame mapping and initial inspection images remain locally preserved and are not the accepted deliverable.

An earlier verifier failure assumed all samples were separated by exactly 20 ms. Actual selected sample ages reach 32 ms in this approximately 50 Hz recorder. The corrected check requires the actual retained predecessor and verifies adjacent original sample times, with no interpolation. The measured maximum age is reported instead of inventing a constant sample rate. Both failed verifier receipts/logs are retained.

The primary browser-control runtime failed twice before exposing browser state. A first isolated Edge attempt also failed because the sandbox-started loopback player was unreachable. The player was restarted outside the sandbox on loopback only, with no change to browser/account settings. Failure receipts and the isolated-browser error are retained; a full normal-speed playback receipt is required before acceptance.

Version 2 passed all source/decode checks and a full 1× browser playback (140 seconds, 3,357 presented frames). Visual review then found that throwing feedback was displayed too briefly. Version 3 keeps the 140-second script/caption schedule, speeds the short recorded throw segments explicitly, then holds their actual recorded results for about two seconds. The held states remain labeled; no new motion or outcome is invented. It also adds outlined timestamps for contrast, shows a useful literal route excerpt, explicitly shows the saved kitchen-map file, and uses the saved cup-staging sentence as the continuity excerpt. These are presentation changes, not new factual corrections to the script. Earlier MP4s and their supporting records remain under ignored `outputs/v1/` and `outputs/v2/`.
