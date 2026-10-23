# Third-party notices

This file identifies known third-party materials and production tools. It does not replace their licenses, grant rights to third-party material, or imply endorsement. The root project licenses do not override the terms below.

## Included framework

**Collaboration Station 2.0**, Dandelion Engineering, Copyright (c) 2026 Dandelion Engineering. Framework code is MIT; prose and templates are CC BY 4.0. The robotics project adapts the framework. Attribution and license scopes are in `LICENSING.md`, `LICENSE`, and `LICENSE-docs`.

Source: https://github.com/Dandelion-Engineering/Collaboration-Station-2.0

## Included mfusepy source

Copies of `mfusepy.py`, `LICENSE`, and `provenance.json` are present in the `vendor/` directories of campaigns 003, 004, and 005 under `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/`.

Source: https://github.com/mxmlnkn/mfusepy/tree/681aeaf67f5ca93f1d17450be5b6c5aa895e61f0

License: ISC. The upstream LICENSE states Copyright 2012 Giorgos Verigakis. The source header also credits Copyright (c) 2012 Terence Honles (maintainer) and Copyright (c) 2008 Giorgos Verigakis (author). Preserve the full source headers as well as the accompanying LICENSE. A convenience copy is provided at `licenses/third-party/mfusepy-LICENSE`.

## Included OpenAI Codex source excerpts

Upstream source-investigation records under `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair/` contain copied Codex source, including `codehost-channel-source-001/` and `native-output-source-001/`, `native-output-source-002/`, and `native-output-source-003/`. Their source-evidence records identify the upstream files and retrieved revisions. These are third-party source records, not original project code.

Source: https://github.com/openai/codex

License: Apache License 2.0. Copyright 2025 OpenAI. Existing licenses and notices are retained. Complete convenience copies are in `licenses/third-party/OpenAI-Codex-LICENSE` and `licenses/third-party/OpenAI-Codex-NOTICE`. The upstream notice also identifies Ratatui-derived material, with Copyright (c) 2016–2022 Florian Dehau and Copyright (c) 2023–2025 The Ratatui Developers. That notice is preserved without claiming that every upstream component appears in each excerpt. Any modified upstream files must retain applicable notices and identify their modifications.

## Included Rust dependency source and package archives

Under the same `codehost-channel-source-001/` directory:

- **hyper-util 0.1.20**: package archive and source excerpts, MIT. Preserve `hyper-util-0.1.20__LICENSE`. Source: https://github.com/hyperium/hyper-util. Convenience copy: `licenses/third-party/hyper-util-LICENSE`.
- **reqwest 0.12.28**: package archive and source excerpts, MIT or Apache 2.0 as provided upstream. Preserve both `reqwest-0.12.28__LICENSE-MIT` and `reqwest-0.12.28__LICENSE-APACHE`. Source: https://github.com/seanmonstar/reqwest. Convenience copies are in `licenses/third-party/`.

Package contents and historical source bundles retain all embedded licenses and notices; they are not covered wholesale by the project's MIT license.

## Historical Panda model bundles

Two historical evidence archives contain the MuJoCo Menagerie Franka Emika Panda model:
- `Long-Horizon Adaptive Robotics Expirement/Evidence/calibration/posture-screen-001/source-bundle.zip`
- `Long-Horizon Adaptive Robotics Expirement/Evidence/diagnostics/raw-pickup-geometry-001/diagnostic-sources.zip`

Their `Runtime/vendor/panda/` directories retain the Apache-2.0 LICENSE, README and provenance manifest. Source: https://github.com/google-deepmind/mujoco_menagerie/tree/822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7/franka_emika_panda . Keep those notices with the model. This historical model material is distinct from the later procedural apartment apparatus and is not relicensed under the project's MIT or CC BY terms.

## Distributing historical source archives separately

The `Architecture Map/releases/RCI001-C02-dev-059`, `060`, `064`, `065`, `068`, `069`, `072`, and `073` `code.zip` files under `Long-Horizon Adaptive Robotics Expirement/` contain OpenAI Codex source excerpts without an embedded copy of its license/NOTICE. When distributing these ZIPs separately from this repository, supply the applicable `licenses/third-party/OpenAI-Codex-LICENSE` and `OpenAI-Codex-NOTICE` alongside them and preserve applicable source notices. The repository-level copies accompany the complete repository distribution; they do not make a standalone ZIP self-contained.

## Simulation and video tools

The project uses **MuJoCo**, developed by Google DeepMind and contributors, for simulation and rendering. MuJoCo is Apache-2.0-licensed: https://github.com/google-deepmind/mujoco/blob/main/LICENSE. The apartment scene is constructed procedurally by `Apartment Experiment/scene.py`; its source identifies no external scene assets.

The root `requirements.txt` records runtime packages, including MuJoCo, NumPy, absl-py, etils, fsspec, glfw, PyOpenGL, typing_extensions, websockets, and zipp. Video-production code additionally uses Pillow, imageio-ffmpeg, and an installed FFmpeg executable. These tools and dependencies retain their respective licenses. Listing or invoking an installed dependency is distinct from redistributing its source or binary.

The short presentation uses project simulation renders, recorded camera frames, captions, and editorial graphics. Its production script invokes FFmpeg with libx264 to make a silent H.264 MP4. FFmpeg's license varies with its build configuration: https://ffmpeg.org/legal.html. This notice does not claim ownership of FFmpeg or libx264, or grant codec-patent rights. The output video's project-owned content is covered by `LICENSE-docs`; this does not relicense an encoder or other software.

## Fonts rendered in the short presentation

The production script uses locally installed Windows **Segoe UI**, **Segoe UI Semibold**, and **Consolas** fonts. The captions are rendered into image pixels; the script does not embed font files into the MP4. Microsoft's font FAQ permits this kind of video-caption output, subject to the stated conditions, while distinguishing it from font-file redistribution:

https://learn.microsoft.com/en-us/typography/fonts/font-faq

Font software remains owned by its respective rights holders and is not licensed under the project's MIT or CC BY licenses. Rebuilding the video requires appropriately licensed installed fonts or permitted replacements.

## Other quoted material

Third-party product descriptions, quotations, literature excerpts, trademarks, and any third-party content captured in records retain their own rights. The current `Project Details/Parts List.md` contains factual item names and recorded quantities only. Earlier versions contained product-listing prose; those historical versions are not relicensed by the project licenses. A source citation or exclusion is not itself permission to redistribute protected text.
