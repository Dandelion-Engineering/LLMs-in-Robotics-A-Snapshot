# Project Details

## Working Title

**LLMs in Robotics**

## Dandelion Engineering

This is a **Dandelion Engineering** project.

Dandelion Engineering exists to **engineer affordable technology that materially improves the lives of everyday people**, using AI, scientific research, and practical experimentation. Research is part of building, not a stage that must be completed before engineering begins.

The company aims to remain independent and sustainable, financially support Randy and his family comfortably, and prioritize usefulness and affordability rather than venture-capital growth targets. 

## Project Purpose

Explore and build ways to integrate large language models and agent frameworks with robotics so that physical systems can reason about tasks, use observations and experience, and adapt their behavior.

The motivating idea is **a robot that thinks**. Its observable capabilities and the LLM's placement will emerge through learning, design, and testing. Memory, code generation, sensor-grounded decisions, and transfer across compatible bodies are possibilities, not an adopted architecture.


## Engineering First

The destination is a working, useful capability—not a literature collection, framework, or publication for its own sake.

- Use existing components when they work. Novelty is welcome, not required.
- Use research to explore possibilities, inform designs, challenge assumptions, and investigate unresolved problems. Literature discovery is a legitimate starting point; exhaustive reading is not a prerequisite for building.
- Try promising ideas without requiring a prior failure. Test their value rather than assuming it.
- Connect increments to the larger capability. Prefer runnable behavior and decisive experiments over elaborate plans.
- Compare against simpler alternatives. Distinguish observations, reported findings, interpretations, and hypotheses; preserve failures and limitations.
- Consider human effort, compute, learning, reliability, cost, and physical constraints. Simulation does not establish real-world deployment.

Neuroscience is a welcome source of mechanisms and design ideas, not a requirement to reproduce biology or evidence that an artificial mechanism works.


## Codex-Only Operation

**Randy is the human project lead. Codex is the only standing AI agent. All project tasks belong to Codex.**

These project-specific rules override conflicting multi-agent assumptions in `AgentPrompt.md` and the local scaffold:

- Do not announce seams, post a first-claim coordination message, or leave work open for another standing agent. The generic instruction to do so unconditionally does not apply here.
- Do not create Claude assignments, cross-model conversations, peer-approval dependencies, or reciprocal review cycles. Do not wait for another model to respond.
- Keep the normal human-message checks, work-claim safeguards, continuity records, and closeout procedures. Project chats remain a way to receive Randy's direction, not a requirement to manufacture agent-to-agent conversation.

Apply these overrides within this project. Do not rewrite the shared Collaboration Station template or unrelated projects.

## Resources and Authority

There is no budget for new spending. Use existing authorized resources and favor components with verified terms suitable for eventual commercial use. Research-only work can still inform our thinking; permission to read a paper is not permission to reuse its code, weights, data, or assets.

Randy's approval is required for spending, new accounts or credential use, external contact, publication, destructive external actions, and physical deployment. Existing authorized access may be used within its scope. 

**As stated above, this project does not have any cash available at the moment. That constrains us to simulations and open source resources. Any resources used must allow for commercial applications. If this project is successful it could be a potential source of income for Randy and Dandelion Engineering.**


## Available Hardware and Physical Build Preferences

A current inventory of hardware, electronics, sensors, tools, and leftover parts is maintained in:

**[Parts List](Parts%20List.md)**

Check this file before assuming new hardware must be purchased. Existing parts may be used when they are genuinely useful to an engineering direction, prototype, experiment, or physical robot.

The existing inventory includes computing and control hardware, sensors, actuators, electronics prototyping equipment, soldering equipment, and other components that may support future physical builds. The existence of a part does **not** mean the project should be designed around it. Choose the engineering approach first, then determine whether existing hardware can support it.

### Physical Build Preferences

Randy is willing to:

- connect and wire electronic components;
- use breadboards for electronics development and testing;
- solder wires, headers, sensors, connectors, and circuit components;
- assemble electronics and actuators into a designed system;
- assemble an existing open-source or documented robot design;
- assemble a mechanical design created by Codex when the parts can be fabricated cleanly;
- and, when funding becomes available, use 3D-printed parts for proper mechanical structures, housings, mounts, robot bodies, or mechanisms.

Randy does **not** want to build makeshift mechanical rigs.

Do not design project milestones around improvised physical structures whose main construction method is ad hoc mounting, scrap materials, temporary mechanical arrangements, or manually fabricated structures that exist only because a proper design has not been made.

This does not prohibit ordinary electronics prototyping, breadboarding, temporary wiring during circuit development, or controlled component tests. The distinction is that Randy is comfortable doing **electronics integration and assembling a designed machine**, but does not want the project to depend on extensive improvised mechanical fabrication.

For a physical robot, prefer one of the following routes:

1. an existing documented mechanical design that can be purchased (only if cash becomes available), printed, or assembled;
2. an existing low-cost/open-source robot platform;
3. a mechanical design produced for this project that can be manufactured cleanly, especially through 3D printing or standard off-the-shelf components.

A physical build should therefore be treated as an engineering design before it becomes an assembly task.


## Playbooks

Playbooks provide practical guidance for recurring project work. Read the relevant playbook when its task arises; use this section as the index of what each covers and when to access it.

- **[Architecture Map](../Playbooks/Architecture%20Map.md):** Read before proposing or revising an experiment architecture, implementing or running one, comparing results, or recording discoveries and notes. The [Long-Horizon Adaptive Robotics Experiment](../Long-Horizon%20Adaptive%20Robotics%20Expirement/README.md) contains both its design package and an initially empty searchable map of architecture identities, exact revisions, runs/results and investigation history. Retrieve prior attempts first; keep measured evidence distinct from interpretation, preserve failures and superseded results, and do not let a record schema restrict the architecture design space. Creating the map does not authorize architecture candidates or experiments.

- **[HTML Interactive Reports](../Playbooks/HTML%20Interactive%20Reports.md):** Read when creating a substantial research explanation, synthesis, comparison, or other report where interactive visuals and exploration could materially improve understanding over a conventional linear document. It explains the system-first learning approach, progressive technical depth, connecting details to larger ideas, meaningful interactivity, evidence provenance, original-paper access, and scientific and interaction QA.

- **[Synchronized Experiment Replay](../Playbooks/Synchronized%20Experiment%20Replay.md):** Read when creating derived replay tooling to inspect an experiment over time. It covers shared cursor behavior, clock/receipt verification, observable-channel filtering, bounded filesystem reconstruction, final browsing, browser QA and prospective capture improvements. Replay tooling does not reopen or change frozen experiments.

- **[Accessing and Updating the Literature Map](../Playbooks/Literature%20Map.md):** Read when looking for research papers, before external literature searches, when a paper is materially used, and when adding, correcting, or maintaining corpus records. It explains retrieval, source and reading-depth provenance, deduplication, material-use updates, and keeping the canonical corpus and derived views consistent.

The Literature Map at `literature/` is Codex's first reference for research relevant to this project. Check it before repeating external searches; use external research to fill gaps, obtain needed primary detail, and find newer or competing evidence. Add relevant discoveries and update materially used records with their actual reading depth, evidence, and limitations. The map supports engineering judgment; it neither selects the robot's architecture nor replaces the underlying sources.

Use HTML Interactive Reports when the format helps the project lead build a mental model, explore an important mechanism or comparison, or move between high-level ideas, technical details, and underlying evidence without requiring long stretches of linear reading. Do not convert every report to HTML by default; use the format when interactivity, visualization, or layered depth meaningfully improves understanding. Important claims must remain traceable to their evidence, and schematics, simulations, agent interpretations, and hypotheses must be distinguishable from directly reported or measured results.


## Compute Environment

The reference desktop is Windows 11, an AMD Ryzen 7 8700F, an NVIDIA RTX 5060 Ti with 16 GB VRAM, 32 GB RAM, a 1 TB NVMe drive on `C:`, and external SSD storage on `D:`. Verify the actual host, available capacity, software, and paths before relying on them; historical driver or environment versions are not guarantees.

Use the project-local `venv` for Python work. Verify it exists, or create it when needed; do not assume the new project inherited another project's environment. Once available, invoke `.\venv\Scripts\python.exe` and install through that interpreter, recording installed dependencies and versions in `requirements.txt`.

Submit sustained heavy CPU, GPU, RAM, or storage work through the shared queue:

```powershell
.\venv\Scripts\python.exe -B "C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py" submit --project "<actual-repository-name>" --cwd "<actual-project-directory>" -- <executable> <arguments...>
```

Record the job ID. Query `status <job-id>` through the same queue tool and require `state` to be `succeeded` with `exit_status` 0 before using outputs. Queued or running work is not complete. Never bypass or modify the queue or another project's jobs.

## Project Lead

Always read **[Project Lead.md](Project%20Lead.md)** in this folder at initialization.
