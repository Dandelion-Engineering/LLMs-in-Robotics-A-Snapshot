# Long-Horizon Adaptive Robotics Experiment



---

**Randy (2026-09-22 11:31 PDT):**

Here is the next task.

# Initial Task — Design the Long-Horizon Adaptive Robotics Experiment

Codex, I want to move the **LLMs in Robotics** project from broad discovery toward an ambitious engineering experiment.

This assignment is **only to design the experiment**. Do **not** propose the competing robot architectures yet, do not choose where the LLM will sit in the stack yet, and do not begin implementing those architectures. We will do that in a separate step after the experimental arena is written down.

Create a folder in the **root of this project** named:

```text
Long-Horizon Adaptive Robotics Experiment Design
```

Use that folder as the durable home for the experiment design. You may structure the contents inside it however you think is clearest and most useful for continuity. There should be an obvious entry point so that a future Codex session or Randy can understand the experiment without reconstructing this chat.

---

# 1. The Engineering Idea

I want to investigate whether placing an LLM in different parts of a robotic system can substantially improve three connected capabilities:

1. **Long-horizon task completion**
   - preserving the overall goal over many actions;
   - remembering what has actually been completed;
   - maintaining continuity through long tasks, interruptions, model-context changes, or runtime restarts;
   - and avoiding repeated, forgotten, or contradictory work.

2. **Error correction and adaptation**
   - recognizing when an action failed;
   - noticing when the physical world no longer matches prior expectations;
   - responding to unexpected occurrences;
   - revising plans or executable behavior;
   - recovering from failure rather than simply stopping or repeating the same action;
   - and knowing when more observation or human help is needed.

3. **Better physical execution**
   - reducing unnecessary hesitation, stop-start behavior, contradictory commands, and poor transitions;
   - allowing higher-level decisions to become effective physical behavior;
   - supporting useful changes while an overall task is already underway;
   - and improving movement quality without achieving “smoothness” merely by moving extremely slowly or ignoring important corrections.

These are not three independent projects. They are parts of one larger goal:

> **Build a robot that can keep a useful physical job moving over time: retain what it is trying to accomplish, understand enough of what has happened to continue intelligently, respond when reality changes, and turn revised intentions into effective action.**

The future experiment should let several complete architectures attempt this same overall challenge.

---

# 2. Shared Design Hypothesis: Filesystem-Based Continuity

There is one architectural idea that I want **all future candidate architectures** to include.

Each architecture should use a **persistent filesystem-based continuity system inspired by Collaboration Station**.

Do not interpret this as “copy Collaboration Station into the robot.” The goal is to transfer the useful principle:

> **The robot should not depend on one model context containing everything required to finish a long physical task. Important state should survive individual model calls, context limits, interruptions, reconnections, and runtime restarts, and the context that matters should become available when it is needed.**

The memory systems I have read about so far often look too much like scratchpads or simple episodic summaries. I want to explore something more operational.

The filesystem should help preserve distinctions such as:

- what the human asked the robot to accomplish;
- the current task or subtask;
- what the robot currently believes about the relevant world;
- what has been **observed** versus inferred;
- what has been planned;
- what action was requested;
- what action was actually dispatched;
- what is currently executing;
- what outcome was observed;
- what work has been **verified complete**;
- what remains unresolved;
- what changed unexpectedly;
- human corrections or preferences;
- useful environment knowledge;
- and procedures or solutions worth reusing.

For example, these are not equivalent:

```text
I intend to move the object.
I issued the movement command.
The movement appears to have executed.
I observed the object in the intended destination.
The placement is verified complete.
```

The continuity system should make it possible for the robot to resume intelligently even when only some of those events occurred before an interruption.

It does **not** need to store every raw sensor sample or every transient controller variable as a file. Fast-changing state can remain in appropriate runtime systems. The filesystem is for **durable consequential context, task continuity, retrieval, and reconciliation with the current physical world**.

The exact filesystem structure is **not** being prescribed here. Designing candidate implementations of this idea belongs to the later architecture-design phase.

However, the experiment you design now must be capable of testing whether this continuity idea is genuinely useful. Plan for an appropriate simple-memory or no-persistent-continuity control/ablation later, without treating that control as one of the main future architecture proposals.

---

# 3. Do Not Design the Architectures Yet

This boundary is important.

In this assignment, do **not**:

- propose the set of candidate architectures;
- choose the LLM's location in the robotics stack;
- decide whether the LLM directly selects skills, writes programs, modifies controllers, changes parameters, or does something else;
- choose whether the runtime uses one reasoning agent or multiple agents;
- decide whether code modification happens online, between episodes, or not at all;
- decide which architecture should be favored;
- or begin implementing architecture-specific logic.

Those are the next design problem.

The job now is to create a **fair, revealing, architecture-flexible experimental arena** in which several meaningfully different complete approaches can later be proposed and tested.

Design the experiment so it does not quietly privilege the first architecture you happen to imagine.

---

# 4. Commercial Physical AI Map — Read-Only Input

Use the **Commercial Physical AI Problem Map** in the central Dandelion Engineering instance to help select and ground the experimental task or task family.

The map is located at:

```text
C:\Users\cresp\Documents\Dandelion Engineering\Dandelion Engineering\Commercial Physical AI
```

Its maintenance playbook is:

```text
C:\Users\cresp\Documents\Dandelion Engineering\Dandelion Engineering\Playbooks\Commercial Physical AI Problem Map.md
```

Read the playbook before using the map so that you understand its evidence structure and how its records are meant to be interpreted.

### This map is strictly read-only from this project

The **LLMs in Robotics** project may inspect and use the map as evidence, but it does not own it.

Do **not**:

- edit any Commercial Physical AI Problem Map entry;
- add a problem;
- correct a record;
- update its evidence;
- regenerate its views;
- change its schema;
- run its maintenance process in a way that writes to the map;
- or modify its playbook.

Only the agent operating inside the central **Dandelion Engineering** Collaboration Station may maintain that resource.

If you find an apparent error, important missing problem, outdated claim, or useful addition, record the observation inside this project's experiment-design materials as a potential Dandelion follow-up. Do not change the commercial map yourself.

### How to use the map for this assignment

Use it to identify a physical task or task family where the commercial problem naturally puts pressure on the capabilities we want to investigate:

- sustained multi-step execution;
- dependence between earlier and later actions;
- meaningful physical state that can change during the task;
- realistic opportunities for failure;
- unexpected occurrences that should cause adaptation;
- and physical execution where latency, unnecessary stopping, or poor movement can matter.

Do not choose a task simply because it makes an LLM look useful.

The experiment should remain meaningful even if a future result shows that the best architecture uses an LLM much less than expected.

Preserve the map's distinction between commercial evidence, technical interpretation, and Dandelion feasibility. Cite the specific map records and underlying sources that materially influence the experiment design.

---

# 5. Use This Project's Literature Map Selectively

Use the **LLMs in Robotics Literature Map** and its playbook as a second input to the experiment design.

Use it **selectively**, not as a template that dictates the architecture.

The literature should help with questions such as:

- what kinds of long-horizon robot evaluations have been attempted;
- known failure modes in LLM/robot systems;
- memory and continuity evaluation;
- closed-loop adaptation and recovery;
- sensor/state grounding;
- timing and latency;
- asynchronous reasoning and control;
- generated code or executable policies;
- movement/control evaluation;
- simulation-to-real limitations;
- common benchmark traps;
- privileged information;
- human intervention;
- and what existing work reveals about fair comparisons.

Use relevant original papers when the map indicates that important experimental details cannot be responsibly inferred from the record alone.

Do **not** use the literature map in this assignment to:

- generate the candidate architectures;
- constrain future architecture proposals to approaches already in the literature;
- assume an existing benchmark is automatically the right experiment;
- or turn the experiment into a reproduction of a paper.

The purpose of using the literature now is to make the **arena, measurements, controls, and failure cases more intelligent**, while keeping the future design space open.

The experiment should be capable of revealing value in an architecture that does not resemble the current literature.

---

# 6. Design the Experimental Arena

Design a complete experiment that future candidate architectures can enter.

At minimum, address the following.

## A. Commercially Grounded Task or Task Family

Choose and justify a task or tightly related task family using the Commercial Physical AI Problem Map.

Explain:

- what the physical job is;
- why it matters commercially;
- who currently performs or pays for it;
- what existing automation can and cannot do;
- which parts of the task are being represented in simulation;
- which commercially important difficulties are intentionally preserved;
- and which real-world difficulties are simplified or absent.

The task should be substantial enough to expose long-horizon behavior. Do not create an artificially long list of independent pick-and-place actions merely so the episode has many steps.

Earlier actions should affect later decisions in meaningful ways.

## B. Environment

Choose an experimental environment that can realistically run under the project's current financial and compute constraints.

Specify:

- simulator or environment;
- relevant physical dynamics;
- scene structure;
- object types;
- variation across episodes;
- what can change while a task is underway;
- how environment state persists;
- how resets work;
- what information is hidden from the robot;
- what information exists only for independent evaluation;
- and what is intentionally simplified.

If a small feasibility probe is necessary to confirm that a proposed simulator, package, or logging method actually works on the current machine, you may perform that bounded check and record the result. Do not begin architecture experiments.

## C. Embodiment

Select an embodiment appropriate to the task and explain why.

The embodiment should create the physical problems necessary to evaluate the idea without making hardware complexity the entire experiment.

Consider:

- degrees of freedom;
- mobility if needed;
- sensing;
- gripper/end-effector assumptions;
- reachability;
- control interface;
- and whether a plausible future path exists from simulation to affordable physical hardware.

Do not select a humanoid or any other body merely because it is fashionable.

## D. Task Structure and Horizon

Define what makes the task genuinely long-horizon.

Specify:

- dependencies between subtasks;
- what must be remembered or reacquired;
- when progress can become ambiguous;
- what counts as task completion;
- what constitutes partial progress;
- and how task state will be independently evaluated.

Consider designing more than one difficulty level or scenario if that reveals scaling behavior without turning the experiment into a benchmark suite for its own sake.

## E. Unexpected Occurrences and Failure Opportunities

Design disturbances that are meaningful for the chosen task.

Examples may include, where appropriate:

- moved objects;
- changed destinations;
- occlusions;
- failed grasps;
- dropped objects;
- missing objects;
- temporary obstructions;
- altered scene layout;
- interrupted actions;
- communication or model-call interruption;
- runtime restart;
- stale assumptions;
- tool unavailability;
- changed human instruction;
- or other task-specific surprises.

Do not insert arbitrary chaos merely to make the experiment look difficult.

Each disturbance should test a real capability connected to the goal.

Define which disturbances are known during development and which are held out for later evaluation.

## F. Movement Quality and Responsiveness

Define what **better movement** means for this task.

Distinguish, where relevant:

- high-level indecision;
- pauses caused by waiting for inference;
- poor sequencing;
- repeated starts and stops;
- unnecessary path length;
- abrupt target changes;
- trajectory smoothness;
- excessive conservatism;
- and actual controller-level motion quality.

Use existing robotics methods as appropriate for measurement and baseline execution.

Do not define smoothness in a way that can be “won” by simply moving very slowly, refusing to adapt, or avoiding difficult situations.

If the experiment will make claims about responsiveness in a changing world, the simulation should not simply pause while an LLM thinks. Design how wall-clock or simulated inference delay will enter the experiment and what the robot is allowed to do while waiting.

---

# 7. Define an Architecture-Neutral Interface

Future architectures must be able to differ meaningfully without being impossible to compare.

Design the minimum common experimental contract needed for comparison.

This may include:

- what observations the robot may receive;
- timestamps and observation age;
- available sensors;
- permitted actions or actuator interfaces;
- access to task instructions;
- access to the persistent filesystem;
- what runtime tools exist;
- what parts of the system may be modified;
- what parts are protected;
- how an action is started, interrupted, cancelled, or superseded;
- what feedback is returned;
- and what the evaluator can observe that the candidate cannot.

Do not make this interface so high-level that every architecture is secretly forced to be an LLM skill selector.

Do not make it so low-level that every candidate must reinvent mature robotics components before testing the actual idea.

Where multiple interface levels may need to remain possible, design the experiment accordingly and explain how fair comparison can still be achieved.

---

# 8. Comparison and Control Machinery

Design the comparison methodology now, before future architectures exist.

Include appropriate plans for:

- a straightforward non-agentic or conventional baseline;
- a simple context/scratchpad or no-persistent-filesystem control for testing the continuity hypothesis;
- shared task conditions;
- equivalent observation permissions;
- comparable development opportunity;
- runtime inference accounting;
- human intervention accounting;
- held-out evaluation cases;
- repeated trials/seeds where needed;
- and independent success evaluation.

Do not assume that a single scalar “score” will summarize everything important.

Avoid designing the experiment around one architecture-specific metric.

The evaluator, test definitions, protected simulator state, held-out scenarios, and success criteria must not be editable by a runtime architecture during a scored run.

Plan how generated or modified code would later be evaluated safely if a future architecture uses that ability, without prescribing that any architecture must do so.

---

# 9. Development vs. Evaluation

Design a clear distinction between:

**development conditions**, where future architectures may be debugged, improved, and exposed to feedback;

and

**evaluation conditions**, where we test whether the resulting approach handles unseen combinations, disturbances, layouts, or other relevant variation.

The future architecture-design phase should be free to be ambitious. The evaluation phase should make it difficult to obtain a convincing result simply by repeatedly adapting to the exact scored episodes.

Specify:

- what can be tuned;
- what gets held out;
- when evaluation begins;
- how much architecture-specific development effort should be recorded;
- and how to avoid giving one candidate effectively unlimited tuning while others receive little effort.

Do not overengineer a competition protocol. The purpose is informative engineering evidence.

---

# 10. Measurements

Define a measurement set that lets us understand **how** a system succeeds or fails.

Depending on the chosen task, include appropriate measures of:

- full task completion;
- partial task completion;
- time to completion;
- human intervention;
- failure detection;
- recovery success;
- recovery time;
- repeated actions;
- contradictory actions;
- stale-state or stale-memory errors;
- task-state mistakes;
- incorrect claims of completion;
- unresolved actions handled correctly or incorrectly;
- unnecessary observations;
- unnecessary motion;
- path or action inefficiency;
- motion pauses;
- latency;
- responsiveness to changed conditions;
- trajectory or control quality where relevant;
- runtime model/API use;
- compute;
- and cost.

Separate **runtime cost** from **development cost**.

The robot or LLM must not grade its own success. Use independent simulator/evaluator state and clearly defined task outcomes.

Do not add metrics merely because they are customary. Every important metric should correspond to a behavior or cost we care about.

---

# 11. Filesystem Continuity Evaluation

Even though all serious future architecture candidates will include the filesystem-based continuity idea, the experiment must let us investigate its contribution.

Design situations that reveal whether the continuity system handles:

- context loss;
- model-call boundaries;
- runtime restarts;
- interrupted actions;
- ambiguous completion;
- stale environment knowledge;
- changed physical state;
- resumption after time away;
- corrections;
- and retrieval of previously useful information.

Plan an appropriate simpler-memory comparison or ablation.

Design evaluation around **behavior**, not around how many files exist or how much text was written.

A filesystem that perfectly preserves an incorrect belief is not successful memory.

The system should ultimately be judged on whether persistence helps the robot continue and adapt correctly in the physical task.

---

# 12. Evidence Capture and Replay

Design the logging system as part of the experiment.

For important episodes, we should eventually be able to reconstruct a chain like:

```text
world state/change
    ↓
robot observation
    ↓
available and retrieved persistent context
    ↓
decision
    ↓
generated program / requested action / changed target
    ↓
lower-level execution
    ↓
physical outcome
    ↓
updated task state
```

Capture enough synchronized evidence to determine where a failure entered the chain.

Potential evidence includes:

- simulator ground truth for evaluation;
- robot-visible observations;
- timestamps;
- action requests;
- controller/executor feedback;
- relevant filesystem snapshots or diffs;
- retrieved context;
- model/tool calls;
- generated code where applicable;
- task-state transitions;
- trajectories;
- failures;
- recoveries;
- latency;
- and resource usage.

Do not indiscriminately save enormous raw streams if a lighter representation provides the evidence we need. Preserve enough raw or reproducible information for consequential cases.

Specify what must be logged during every run versus what can be captured only for selected diagnostic episodes.

---

# 13. Design the Future Human Investigation Experience

As part of the experiment design, define **how the results should eventually be made investigable by Randy**.

Read the project's **HTML Interactive Reports** playbook for principles such as:

- system-first understanding;
- progressive depth;
- meaningful interactivity;
- evidence provenance;
- mechanism-first explanations;
- original-source access;
- and distinguishing evidence from interpretation.

Do **not** assume the final artifact should be a conventional HTML research report.

Adapt those principles to what this project actually needs. The eventual result may be better understood as an **interactive engineering investigation environment**.

Design what the future interface should let Randy do.

Useful possibilities may include:

- replaying representative episodes;
- moving through a synchronized timeline;
- seeing what changed in the simulated world;
- seeing exactly what the robot was allowed to observe;
- inspecting which filesystem context existed and which context was retrieved;
- viewing task-state transitions;
- seeing the LLM's decision or generated program;
- inspecting motion or action traces;
- comparing the same disturbance across architectures;
- jumping from a failure to the point where it first became likely;
- comparing common successes and common failures;
- highlighting unusual behavior from an otherwise weaker architecture;
- opening the relevant robotics concept or mechanism when a failure exposes something Randy should learn;
- and following important technical explanations back to original papers or implementations.

The interface should help Randy answer:

> **What happened? Why might it have happened? What evidence supports that explanation? What do I need to understand to participate in the next engineering decision?**

### Design this now because it affects what the experiment must capture

Specify:

- what evidence the future interface requires;
- which views or interactions would actually improve investigation;
- which parts should be quantitative;
- which representative episodes should be preserved;
- and how the interface should distinguish measured behavior, source-reported facts, Codex interpretation, and hypotheses.

Do not fully build the final interface during this assignment unless a tiny prototype is necessary to prove that the proposed logging/replay structure is technically viable.

The real interface should later be built around actual experiment outputs, not invented placeholder results.

---

# 14. Learning Through Engineering

One purpose of this experiment is to let Randy learn the robotics concepts that become important **because we observed something real**.

Do not front-load Randy with a general robotics curriculum as a prerequisite for this project.

Design the experiment and evidence return so that after the future architectures have run, Codex can identify:

- common failure modes;
- common successes;
- meaningful differences;
- interesting anomalies;
- likely causes;
- unresolved explanations;
- and the robotics concepts, papers, algorithms, interfaces, or mechanisms that Randy should understand to investigate those observations.

The desired loop is:

> **build → observe → identify the consequential mechanism → learn what is needed → Randy contributes ideas/judgment → design the next iteration**

This does not mean concepts outside the observed failures are forbidden. It means the experiment should make targeted human learning possible rather than assuming Randy must master the traditional robotics stack before contributing.

---

# 15. Feasibility and Resource Plan

Design the experiment for the resources actually available to this project.

Account for:

- the current desktop;
- GPU memory;
- CPU/RAM;
- storage;
- shared compute with other Dandelion/[lab name redacted] work;
- software/platform compatibility;
- model/API cost if remote models might later be evaluated;
- and the current lack of budget for new hardware.

Prefer a design where the important questions can first be tested in simulation.

Do not reduce the ambition merely because the final physical system would require more resources.

Instead distinguish:

- what can be tested now;
- what can be approximated;
- what would need future hardware;
- and which conclusions simulation cannot establish.

Do not purchase anything or create paid accounts in this assignment.

---

# 16. What the Experiment Design Must Return

Inside:

```text
Long-Horizon Adaptive Robotics Experiment Design
```

leave a durable design package that makes clear:

- the engineering question;
- the chosen commercial task/task family and why it is useful;
- the environment;
- embodiment;
- task structure;
- disturbance design;
- filesystem-continuity requirements;
- architecture-neutral interfaces;
- development/evaluation split;
- baselines and ablations;
- measurements;
- timing/latency treatment;
- evidence capture;
- replay/logging plan;
- human investigation-interface requirements;
- feasibility and resource assumptions;
- important design alternatives considered;
- unresolved questions;
- risks and confounds;
- and the exact boundary between this experiment design and the later architecture-design phase.

You may organize these materials however you think produces the clearest durable engineering record.

Do not create unnecessary bureaucracy or duplicate the same information across many files.

The package should be detailed enough that the next assignment can say:

> **Now design several meaningfully different complete architectures to enter this experiment.**

without needing to reconstruct the experimental assumptions from chat history.

---

# 17. Scope and Stopping Point

This assignment authorizes:

- reading the Commercial Physical AI Problem Map **without modifying it**;
- using this project's Literature Map and relevant primary sources;
- investigating simulators, robot embodiments, evaluation methods, and available implementations;
- small feasibility checks needed to validate important experiment-design assumptions;
- designing the experiment;
- designing the evidence/logging requirements;
- designing the requirements for the future human investigation interface;
- and writing the complete design into the root-level experiment-design folder.

This assignment does **not** authorize:

- proposing the candidate architectures;
- selecting where the LLM goes in the robotics stack;
- implementing the candidate architectures;
- running the architecture comparison;
- modifying the Commercial Physical AI Problem Map;
- changing Dandelion Engineering strategy;
- buying hardware;
- creating paid accounts;
- contacting external people or companies;
- or starting a separate project.

When the design is ready, return one concise handoff that tells me:

- which commercial task/task family you chose;
- why the experiment is a good test of the larger idea;
- what the experimental arena looks like;
- what the most consequential design decisions were;
- what remains uncertain;
- where the design lives;
- and what I should inspect before we move to architecture design.

Do not propose the architectures in that handoff.

**Stop there. We will review the experiment design together before asking for competing architectures.**

---

**Codex (Session 2, 2026-09-22 11:54 PDT):**

The experiment design is ready for review. Start with the [design entry point](../../../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/README.md), then inspect the Arena and Experimental Contract.

I chose small-batch machine tending: loading, processing, inspecting and routing parts while fixtures, finite staging, order changes and interruptions make earlier actions matter later. The arena uses MuJoCo, a simulated Panda arm and a noncutting processing station. Commercial-map CP-003 and its original sources ground the job; the central map was read only.

The important choices are independent physical outcome checks, a world that keeps advancing during inference, several permitted control interfaces, and paired persistence ablations alongside a competent conventional baseline with normal durable records. The package also specifies measurements, evidence/replay and Randy's future investigation interface.

A tiny local MuJoCo probe passed contact, RGB/depth rendering, state restoration and stepping during a mock inference wait. It does not validate the full workcell, grasping, perception or protected execution. Those remain explicit implementation gates. Four literature records received selective full-text skims; no paper result was reproduced.

Please inspect the task/dependencies, sensing assumptions, continuity controls and open gates before we move to architecture design. No candidate architectures, LLM placement or runtime model have been proposed. This assignment stops at design review.

---

**Randy (2026-09-22 18:06 PDT):**

This looks great! So we need a good way to keep track of the different architectures we test. Can you create something akin to the literature map that will help us keep track of them? It should include everything we need to know about the architecture and how it works, a place for the results, maybe a place to put interesting happenings, maybe a place for general notes about the experiment with that architecture, etc. I will let you come up with the exact structure and name for this. It should be easily searchable as you must create different architectures so you must know what previous architectures have been tried and the results of their experiments. This map needs to be flexible though so that the types of architectures we can test aren't restricted. Create this map, create its playbook and edit Project Details.md to include this playbook. 

Another thing, can you actually make a Long-Horizon Adaptive Robotics Expirement folder in the root directory. Transfer the Long-Horizon Adaptive Robotics Experiment Design folder into this folder and place the folder for the map in it as well. Just to be more organized and in case we run different types of experiments here.

Don't create any architecture candidates yet.

---

**Codex (Session 3, 2026-09-22 18:22 PDT):**

Created the [Architecture Map](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Architecture%20Map/README.md) and moved the existing design into the [experiment folder](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/README.md), using the folder name you requested.

The map links architecture identities, exact revisions, individual runs, results and investigation notes. It supports full-record search, linked history, flexible mechanism descriptions, evidence references and corrections that preserve the original results. Its playbook is now listed in Project Details; current navigation and literature references point to the relocated design.

All 17 map regression tests pass, structural validation passes, and the checked local links resolve. The map is intentionally empty: no architecture candidates, runs or results were created. We are ready for your next direction on architecture design.

---

**Randy (2026-09-22 19:08 PDT):**

Alright, let's go ahead and get the experiments started! Let's start by having you create 3 different architectures. This will be the first batch. So once these are done you can create the engineering investigation workspace for me.

---

**Codex (Session 4, 2026-09-22 19:35 PDT):**

Your live-session clarification is now the operative scope: "you should design the architectures and run the complete experiments. So you also need to do anything required to be able to run the experiments."

I am implementing the three candidates and the shared physical arena, sensing, local model runtime, isolated candidate processes, evaluator and evidence capture. Three initial proposed mechanisms are registered in Batch 01; the conventional baseline is separate. The investigation workspace will use actual recorded evidence. Calibration and development checks will remain distinct from scored results, and the existing experimental contract remains the standard.

---

**Codex (Session 4, 2026-09-26 11:42 PDT):**

The first batch's experiments, fixed analysis and Engineering Investigation workspace are complete. [Open the current viewer](http://127.0.0.1:8778/Engineering%20Investigation%20007/site-r4-003/index.html#view=analysis), or start with the [results report](../../../agents/Codex/Session%20Summaries/HumanReport4.md). The [experiment entry point](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/README.md) explains how to restart its local server.

There are 264 honest planned dispositions: 263 normal terminals and one administrative interruption with unknown physical outcome. Whole-block exclusions leave 253 eligible records. Persistent task successes were baseline 43/46, A1 0/46, A2 0/46 and A3 45/46. The baseline–A3 interval reaches zero, and the persistence ablations do not establish equivalence or that memory has no effect. Simulation and whole-system comparisons do not establish hardware reliability or isolate one component's causal benefit.

The viewer includes all 264 dispositions and the twelve predeclared traces, including the A2 timeout. Its final 203 checks passed, all twelve packaged traces reconstructed exactly, and browser checks covered images, contexts, actions, restart cutoffs, keyboard navigation and event links. Preserved failures and two interface limitations are documented. Exact frozen sources and all local evidence remain retained; Runtime Recovery 001 and Analysis 005 are explicitly distinguished from the original Runtime 004 release.

No new campaign is started. The next useful discussion is the A1/A2 failure mechanisms and the two discordant baseline–A3 pairs. I am concluding this completed assignment's chat and claims before the final scoped commit/push; actual Git publication is established by the closeout result.

---

**Randy (2026-09-26 12:42 PDT):**

I changed this chat back to active. Let's keep it open while running the long-horizon adaptive robotics experiment (unless it gets too long which I'll decide when that happens).

I actually want you to create another html report. I want this one to clearly explain what the actual task is, explain each of the architectures, have an example simulation that I could watch that shows the input and output of the llm.

So for the explanation of each architecture, I want a clear schematic of the robot stack. It should show the traditional robot stack and anywhere the llm is embedded. It should also show a clear schematic of the collaboration station-like framework the llm works in. I'll let you decide the best way to show all of this clearly. It shouldn't be a text explanation though. It needs to be more visual. Think block diagrams but again you know the architectures well so you know the best way to show this to me.

For the example simulation, I want to be able to switch viewpoints. I also want a clear view of the current input/output of the llm and a clear view of where it is writing in the collaboration station-like framework. If you don't have all of this available from the previous runs, go ahead and run some new simulations. Only run them until you get a workable simulation back where you could set this up. If one of the architectures can't do this because the architecture itself fails all the time in some way, then just let me know.

---

**Codex (Session 5, 2026-09-26 13:05 PDT):**

The [Task and Architecture Explorer](http://127.0.0.1:8778/Task%20and%20Architecture%20Explorer/index.html) is ready. It visually explains the job, each robot stack and the actual filesystem framework, then lets you watch the same recorded C01 example under all four entrants. Choose reconstructed camera angles or the original overhead recording; model input/output and historical checkpoint writes follow the playhead.

The baseline and A3 complete this example; A1 reaches2/3 accepted parts and A2 reaches1/3 at the time cap. Their full persistent batches had0/46 successes each. The failed examples still provide useful action, model and file evidence, so no new simulations were needed.

One distinction is explicit in the diagrams: the host runtime manages candidate-state.json; these LLMs have no direct file-editing tools. Alternate camera views are simplified reconstructions from recorded poses, with sample ages shown. Exact model and file content stays tied to its original timestamps; the four-run tour does not change the batch analysis.

Temporal and scene tests, data integrity checks and browser checks at375px/1280px passed. [Report sources and reproduction](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Task%20and%20Architecture%20Explorer/README.md) and [HumanReport5](../../../agents/Codex/Session%20Summaries/HumanReport5.md) contain the details. This chat stays active as requested.

---

**Randy (2026-09-26 19:36 PDT):**

This is for the session that runs after the audit storage proposed fix has been implemented. So not session 7.

# Task — Set Up Robot-Codex and Novel Recovery Challenges

I have placed the **Robot Agent Filesystem v0.1** folder in the root of the **LLMs in Robotics** repository.

I want to use this as the starting point for the next phase of the project.

For clarity, use these names consistently from now on:

- **Development Codex** = you, the Codex instance working on and developing the LLMs in Robotics project.
- **Robot-Codex** = the separate Codex agent that will operate as the thinking/recovery agent attached to the simulated robot.

Do not use “Codex” alone when the distinction matters.

This assignment is **setup and integration work**, not a new scored architecture campaign. The goal is to leave us with:

1. a small set of new, physically solvable recovery challenges that the **frozen conventional baseline** does not know how to resolve;
2. a populated experiment-specific instance of the Robot Agent Filesystem;
3. a working way to launch **Robot-Codex** into that filesystem and let it interact with the running simulation through protected robot interfaces;
4. a verified development-only integration path showing that Robot-Codex can actually read/write its workspace, inspect robot evidence, issue permitted robot actions, and return control;
5. a clear handoff to Randy before any real performance campaign begins.

Do **not** run a new large comparison matrix or claim experimental performance from this task.

---

# 1. Preserve the Existing Batch 01 Work

The completed Batch 01 experiment, frozen releases, evidence, analysis, and Engineering Investigation are historical evidence.

Do not rewrite, delete, or mutate them to implement this phase.

Create the new work separately under the **Long-Horizon Adaptive Robotics Experiment**. Choose a clear durable location, preferably something like:

```text
Long-Horizon Adaptive Robotics Expirement/
    Robot-Codex Integration 001/
```

Use the repository’s existing continuity/provenance practices where they are useful, but do not create unnecessary bureaucracy.

The root-level **Robot Agent Filesystem v0.1** should remain the reusable generic framework. Create an **experiment-specific populated runtime instance** from it rather than silently converting the generic template into a machine-tending-only framework.

Record exactly which template revision the populated instance came from.

---

# 2. Start With the Existing Workcell, Not a New Robot or Entirely New Simulator

For this phase, keep the current simulated workcell, embodiment, protected evaluator, robot body, sensing interfaces, and conventional task machinery unless a specific requirement below makes a small extension necessary.

Do **not** build a more complicated task merely to make the baseline score worse.

Instead, add a small number of **novel but physically recoverable exception situations** that expose a capability the frozen conventional baseline does not currently possess.

The distinction is important:

> We are not trying to prove that “traditional robotics can never solve this.”
>
> We are asking whether the **existing frozen conventional system** encounters situations outside its pre-engineered recovery repertoire, while the physical robot still has enough capabilities to recover if an appropriate solution can be developed.

A conventional system could potentially solve these situations if engineers later added the missing logic. That is part of the commercial question.

---

# 3. Create a Small Novel-Recovery Challenge Set

Design and implement a **small initial set** of challenge families. Two to four good families are preferable to a large benchmark.

Each challenge must satisfy all of the following:

## A. The frozen conventional baseline cannot already solve it

Demonstrate this with development runs or a direct code/behavior analysis plus a confirming run where practical.

Do not modify the baseline to teach it the recovery.

A “baseline failure” must mean that the existing implementation cannot complete or restore the task under its frozen behavior—not that the robot is physically incapable of the required action.

## B. A valid physical recovery actually exists

Before asking Robot-Codex to solve a challenge, establish independently that the robot can recover using only interfaces that are legitimately available to it.

A reference recovery may use:

- existing robot skills;
- safe manual Cartesian/joint/gripper operations;
- observation requests;
- or a small reference recovery program.

The reference recovery is **development/evaluator evidence only**. Do not expose its solution steps, hidden state, or implementation to Robot-Codex.

The purpose is to prove:

> “There is a solution available to this robot.”

not:

> “The agent should somehow overcome impossible physics.”

## C. The missing piece should involve adaptation or reasoning

Prefer situations where:

- the normal procedure becomes invalid;
- an assumed resource/location is no longer usable;
- the robot has to combine existing abilities in a new way;
- the current workflow lacks a recovery for a new state;
- the agent must gather additional information before acting;
- or a new instruction/constraint cannot be handled by the frozen task logic.

Avoid challenges where the only problem is that the motor is too weak, a target is unreachable, or required information is permanently unavailable.

## D. The solution must not be leaked

Robot-Codex may know:

- the current task;
- its robot and tools;
- the public action/history record;
- observations it legitimately requests;
- the symptom/reason it was activated.

It must not receive:

- evaluator-only ground truth;
- the reference recovery;
- the hidden challenge script;
- future disturbances;
- or a message that effectively diagnoses the problem for it.

## E. Preserve ordinary cases

Later experiments should include nominal/familiar conditions as well as new exceptions.

An agent that handles a novel recovery but makes normal automation worse is not automatically useful.

You do not need to create the full future evaluation matrix in this task, but design the challenges so this comparison remains possible.

---

# 4. Treat the Conventional Stack as the Default Worker

The next architecture should **not** replace working conventional automation with an LLM at every step.

Use this control concept:

```text
Conventional automation
        ↓
does the normal job
        ↓
possible problem / inability detected
        ↓
Robot-Codex is activated
        ↓
investigate → recover → verify
        ↓
protected handback
        ↓
conventional automation resumes
```

This is the starting architecture for this phase.

Robot-Codex is a **recovery/thinking agent**, not the normal low-level robot controller.

It may use the same skills the conventional system uses, plus the lower-level/manual interfaces and code-writing capabilities described below.

---

# 5. Initial Activation Policy: On-Demand, Not Always Awake

For this first integration, do **not** keep Robot-Codex continuously reasoning in the background.

Start with **on-demand activation** when the conventional system has encountered a condition that may require assistance.

Design a deterministic supervisor/monitor that can activate Robot-Codex based on public/allowed evidence such as:

- an explicit skill/action failure;
- repeated failure;
- an inability/stuck state declared by the frozen conventional controller;
- an unresolved prerequisite;
- no useful progress beyond a declared condition;
- or another challenge-specific public signal.

Do not use evaluator-only knowledge to trigger Robot-Codex.

Do not make normal waiting—such as an accepted process still running—look like failure.

For early integration/debugging, an operator-forced activation is acceptable as a clearly labeled fallback. It is not evidence that automatic failure detection has been solved.

The activation message should describe **why Robot-Codex was called in terms of observable symptoms**, not give it the hidden cause or recovery.

---

# 6. Populate the Robot Agent Filesystem for This Experiment

Use the root-level **Robot Agent Filesystem v0.1** as the generic source.

Populate an experiment-specific runtime workspace with at least the intended equivalents of:

```text
RobotAgentPrompt.md
Tasks.md
Robot.md
Tools.md
Continuity.md
live/
notes/
programs/
```

Follow the framework’s existing intent unless implementation evidence shows something must change. If you think the generic framework itself needs revision, document the proposed change separately rather than silently rewriting the template.

## Tasks.md

Populate it with:

- the current machine-tending job;
- current order/task semantics;
- success/handback requirements;
- what Robot-Codex is responsible for during recovery;
- what it is not responsible for.

Do not put hidden challenge answers in this file.

## Robot.md

Populate it with the actual implemented robot information Robot-Codex needs, including:

- embodiment;
- relevant coordinate frames;
- sensors/observations;
- gripper;
- operating limits;
- what the conventional system normally does;
- important timing/feedback semantics;
- enforced protections;
- known physical/software limitations.

Do not give it evaluator-only simulator internals.

## Tools.md

Document the actual callable interfaces Robot-Codex receives.

Robot-Codex should have three levels of action where feasible:

### Existing skills

Expose the skills/macros the conventional system already uses for the task.

Robot-Codex should be able to reuse them instead of recreating working robot behavior.

### Protected manual control

Provide lower-level operations needed for recovery, such as appropriately bounded forms of:

- observe/get fresh camera or structured observation;
- robot/public status;
- relative Cartesian movement in a named coordinate frame;
- absolute Cartesian target where supported;
- gripper open/close;
- bounded joint movement where justified;
- cancel/hold/status;
- other current robot interfaces needed for the workcell.

“Manual” does **not** mean unprotected.

Every manual command still passes through the same or stronger protected execution boundary that rejects invalid/unsafe commands.

### Agent-written recovery code

Robot-Codex should be able to create code under its `programs/` area and execute that code through a controlled robot-facing interface.

It may combine:

- observations;
- loops/conditions;
- existing skills;
- manual movement calls;
- public task/device state.

Generated code must **not** gain direct access to simulator state, actuator bypasses, evaluator files, safety configuration, hidden manifests, or unrestricted host resources.

If safe generated-code execution cannot yet be isolated adequately on this Windows environment, implement as much of the interface as is development-safe, clearly mark it **development-only**, and tell Randy exactly what prevents scored use. Do not fake an isolation guarantee.

---

# 7. Build a Robot-Facing Tool Surface That Feels Natural to Codex

Robot-Codex is a coding/filesystem agent. Design its robot interaction so it can work naturally from its workspace.

A local CLI or similarly inspectable interface is likely appropriate, for example conceptually:

```text
robot status
robot history ...
robot observe ...
robot skill ...
robot move-relative ...
robot gripper ...
robot run-program ...
robot request-handback ...
```

These names are examples, not required commands.

Choose the actual interface based on the current runtime.

Important requirements:

- every action has a unique identity;
- accepted/dispatched/executing/terminal/physically-verified states remain distinguishable;
- Robot-Codex can inspect command results;
- history persists independently of Robot-Codex;
- stale information is timestamped;
- the simulator/evaluator remains authoritative;
- no command can bypass the protected actuator/safety boundary.

Do not force all information into a single giant prompt if Robot-Codex can inspect it through files/tools.

---

# 8. Continuity: Let the Filesystem Carry the Agent Across Fresh Invocations

For this phase, prefer a design where **Robot-Codex may be a fresh Codex invocation each time it is activated**.

The point of the filesystem is that continuity should not depend on retaining one giant chat thread forever.

Robot-Codex should be able to reconstruct the relevant situation from:

- `RobotAgentPrompt.md`;
- `Tasks.md`;
- `Robot.md`;
- `Tools.md`;
- its own `Continuity.md`;
- its notes/programs;
- independently recorded robot history and current public state;
- fresh observations when needed.

If a persistent/resumable Codex thread is useful, it may be evaluated later. Do not make it a requirement for the first integration.

### Fixed Robot-Codex initialization prompt

Every fresh Robot-Codex invocation should be launched from the **root of its permitted runtime workspace** with this initialization prompt:

```text
Follow the instructions in RobotAgentPrompt.md.
```

This is deliberate. It is the same basic bootstrapping pattern Randy uses when launching agents into Collaboration Station.

Do **not** make the launch prompt itself carry the current diagnosis, hidden challenge details, a giant state dump, or a recovery plan. The runtime state belongs in the filesystem and robot-facing tools.

`RobotAgentPrompt.md` is responsible for telling Robot-Codex what to read next, including `Tasks.md`, `Robot.md`, `Tools.md`, `Continuity.md`, and the relevant material under `live/`.

The launch mechanism must therefore ensure:

- the current working directory is the correct per-run Robot-Codex workspace;
- `RobotAgentPrompt.md` exists there and is readable;
- the exact bootstrap instruction above is actually supplied to Robot-Codex;
- Robot-Codex can then discover and use the rest of the permitted filesystem itself.

Do not rely only on implicit `AGENTS.md` discovery or on Development Codex remembering the intended behavior. Keep `AGENTS.md` if it is useful for Codex tooling, but the explicit initialization prompt above is the required Robot-Codex bootstrap for this framework.

Challenge-specific activation information should be written to the permitted runtime files (for example `live/activation.json`) before Robot-Codex starts. A newly launched Robot-Codex should be able to begin with only the fixed bootstrap prompt and then reconstruct what it needs from its workspace.

The supervisor must continue recording robot/task events even while Robot-Codex is absent or crashed.

On restart or a new invocation, Robot-Codex must not assume its previous working belief is still true. It should reconcile durable notes with current observations and public state.

---

# 9. Launch Robot-Codex Using My ChatGPT/Codex Subscription, Not API Billing

I do **not** want to use the OpenAI API or a paid API key for Robot-Codex.

Investigate whether the installed local Codex client can launch Robot-Codex using my existing **ChatGPT-authenticated Codex account/subscription**.

Consult:

- the current official Codex documentation;
- the installed Codex CLI/app version and `--help`;
- the current authentication state.

Do not infer behavior from old docs.

Start by checking the active authentication method with an approved status command such as:

```text
codex login status
```

Do **not** print, copy, parse, log, or commit authentication tokens or the contents of credential files.

Do **not** create or request an API key.

Do **not** switch the account to API-key authentication.

Current OpenAI documentation indicates that local Codex supports **Sign in with ChatGPT for subscription access**, with cached credentials reused for local work. Determine whether that current local authentication can also support the unattended/non-interactive Robot-Codex launch we need on this machine.

### Preferred outcome

The simulation/supervisor can automatically launch a local Robot-Codex process when the activation condition is met, using the already authenticated ChatGPT Codex session.

The launch must start Robot-Codex in the correct per-run runtime workspace and provide exactly:

```text
Follow the instructions in RobotAgentPrompt.md.
```

If a local non-interactive command such as `codex exec` can use the cached ChatGPT subscription session in this environment, build and validate that path.

### If automatic subscription-authenticated launch is not supported or reliable

Do not hack around authentication, automate a browser login, scrape credentials, or silently use API billing.

Instead:

1. determine the closest supported workflow;
2. create the cleanest manual-launch fallback;
3. tell Randy exactly:
   - when the simulator will stop/hold and ask for Robot-Codex;
   - what command or action Randy must perform;
   - which directory Robot-Codex should be launched in;
   - what prompt/entry instruction it receives;
   - how the simulation knows Robot-Codex has started;
   - how control returns afterward.

If even a manual subscription-authenticated workflow cannot work with the required robot tooling, stop and explain the blocker.

---

# 10. Robot-Codex Model and Reasoning Setting

Robot-Codex must use:

```text
GPT-6 Astra
```

Start with **Max reasoning**.

Do **not** use Ultra for this phase.

The purpose is to test one strong reasoning agent, not an automatically delegated multi-agent system.

Do not intentionally enable Robot-Codex subagents during this phase.

Use the installed client's current supported representation for **Max** reasoning. Verify the exact accepted setting from current documentation/configuration rather than guessing.

Verify and record the **effective model and reasoning setting actually used**, not just the requested configuration.

If GPT-6 Astra + Max is not available through the current ChatGPT-authenticated Codex client/account, do not silently substitute another model or reasoning level. Tell Randy and stop at that blocker.

---

# 11. Isolate Robot-Codex From the Development Repository and Evaluator

Robot-Codex must not simply be launched at the root of the full research repository with permission to inspect everything.

That would give it access to:

- hidden evaluator state;
- reference recoveries;
- disturbance-generation code;
- future challenge information;
- development notes;
- prior scored outcomes;
- and potentially protected simulator internals.

Create a runtime working directory that contains only what Robot-Codex is legitimately allowed to use.

The generic framework can live in the repository, but a **per-run/per-activation working copy** should contain the populated runtime files and allowed interfaces.

Determine what actual sandbox/filesystem boundary can be enforced on this Windows system.

A directory convention alone is not a security boundary.

If robust isolation cannot be established yet:

- development-only integration work may continue where reasonable;
- clearly label the limitation;
- do not call a Robot-Codex result a protected/scored experiment;
- tell Randy what needs to change before scored use.

Do not expose account credentials inside the Robot-Codex workspace.

---

# 12. Control Ownership and Safe Handoff

Robot-Codex and the conventional controller must not command the same resource simultaneously.

Implement an explicit authority transition:

```text
conventional control
    ↓
problem trigger
    ↓
finish/cancel/hold at a protected control boundary
    ↓
Robot-Codex authority
    ↓
recovery actions
    ↓
Robot-Codex requests handback
    ↓
supervisor verifies resumption conditions
    ↓
conventional control resumes
```

Robot-Codex does not get to declare safety protections disabled.

The supervisor must independently enforce:

- actuator/workspace limits;
- interlocks;
- resource ownership;
- stale-command rejection;
- command expiry/cancellation semantics;
- whatever collision/contact constraints are genuinely implemented.

Audit what the existing implementation actually protects. Do not claim protections that are not present.

Physics/world time should not be silently paused merely because Robot-Codex is reasoning. A protected robot hold is allowed where that is the actual robot behavior, but machine/world state should evolve according to the defined simulation semantics.

---

# 13. Robot History and Activation Evidence

The conventional robot may have been working for a long time before Robot-Codex is called.

Maintain an independent append-only or equivalently reliable public history that Robot-Codex can inspect.

It should preserve enough information to understand:

- relevant task/order changes;
- observations;
- skill/action requests;
- command acceptance;
- execution/feedback;
- verification status;
- failures;
- unresolved outcomes;
- control-owner changes;
- timestamps.

Do not make this an omniscient evaluator transcript.

A missing observation remains missing.

A commanded action is not automatically a verified physical result.

Robot-Codex should be able to inspect history selectively rather than receiving an arbitrarily enormous transcript in its initial prompt.

---

# 14. Development-Only Validation Before Any Experiment

Before proposing a scored campaign, validate the infrastructure in stages.

At minimum:

## A. Authentication/model smoke check

Establish whether a local Robot-Codex invocation can:

- use ChatGPT subscription authentication;
- launch without an API key;
- use GPT-6 Astra;
- use Max reasoning;
- start in the intended runtime workspace;
- receive the exact initialization prompt `Follow the instructions in RobotAgentPrompt.md.`;
- read `RobotAgentPrompt.md` because of that bootstrap;
- follow its start/resume instructions and read the next required runtime files;
- read/write permitted files.

No robot actuation is needed for this first smoke check.

## B. Robot-tool smoke check

Using a development scene:

- read robot status;
- request a fresh allowed observation;
- invoke one existing safe skill or bounded manual action;
- observe the result;
- update continuity;
- stop.

## C. Interruption/continuity smoke check

Terminate a Robot-Codex invocation after it has written meaningful state, then activate a fresh Robot-Codex in the same permitted workspace.

Confirm that it can reconstruct the situation from the filesystem/history rather than relying on prior chat context.

## D. Control-ownership smoke check

Confirm that conventional control and Robot-Codex cannot both command the same robot resource.

## E. Generated-program smoke check

If the isolation boundary is ready, let Robot-Codex write a tiny bounded program that uses only the documented robot interface and verify that the protected supervisor still rejects an invalid command.

If isolation is not ready, defer this and record why.

---

# 15. One Development-Only End-to-End Recovery Is Allowed

Once the launch path and protected interfaces work, you may perform **one clearly labeled development-only end-to-end recovery pilot** on a challenge created for development.

The purpose is only to establish that the intended loop exists:

```text
frozen baseline encounters a problem
        ↓
Robot-Codex is activated
        ↓
Robot-Codex inspects filesystem/history/current state
        ↓
Robot-Codex gathers evidence
        ↓
Robot-Codex uses skills/manual control and/or allowed code
        ↓
physical state changes
        ↓
Robot-Codex verifies recovery
        ↓
Robot-Codex updates continuity
        ↓
protected handback
        ↓
conventional robot resumes useful work
```

Preserve the complete inspectable trace.

Do not tune repeatedly until Robot-Codex succeeds and then present the final attempt alone.

If the pilot fails, preserve the failure. That is useful development evidence.

Do not infer general performance from this pilot.

---

# 16. Do Not Start the Real Test Campaign Yet

This assignment does **not** authorize:

- a new scored architecture matrix;
- dozens of Robot-Codex trials;
- changing the completed Batch 01 results;
- a Maps + Attention implementation;
- autonomous map-maintenance agents;
- a new robot embodiment;
- a new simulator unless a hard blocker is first brought to Randy;
- API-key spending;
- paid external services;
- hardware purchases;
- or external outreach.

Maps + Attention comes later.

First we need a stable, inspectable Robot-Codex host that behaves like the filesystem-native agent Randy intended.

---

# 17. What to Return to Randy

Leave a durable setup/integration record in the new Robot-Codex integration folder.

Then return one concise handoff explaining:

1. **Challenge set**
   - what new challenge families were created;
   - why the frozen conventional baseline cannot handle them;
   - how you established that the robot can physically recover;
   - what information is hidden from Robot-Codex.

2. **Robot Agent Filesystem**
   - where the populated runtime template lives;
   - what was filled into `Tasks.md`, `Robot.md`, and `Tools.md`;
   - any changes you recommend to the generic v0.1 framework.

3. **Robot-Codex launch**
   - whether unattended launch using my ChatGPT-authenticated Codex subscription works;
   - exact supported mechanism used;
   - whether any manual involvement is still required;
   - exact manual fallback if needed.

4. **Model**
   - confirm the effective model is GPT-6 Astra;
   - confirm the effective reasoning setting is Max;
   - confirm Robot-Codex did not intentionally use subagents.

5. **Tool/control boundary**
   - which skills Robot-Codex can call;
   - which manual controls are exposed;
   - whether generated programs are enabled;
   - what protections are actually enforced.

6. **Continuity**
   - how independent robot history is recorded;
   - how a fresh Robot-Codex invocation resumes;
   - what happens after a lost acknowledgement or interrupted agent run.

7. **Isolation**
   - what prevents Robot-Codex from reading evaluator/reference/development files;
   - any remaining reason the setup is development-only rather than ready for scored testing.

8. **Validation**
   - which smoke checks passed or failed;
   - outcome of the one optional development recovery pilot;
   - exact evidence location.

9. **Next decision**
   - what Randy should review before authorizing real Robot-Codex experiments.

If automatic ChatGPT-subscription launch, Astra Max, safe robot control, or adequate isolation is not technically achievable, do not hide the issue or substitute API access. Stop at the strongest working setup and explain the blocker clearly.

**Do not begin the real performance experiments until Randy reviews this handoff.**



---

**Randy (2026-09-26 22:17 PDT):**

I want to give the Robot-Codex isolation problem one more focused engineering session before we fall back to monitored development mode. There is no deadline, so please take a serious attempt at finding an enforceable isolation boundary rather than relaxing the boundary just so Robot-Codex can launch.

The goal for this session is narrow: **find and demonstrate a practical isolation method for Robot-Codex, or establish clearly why the practical options available on this machine do not work.** Do not do another robot experiment, expand the challenge set, start Maps + Attention work, or begin a scored campaign during this session.

The required outcome is that Robot-Codex can use its own runtime workspace and the protected local robot gateway while being unable to read the LLMs in Robotics repository, evaluator/reference-recovery files, Development Codex evidence, unrelated personal files, or unrestricted network resources.

Please use real enforcement and canary tests rather than relying on instructions alone. A successful qualification should demonstrate at minimum that Robot-Codex can read its workspace, write only its intended writable areas, use the approved loopback robot interface, and is denied access to protected repository/unrelated-user canaries and non-approved network access.

You may choose the implementation. Please investigate materially different approaches rather than spending the entire session on small variations of the same failing ACL profile. Some avenues you are explicitly allowed to consider, but are **not** requirements, include simplifying the native Codex sandbox around a completely separate Robot-Codex runtime workspace, using a dedicated Windows user/security identity whose NTFS permissions enforce the boundary, restricted Windows process/token or other native OS isolation mechanisms, or a lightweight VM/container-like boundary if something already available on this machine is practical and compatible with the existing ChatGPT-authenticated Codex setup.

Treat those as suggestions, not as the architecture I am prescribing. Inspect what is actually supported on this Windows installation and by the installed Codex client, and choose the cleanest solution based on evidence.

Do not weaken isolation repeatedly until a model happens to launch and then call that success. Preserve failed approaches and their evidence. Do not switch to API-key billing or create paid infrastructure.

If you establish a qualified boundary, you may proceed only far enough to prove the actual Robot-Codex bootstrap works under that boundary: use the existing ChatGPT-authenticated Codex session, GPT-6 Astra at Max, the exact bootstrap `Follow the instructions in RobotAgentPrompt.md.`, and capture the effective startup/tool/context evidence needed to show the boundary still holds. Do not start the recovery campaign.

Give this **one focused engineering session**. If no enforceable practical boundary can be demonstrated after materially exploring the available approaches, stop rather than turning this into an endless infrastructure project. Return the strongest option you found, the specific remaining blocker, and your recommendation for the next step. We can then consciously decide whether to use the external-workspace + explicit instruction + monitored development-only fallback.

Preserve the current Robot-Codex Integration 001 evidence and historical failures rather than rewriting them.

---

**Codex (Session 9, 2026-09-26 23:56 PDT):**

The focused isolation session demonstrated an enforceable WSL2/bubblewrap boundary and an actual ChatGPT-authenticated GPT-6 Astra / Max bootstrap. The exact sole prompt was `Follow the instructions in RobotAgentPrompt.md.` Robot-Codex read all eight required startup files (outputs match frozen hashes), ran all 28 boundary canaries successfully, wrote both observation files and continuity, and successfully read back its writes. No robot experiment or actuation occurred, and Robot-Codex created no subagents.

The entire Linux executor and separate Code Mode host are confined. The runtime write split, denied repository/user/evaluator/development canaries, blocked unrestricted networking, approved authenticated synthetic gateway, and child retirement were exercised. Native Windows, AppContainer, identity and VM/WSL findings and all failed attempts remain in the evidence.

There is a launcher qualification limit: the successful third bootstrap was followed by a Windows connection-reset error during trusted client shutdown, so the outer runner returned failure even though the task and namespace retirement succeeded. Shutdown handling is corrected; later nonmodel abort/retirement checks passed without reproducing the exact reset, and I did not run another model turn. The interrupted raw artifact export and later disappearance of the temporary WSL runtime mean durable outputs are explicitly derived from successful tool/readback traces, not mislabeled as later raw-file exports. A clean complete launcher run and durable retention remain prerequisites before robot integration.

Start with [HumanReport9](../../../agents/Codex/Session%20Summaries/HumanReport9.md) and the [focused handoff](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/isolation-session-9/README.md). I recommend retaining this enforced WSL boundary instead of falling back to instruction-only monitored mode. I am stopping for your review before any recovery experiments.

Git continuity: Session 8 saved its report/summary/handoff but did not append a chat reply. The uncommitted addition was your earlier 19:36 task. I preserved it, pulled your GitHub 22:17 follow-up, and appended this response without rewriting the original transcript prefix. This session's scoped closeout includes all three portions together; the preservation stash remains an extra backup.


---

**Randy (2026-09-27 09:13 PDT):**

I reviewed the Session 9 result. Great work — keep the **WSL2 + bubblewrap isolation boundary**. Do not fall back to instruction-only monitored mode unless this enforced approach later proves unusable.

I am authorizing the remaining bounded engineering and qualification work needed to make Robot-Codex genuinely ready for the first recovery experiments. The goal of this session is to finish the path from the now-demonstrated isolated Astra Max bootstrap to a robot-connected, restartable, inspectable development system that we can confidently freeze for an initial experiment.

Please use your judgment on implementation details, but at minimum close the remaining gaps that matter before a real Robot-Codex run:

- qualify a **clean complete launcher run** under the same enforced boundary using the existing ChatGPT-authenticated Codex session, GPT-6 Astra at Max, and the exact bootstrap `Follow the instructions in RobotAgentPrompt.md.`;
- make the runtime/model outputs and relevant artifacts **durably retained even across normal shutdown, client failure, and namespace teardown**, and verify that the corrected shutdown path actually works;
- connect the **real protected robot/actuator gateway** through the same constrained broker without widening filesystem or network access, and prove with canaries that the previous isolation guarantees still hold;
- finish any launcher↔host lifecycle/control-authority bridge needed so an old Robot-Codex process cannot keep or reacquire control after retirement/restart;
- run the original staged Robot-Codex smoke checks with the **actual model**, not only synthetic clients: filesystem/bootstrap, robot status/observation, one bounded safe robot action, actual fresh-invocation continuity/reconciliation after interruption, and protected handback/ownership fencing;
- address the atomic continuity/restart mechanics to the degree actually required for those fresh-invocation tests;
- if agent-written recovery programs are going to be available in the first experimental architecture, qualify a bounded program-execution path before exposing that capability. If you determine that capability should remain disabled for the first experiment, make the architecture and tool surface explicit about that rather than leaving an unqualified route accidentally available.

You are also authorized to use the **single development-only end-to-end Robot-Codex recovery pilot** that was already contemplated in the original integration task once the preceding gates pass. Use one of the existing protected development challenges. Preserve the complete trace whether it succeeds or fails; do not tune/retry until success and do not interpret one pilot as performance evidence.

Do not start a scored campaign, parameter sweep, Maps + Attention work, or a new architecture comparison in this session.

Some items from Session 9 such as complete full-host restart recovery or per-program resource accounting may or may not be necessary before the first bounded experiment. Decide based on the actual architecture and failure model rather than creating process for its own sake. If something can legitimately remain a documented limitation for the first experiment, say so clearly. If it is necessary for scientific validity or safe control, finish it before declaring readiness.

At the end, update/register the exact architecture revision that is actually ready to test, preserve all prior failed attempts and development evidence, and return a concise handoff telling me:

1. whether the launcher now completes cleanly;
2. whether durable evidence retention is verified;
3. whether the real robot gateway is isolated and working;
4. which actual-model smoke stages passed or failed;
5. what happened in the optional single recovery pilot, if used;
6. what capabilities Robot-Codex will and will not have in the first experimental architecture;
7. any remaining limitations;
8. whether you consider the system **ready to begin the first real Robot-Codex experiment**.

Stop for my review once that readiness work is complete. Do **not** begin the experimental campaign automatically.

---

**Codex (Session 10, 2026-09-27 10:06 PDT):**

The readiness work and the single authorized development pilot are complete. Start with [HumanReport10](../../../agents/Codex/Session%20Summaries/HumanReport10.md), the [eight-part handoff](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/readiness-session-10/README.md), and the [system diagram](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/readiness-session-10/Mechanism.md).

1. **Launcher:** clean actual ChatGPT-authenticated GPT-6 Astra / Max runs with the exact sole bootstrap. Native clients exited 0; Robot-Codex used no subagents.
2. **Retention:** actual runtime bytes, transcripts, protected history, continuity and program admissions survived normal completion, deliberate invocation failure and namespace teardown.
3. **Gateway:** the real robot interface works through the unchanged WSL2/bubblewrap enforcement concept and fixed broker; all 45 canaries passed in actual model traces.
4. **Smoke:** 25 bootstrap and 48 physical/restart gates passed, including cancelled-action reconciliation without replay, invalid-command rejection and protected handback rejection. The earlier pre-inference Windows sharing failure remains preserved as invalid infrastructure evidence.
5. **Pilot:** one unretried success. Robot-Codex moved A1 from quarantine to parking1, verified placement and handed back. Five conventional commands then completed processing, inspection and delivery; the independent evaluator accepted A1 in tray1 with the required settling dwell.
6. **Capabilities:** filesystem continuity, structured sensing/history, native skills, protected manual controls and bounded agent-written Python. No evaluator access, free network, persistent controller or model image-viewing tool.
7. **Limits:** the pilot host completed before two final launcher queries, so those late retirement/token-probe receipts are absent and its strict assessment remains 26/28. A separate supplement records the actual handback epoch fence, a subsequent live HTTP403, namespace retirement and clean host closure. Full-host restart, power/disk failure, aggregate resource exhaustion and complete collision protection remain unqualified.
8. **Readiness:** I consider exact **RCI001-wsl-010d** ready for a first bounded simulation experiment after your review, within these limits. The Architecture Map preserves all attempts and the explicit scope judgment. One pilot is not performance evidence.

I am stopping for your review. No scored campaign, sweep, Maps + Attention work or new comparison has started. The generic framework, baseline/evaluator and completed Batch 01 remain unchanged.

---

**Randy (2026-09-27 11:20 PDT):**

I reviewed the Session 10 readiness result and approve beginning the **first real Robot-Codex experiment** using the exact qualified **RCI001-wsl-010d** framework.

For this phase, test **this Robot-Codex framework only**. Do not design or test additional LLM/robot frameworks, start a new architecture comparison, or begin Maps + Attention work yet. Continue using the frozen conventional baseline, protected evaluator, reference machinery and other existing controls where the experimental contract requires them, but the new thing under test is RCI001-wsl-010d.

Before you launch the experiment, inspect the actual evidence from the completed Batch 01 campaign and use it to right-size this campaign. The previous campaign took roughly three days and produced 264 planned dispositions. I want enough independent attempts that the results are genuinely informative, but I do **not** want us to automatically repeat a campaign of that size if a substantially smaller design can answer the first questions responsibly.

Use the prior campaign's empirical runtimes, completion/failure behavior, variance and other relevant evidence to choose and justify a **predeclared attempt count and challenge/seed allocation** for this first Robot-Codex experiment. The design should be materially shorter than the previous campaign if the evidence supports that, while still giving us enough repeated attempts to say something meaningful about the observed success/failure patterns rather than relying on a handful of anecdotes.

You may use an appropriate statistical or engineering justification—for example uncertainty/interval width, repeated seeds, coverage of the recovery challenge families, or a staged design with stopping/continuation rules fixed **before** seeing the new outcomes. Do not choose the number merely because it is convenient, and do not keep adding or retrying runs until the result looks good. If a smaller campaign cannot support a strong claim, narrow the claim instead of pretending the sample supports more than it does.

Record the proposed experiment plan and its runtime/sample-size justification **before the first scored attempt**, then freeze the relevant architecture/protocol for this campaign and proceed with the experiment. Preserve every valid attempt and every failure. Do not tune RCI001-wsl-010d after seeing scored outcomes, do not retry until success, and keep the independent evaluator and complete inspectable evidence chain. Handle infrastructure-invalid attempts only according to rules declared before the campaign begins.

When this first experiment is complete, build or update the human investigation material from the actual results so I can inspect what Robot-Codex did, including representative successes, failures, continuity behavior, recovery decisions and anything unexpected. Then stop for review before expanding into another campaign, an ablation, a simpler-agent comparison, another architecture, or Maps + Attention.

The goal of this first campaign is not to prove the entire framework universally. It is to get a disciplined first body of real experimental evidence about how this exact filesystem-native Robot-Codex framework behaves on the recovery problems we built, while keeping the runtime practical enough that we can iterate.

---

**Codex (Session 11, 2026-09-27 11:43 PDT):**

The first exact RCI001-wsl-010d campaign is prepared but has not launched. [HumanReport11](../../../agents/Codex/Session%20Summaries/HumanReport11.md) and the [campaign entry point](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-001/README.md) contain the pre-outcome plan, sealed 24-slot allocation, actual Batch 01 sizing evidence and admission findings.

I selected 12 attempts per existing recovery fixture, fresh sensor seeds and independent episode workspaces, fixed world seed 173, no replacements or outcome-driven extension. This narrows the claim to fixed-fixture repeatability. Host caps sum to 7.33 hours before outer overhead; Batch 01 occupied 38.01 queue-hours over 59.86 elapsed hours. All 624 qualified source files remain unchanged. Ten external-assessment tests and four census tests passed; the retained exact 010d pilot supports the declared timing calibration with explicit journal interpolation limits. No new Robot-Codex or simulation call occurred.

The remaining human choice is storage: the fresh authenticated census measures 175.842 GB in Evidence alone, exceeding your September 26 provisional 150 GB ceiling even after model/hardlink overcount is removed. The prepared campaign reserves 28.770 GB permanent / 37.962 GB peak, leaving 380.992 GB free C:. May this one campaign use up to 37.963 GB additional peak storage, preserving all existing evidence and the 100 GB free reserve? The alternative is to keep the ceiling and defer until separately authorized normalization. This requests a specific storage exception, not general experiment authorization again; your September 27 instruction already grants the latter.

I have preserved the plan, source identities, failed/valid census receipts, preparation-only map note and resumable assessment tooling. Scientific admission remains closed pending that decision and final external accounting/timing/release binding. No scored result or actual-results viewer is invented. Once admitted, the fixed campaign and result-based investigation remain the intended work, followed by your requested review stop.

---

**Codex (Session 12, 2026-09-27 11:58 PDT):**

Randy's explicit storage approval from the originating task is now recorded in [the Session 12 approval amendment](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-001/admission/storage-approval-session12.md): “Approved. Don’t be super strict about the allowance though. If for some reason you go over it’s ok. Just use your reasoning about when is ok to continue the experiments and when I should be notified about ballooning storage.” The 37.963 GB peak is a planning allowance with modest explainable overruns authorized; the existing footprint above 150 GB no longer blocks this campaign. Preserve historical evidence and the 100 GB free reserve; notify on unexpected growth or threatened capacity.

Session 12 owns the saved-checkout lock after a clean fast-forward-only pull. I am completing external accounting and scientific admission binding, then executing the sealed 24 fixed attempts through the shared queue and building the requested investigation. Exact RCI001-wsl-010d, all fixed seeds and no-replacement/no-tuning rules remain unchanged. The originating task is not running a parallel campaign. No further experiment or storage approval is needed.

---

**Codex (Session 12, 2026-09-27 13:20 PDT):**

Campaign 001 is complete at its predeclared stop. Slots 9 (stock05 transport/client closure failure) and 10 (home05 timing failure) were consecutive infrastructure-invalid attempts, so the remaining fourteen slots were never submitted. All 24 dispositions are recorded: six valid successes, four infrastructure-invalid attempts, fourteen not run. All ten started evaluators observed success; the four invalid scored outcomes remain unknown. No replacements or framework changes followed the results.

The [interactive investigation](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-001/investigation/report.html) connects the system, ownership, model/tool decisions, admitted and verified actions, continuity and actual outcomes, with 128 original camera frames and raw evidence links. [Findings and limits](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-001/investigation/OVERVIEW.md) and [HumanReport12](../../../agents/Codex/Session%20Summaries/HumanReport12.md) provide the compact written handoff. Last preselected episodes remain visibly unrun. Browser interaction QA is unavailable under the tool's explicit URL-policy refusal; static checks and original-image inspection are recorded separately.

The useful behavioral result is recovery followed by conventional productive work: stock required one transport; the first home episode needed a second repair after handback was rejected because the conventional setup retries were exhausted. Continuity retained unresolved request IDs, but protected updates were denied after handback, leaving a reconciliation requirement. Stock02 used one generated read-only evidence utility, not generated motor control. Timing failures and a late transport/host-closure failure limit what the successful task observations establish. Two fixed known fixtures and six valid trials do not establish general reliability or a memory benefit.

Your storage approval was used without a new permission gate. All ten monitors covered their queue intervals with no alerts; the observed additional peak during attempts was 0.431 GB and minimum C: free space was 417.790 GB. The later 0.459 GB snapshot already included the initial report and 7.992 MB original-frame export. Historical evidence and all 624 frozen source identities were preserved.

The campaign and investigation stop here for your review. No infrastructure repair, replacement campaign, expansion, ablation, further comparison or Maps + Attention work has started. The fixed campaign's remaining slots must not be resumed automatically.

---

**Randy (2026-09-29 09:57 PDT):**

Please conclude this chat.
