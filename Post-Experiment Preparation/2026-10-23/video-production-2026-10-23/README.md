# Three sessions later — private video deliverable

Produced October 23, 2026, Development Session 76, from Randy's approved [VIDEO-SCRIPT.md](../VIDEO-SCRIPT.md). Historical evidence and the supplied script remain unchanged.

- **[Final MP4](deliverables/three-sessions-later-session76-v3.mp4)** — 2 minutes 20 seconds, 1920×1080, 24 fps, H.264/yuv420p. Intentionally silent, with no audio stream, narration, synthesized voice or new music.
- **[Plain-text captions/transcript](captions.txt)** and [SRT sidecar](captions.srt). Main on-screen wording follows the script, with the one documented factual correction below.
- **[Source/timecode manifest](source-timecode-manifest.json)** — every editorial shot, video interval, original run/session/time, reconstruction/image/graphic category, source hashes and limits.
- **[Cue evidence bindings](cue-evidence-bindings.json)** — individual file-write/read/checkpoint identities and safe display times; [per-frame source map](frame-sources.jsonl.gz) identifies every actual original sample behind reconstructed frames.
- **[Independent video verification](video-verification.json)** and [normal-speed playback receipt](browser-playback-review.json), plus decoded/browser QA captures in `qa-decoded-v3/` and `qa-browser-v3/`.
- **[Visual QA and playback review](VISUAL-QA.md)** - actual output inspection, phone-size legibility, complete playback and remaining evidence limits.
- **[Corrections and retained QA failures](CORRECTIONS.md)** — the excluded material was the failed original Maps session-6 tail, not the accepted checkpoint-5 continuation. The supplied script itself was not edited.

## What is shown

The three selected stories are Baseline's throwing program across sessions 1/6/9, unfinished toy cleanup across sessions 2/3, and Maps' dropped cup, Randy's checkpoint-5 recovery direction and the accepted session-6 continuation. Later-session reads use the exact saved bytes, not recreated text. Original sparse robot-camera frames are held still and explicitly labeled. Native recorded-state reconstructions use original `qpos`/`qvel` and `mj_forward` only, never a dynamics step or historical executable. Camera viewpoints and hidden apartment wall display group 1 are derived presentation choices; robot geometry is unchanged and its missing connecting structures remain visible.

Session changes, nonlinear time jumps, speed changes, held samples, held original frames and editorial graphics are labeled. Feedback is not shown before its supporting state; file panels are guarded by the upper bound of measured read/write clock brackets. Program invocation times are joined from original executor capture timestamps to adjacent world events, without inventing an exact simulation instant. Selected historical state ages are at most about 56 ms; there is no interpolated robot motion. Raw credentials, account records, private deliberation and host filesystem paths do not appear on screen.

The final cup is occluded in the original post-release image; the video says so and shows the actual task check rather than a fabricated settled-cup view. World state also persists between sessions. The ending explicitly limits the claim to continuity evidence rather than a causal memory benefit or real-hardware validation. Timed throwing advancement is not described as mastery.

## Files and reproduction

The MP4 is small enough for the private repository (about 4.84 MB). `deliverables/` contains an exact-byte copy of the verified local render; `delivery-manifest.json` binds its size/hash to that render. Intermediate movies, broad decode material and isolated browser profiles remain local and ignored under `outputs/` and `.local/`. The final local render is `outputs/v3/three-sessions-later-session76-v3.mp4`; earlier versions are preserved beside it, not overwritten.

`production.py` builds a new uniquely named output version through the shared compute queue. `verify_video.py` independently rehashes sources, checks original samples and time bounds, decodes all 3,360 output frames, confirms format/duration/no audio and exports 111 phone-size frames around all cuts. `browser_qa.js` plays the actual MP4 at normal speed in an isolated installed Edge profile and captures the video element at desktop and 640-pixel phone-landscape sizes. `preview_server.py` is a temporary, loopback-only range-capable player with no experiment routes. The server and isolated browser are stopped after QA.

Use the snapshot's project Python and verified historical NumPy 2.5.3/MuJoCo 3.14.0/Pillow 13.0.0 and existing FFmpeg 7.1 binary. Browser QA uses installed Node 24.16.0 and Edge; no package install, new account or external media was needed. Launch sustained work through the installed shared queue. Require `state: succeeded` and integer exit 0 in each retained queue receipt before using outputs. Select a new output directory to reproduce; never overwrite the retained versions or rerun scientific experiments.

The task authorizes private `origin/main` closeout only. No repository visibility, license, public README, original active robotics project, later VLA work, frozen apparatus or scientific result was changed. This movie has not been publicly published.
