# LLMs in Robotics

What can an AI agent controlling a simulated robot carry from one session into the next?

This snapshot of an ongoing project explores that question with an AI agent, Robot Codex, controlling a simulated robot in an apartment. The agent works on household tasks, writes notes and programs to a persistent filesystem, and returns in later sessions to continue. The repository preserves the engineering process as well as the results: human direction, agent conversations, code, tests, failures, and reports.

## Watch the experiment

**A note about the robot:** The experiment focused on continuity across agent sessions using a persistent filesystem. Randy noticed the arm’s disconnected appearance during the runs and deferred investigating it so the continuity experiment could proceed. The later diagnosis identified the model limitations described here.

The arm is connected to its base through simulated joints, but some physical connecting structures are missing. That is why parts can appear to float. Those missing structures also contribute no collision geometry or mass, so this is a simplified Cartesian manipulator, not a mechanically complete robot or a demonstration of real-hardware performance. [Read the diagnosis](Post-Experiment%20Preparation/2026-10-23/DIAGNOSIS.md).

The short video below follows three examples: creating and reusing a throwing program, resuming unfinished toy cleanup, and recovering a dropped cup across sessions. The cup sequence also identifies a human-directed checkpoint restoration after an infrastructure failure. Recorded-state reconstructions and original camera frames are labeled separately.

https://github.com/user-attachments/assets/087c06ea-d992-440f-b296-de1901f67c94

**[Watch or download the 2:20 video](Post-Experiment%20Preparation/2026-10-23/video-production-2026-10-23/deliverables/three-sessions-later-session76-v3.mp4)**  
*Silent, with on-screen text. [Transcript](Post-Experiment%20Preparation/2026-10-23/video-production-2026-10-23/captions.txt) · [Sources and verification](Post-Experiment%20Preparation/2026-10-23/video-production-2026-10-23/README.md)*

The records demonstrate files surviving, being read in later sessions, and programs being reused. They do not establish that memory alone caused better performance: the simulated world also persists. These are selected examples, not a controlled comparison or proof of general robotic capability.

## How Collaboration Station 2.0 fits in

[Collaboration Station 2.0](https://github.com/Dandelion-Engineering/Collaboration-Station-2.0) organizes the development work in a shared filesystem: project context, human–agent conversations, plans, evidence, and session handoffs. A new development session can recover the project’s state rather than rely on one long conversation.

That development workspace is distinct from the persistent files available to **Robot Codex inside the experiment**. Both are visible in the working record.

## How Randy works with AI

Randy talks through ideas, results, and next steps with ChatGPT using voice in project threads. ChatGPT helps interpret the repository and turn those discussions into written directions for Codex. Codex implements and tests the agreed work, records what happened, and hands the results back for another discussion. The repository messages preserve those directions, often drafted by AI on Randy’s behalf; they are not recordings of the voice conversations themselves.

## Explore the working record

- [Human–Codex conversations](chats/Codex-Human/) — decisions, requests, and responses.
- [Session reports](agents/Codex/Session%20Summaries/) — what was attempted, completed, and left unresolved.
- [Experiment code and documentation](Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/) — the historical apparatus and workflow.
- [Highlight evidence](Post-Experiment%20Preparation/2026-10-23/HIGHLIGHTS.md) — source references, continuity checks, and limitations behind the examples.

## Licensing and citation

Original project code is available under the [MIT License](LICENSE), and original prose, templates, and media under [CC BY 4.0](LICENSE-docs). Third-party materials retain their own terms. See [license scopes](LICENSING.md), [third-party notices](THIRD_PARTY_NOTICES.md), and [citation metadata](CITATION.cff).

## Contact

**Randy Crespo, founder of [Dandelion Engineering](https://github.com/Dandelion-Engineering).**

If this work or the way it was made resonates with you, whether you’re a researcher, an engineer, working on related problems, or simply curious, Randy would welcome hearing from you. Thoughtful questions and critiques are always welcome. Randy is also open to paid projects and consulting opportunities.

- **LinkedIn:** [linkedin.com/in/randy-crespo](https://www.linkedin.com/in/randy-crespo)
- **Email:** [randy@dandelionengineering.com](mailto:randy@dandelionengineering.com)

*This README was drafted by AI at Randy’s direction.*
