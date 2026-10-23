# HTML Interactive Reports Playbook

## 1. Purpose

HTML Interactive Reports are the preferred format for research outputs that would otherwise require substantial reading, explanation, comparison, or conceptual understanding.

The goal is **not to turn a written report into a website**.

The goal is to create an **interactive research environment that helps the Project Lead build the correct mental model, explore the evidence, understand important details, and move between high-level ideas and technical depth without being forced through a long linear document.**

The report should combine:

* concise explanatory writing;
* visual representations;
* meaningful interactive interfaces;
* links to original research papers;
* evidence and provenance;
* technical depth when required;
* explicit connections between details and larger systems;
* clear separation between evidence, interpretation, hypothesis, and illustration.

The reader should be able to understand the central ideas without reading every section.

---

# 2. Primary Design Objective

Optimize for:

> **Understanding, exploration, and scientific reasoning—not information consumption.**

Do not attempt to make the Project Lead read everything the research agents discovered.

Instead:

1. Determine the mental model the reader needs.
2. Build that mental model first.
3. Organize supporting information underneath it.
4. Allow the reader to descend into detail when useful.
5. Maintain access to the underlying evidence at every important point.

A successful report should feel less like reading a report and more like **exploring a scientific problem with an interactive research partner.**

---

# 3. Reader Learning Profile

These reports are optimized for a reader who tends to learn best through **systems, mechanisms, relationships, and large general ideas**.

The reader usually understands technical material better when they can first answer questions such as:

* What larger problem are we solving?
* What system is this part of?
* What are the major components?
* What is interacting with what?
* What changes what?
* Why does this particular detail matter?
* Where does this detail sit inside the larger picture?

The reader frequently learns by **zooming in and out**:

**Big idea → system → component → physical or mathematical mechanism → detail → back to system**

Design reports around this movement.

Do not assume that the ideal learning sequence is:

**simple explanation → increasingly technical explanation → most technical explanation**

The reader may instead move repeatedly between levels.

Support that behavior.

---

# 4. The System-First Rule

Whenever possible, begin with the **world before the pieces**.

Before introducing substantial technical detail, establish:

1. the central research question;
2. the larger system being studied;
3. the major pieces of that system;
4. how those pieces relate to one another;
5. where the current question lives inside that system.

For example, do not begin a section with:

> The analytic signal is constructed using the Hilbert transform...

Begin with the conceptual problem:

> We want to know where an oscillation is in its cycle at a particular moment.

Then establish the relevant system:

> EEG waveform → phase-estimation method → instantaneous phase → comparison with neural events

Only then descend into the Hilbert transform.

Technical mechanisms should appear because **the larger problem requires them**, not merely because they belong in a methods section.

---

# 5. The Detail Connection Rule

Never present important technical detail in conceptual isolation.

When detail is necessary, determine where it belongs using this hierarchy.

### Level 1 — Project Connection

First ask:

> How does this detail connect directly to the research question, analysis, experiment, or system we are working on?

Use this connection whenever possible.

### Level 2 — Larger Scientific or Engineering System

If there is no useful direct project connection, ask:

> What larger scientific, mathematical, computational, biological, or engineering problem is this detail part of?

Connect the detail to that system.

### Level 3 — Useful General Idea

If the larger scientific system is still unlikely to provide an intuitive anchor, connect the detail to a broader idea likely to be interesting to the reader.

Good examples include:

* feedback systems;
* control;
* state estimation;
* signal versus noise;
* information compression;
* prediction;
* synchronization;
* competition between processes;
* uncertainty;
* filtering;
* distributed systems;
* cause and effect;
* representations;
* constraints;
* optimization;
* measurement.

Only use such connections when they are genuinely informative.

### Level 4 — Explicit Implementation Detail

Do **not** force an analogy or grand conceptual connection when none exists.

Instead say clearly:

> This is mainly an implementation detail. You do not need it for the conceptual model. It matters because ______.

This is preferable to an inaccurate or strained analogy.

---

# 6. Progressive Depth

Reports should support several levels of depth simultaneously.

The default structure is:

**Big idea**

↓

**System view**

↓

**Major mechanisms or competing explanations**

↓

**Methods / measurements**

↓

**Technical implementation**

↓

**Evidence and source material**

The report should begin near the top of this hierarchy.

Do not force the reader to descend farther than necessary.

Use controls such as:

* Explore this
* Why does this matter?
* How does this work?
* Go deeper
* Show the mechanism
* Show the math
* Show assumptions
* Show evidence
* Open paper

Technical depth should be **pull-based whenever possible**.

Do not make the deepest level the default reading experience.

---

# 7. Default Report Architecture

The exact interface should vary with the scientific problem. Do not mechanically reuse the same layout.

However, most reports should contain the following conceptual layers.

## A. The Question

Immediately establish:

* What are we trying to understand?
* Why are we investigating it?
* What decision, hypothesis, or research direction does it affect?

This should normally be visible without scrolling far.

Avoid generic introductions.

---

## B. The Big Idea

Explain the most important conceptual insight in a small amount of text.

Ask:

> If the reader remembers only one idea from this report, what should it be?

Represent that idea visually whenever doing so improves understanding.

---

## C. System View

Show how the important pieces relate.

Possible forms include:

* system diagrams;
* causal diagrams;
* signal pipelines;
* timelines;
* hierarchies;
* anatomical diagrams;
* experimental workflows;
* state-transition diagrams;
* data transformations;
* input → process → output diagrams.

This section should provide a mental map that later details can attach to.

---

## D. Interactive Exploration

Identify concepts where changing something and seeing the consequence would improve understanding.

Examples:

* move an event through different phases of an oscillation;
* alter a detection threshold;
* change noise level;
* compare two signals;
* toggle competing models;
* change a parameter and observe the analysis result;
* step through an algorithm;
* highlight parts of an anatomical or computational system;
* turn experimental assumptions on and off;
* compare several candidate methods.

The interface should answer a scientific question.

Do not add interaction merely because HTML allows it.

---

## E. Competing Explanations, Methods, or Routes

When there are legitimate alternatives, make comparison easy.

Allow the reader to explore:

* what each option asks;
* what each option measures;
* what assumptions it makes;
* what it can reveal;
* what it cannot reveal;
* where the literature supports it;
* what uncertainties remain.

Avoid prematurely collapsing meaningful alternatives into one answer.

---

## F. Evidence Layer

Every major scientific claim should have a path back to evidence.

The reader should be able to move from:

**Claim → evidence → paper**

without hunting through the document.

When useful, show:

* paper title;
* authors/year;
* direct link;
* what the paper contributes;
* relevant experiment or figure;
* relevant population/species/dataset;
* limitations;
* disagreement with other papers.

Do not create a citation graveyard that is disconnected from the claims it supports.

---

## G. Deep-Dive Layer

Put material here that is necessary for rigor but not necessary for first-pass understanding.

Examples:

* statistical derivations;
* equations;
* algorithm details;
* preprocessing parameters;
* implementation details;
* assumptions;
* edge cases;
* robustness checks;
* methodological caveats.

Always reconnect this layer to the larger system.

---

## H. What This Means for the Project

Return to the project-level view.

Explain:

* what became clearer;
* what remains uncertain;
* which possibilities remain open;
* what this information changes;
* what decisions may need to be made.

Do not manufacture a recommendation when the evidence does not justify one.

---

# 8. Interactivity Must Teach

Every meaningful interactive element must pass this test:

> **What can the reader understand by interacting with this that would be harder to understand from text alone?**

If there is no good answer, remove the interaction.

Useful interaction often exposes:

### Cause and effect

Change X and observe Y.

### Structure

Select a component and see where it fits.

### Comparison

Switch between competing explanations or methods.

### Time

Move through an event or process.

### Scale

Zoom from system → component → mechanism.

### Sensitivity

Change a parameter and observe how conclusions change.

### Uncertainty

See what happens across plausible values or assumptions.

### Evidence

Select a claim and inspect its supporting literature.

Avoid decorative interactivity.

---

# 9. Use Multiple Modes of Learning

Do not make the report depend primarily on reading.

Mix modalities when the material permits it:

* explanatory text;
* figures;
* diagrams;
* interactive simulations;
* annotated plots;
* timelines;
* comparison interfaces;
* expandable technical explanations;
* paper links;
* evidence panels;
* short questions that direct attention;
* visual transformations;
* before/after views.

The reader should regularly encounter a change in mode.

Avoid creating twenty consecutive screenfuls of prose even if the prose is well written.

---

# 10. Writing Style

Write like a scientist or engineer explaining something interesting to a collaborator.

Do not write like an AI generating a formal report.

Avoid:

* repetitive summaries;
* generic introductions;
* unnecessary conclusions;
* excessive section previews;
* phrases that merely announce what the next section will do;
* inflated academic language;
* long passages saying little;
* formulaic "key takeaway" boxes everywhere;
* repeatedly restating the same concept.

Prefer:

* concrete language;
* direct explanations;
* mechanisms;
* explicit causal relationships;
* short conceptual chunks;
* examples;
* questions the reader is naturally likely to ask.

Paragraphs should generally be short.

Dense sections should be broken by meaningful visual or interactive elements rather than arbitrary decorative cards.

---

# 11. Explain Mechanisms Whenever Possible

Prefer:

> **What actually happens?**

over merely naming a concept.

For biological systems, explain relevant physical mechanisms when useful.

For mathematical methods, explain what information is being transformed and why.

For algorithms, explain the input, transformation, and output.

For statistics, explain what uncertainty or relationship the method is trying to capture.

For engineering systems, explain what signals, forces, states, constraints, or information are moving through the system.

Names and definitions are secondary to understanding how something works.

---

# 12. Evidence and Provenance Rules

Interactive reports can make weak claims look convincing.

Therefore provenance must be unusually explicit.

Whenever relevant, distinguish between:

### Direct evidence

Something directly observed or reported in a source.

### Derived result

Something computed from reported values or project data.

### Literature synthesis

A conclusion formed by combining multiple sources.

### Agent interpretation

An interpretation made by the research agents.

### Hypothesis

A proposed explanation that has not been established.

### Schematic

A simplified illustration designed to teach a concept.

### Simulated example

Artificial values or signals created to demonstrate behavior.

Never visually present simulated or schematic information in a way that could reasonably be mistaken for experimental data.

Label it.

---

# 13. Figures and Visualizations

Figures should exist because they improve the mental model.

Prefer figures showing:

* relationships;
* mechanisms;
* transformations;
* comparisons;
* sequence;
* causal structure;
* uncertainty;
* changes over time.

Whenever a figure is based on a research paper, make the source accessible.

Whenever a figure is reconstructed, transformed, simplified, or simulated, say so.

Do not fabricate realistic-looking scientific data merely to make a report visually impressive.

If artificial data helps teach the concept, label it clearly as **illustrative**, **schematic**, or **simulated**.

---

# 14. Original Papers Are Part of the Interface

The interactive report is not intended to replace reading research papers.

It should help the reader determine **which papers and which parts of papers are worth reading.**

Provide links at moments of curiosity.

Good pattern:

> **Interesting? Read the original evidence →**

The reader may move from the interactive report into a paper, inspect a figure or method, and return.

Design for this behavior.

When useful, explain why a particular paper is worth opening:

* foundational method;
* strongest direct evidence;
* important conflicting result;
* best conceptual explanation;
* closest experimental conditions to the project.

---

# 15. Design for Exploration Rather Than Linear Reading

The report should remain understandable if the reader does not consume it from top to bottom.

Allow several paths.

For example:

**System overview → interesting mechanism → evidence**

or:

**Main question → candidate method → technical details**

or:

**Figure → paper → return to comparison**

or:

**Big idea → deeper mechanism → back to system**

Use navigation that makes the reader's current conceptual location clear.

Do not require completion of earlier sections before later sections can be understood unless the dependency is genuinely necessary.

---

# 16. Reading-Fatigue Protection

Assume long stretches of passive reading will eventually reduce engagement.

Therefore:

* keep initial explanations concise;
* expose depth progressively;
* alternate modalities;
* turn suitable concepts into exploration;
* hide optional technical material behind intentional actions;
* preserve easy access to the system overview;
* avoid enormous uninterrupted sections;
* avoid unnecessarily repeating information;
* allow the reader to jump around safely.

Do not solve reading fatigue merely by placing prose into many colorful cards.

The information experience itself must change.

---

# 17. Equations and Technical Mathematics

Do not avoid mathematics when the mathematics matters.

But establish three things before presenting an equation:

1. **What problem are we solving?**
2. **What does the equation represent conceptually?**
3. **Where does it sit inside the larger system?**

Then explain important terms.

Where useful, make equations interactive by allowing the reader to change values and observe consequences.

Do not turn the report into a textbook derivation unless the derivation itself is important to the research question.

---

# 18. Analogies

Analogies may be used to establish intuition.

They must never silently replace the real mechanism.

A good pattern is:

> **Intuition:** analogy
> **Actual system:** what really happens
> **Where the analogy breaks:** important limitation

Avoid strained analogies.

The goal is conceptual scaffolding, not cleverness.

---

# 19. Uncertainty and Disagreement

Do not clean up scientific uncertainty merely to produce a simpler interface.

If literature disagrees, represent the disagreement.

If evidence is weak, show that it is weak.

If several interpretations are plausible, preserve them.

Useful interactive approaches include:

* switching between competing interpretations;
* evidence maps;
* confidence or evidence-strength indicators with clearly defined meaning;
* paper-by-paper comparison;
* timelines showing how the literature changed;
* toggles showing results under different assumptions.

Do not convert ambiguity into false certainty.

---

# 20. Report-Specific Design

Do not use one universal dashboard template.

Determine the structure from the science.

A report about an oscillation may center on an animated waveform.

A report about neural circuitry may center on a system diagram.

A literature landscape may center on a research map.

A methodological decision may center on competing pipelines.

A statistics report may center on simulated data and parameter manipulation.

A robotics report may center on sensing → state estimation → planning → control.

Reuse principles, components, and code where helpful.

Do not reuse the same experience mechanically.

---

# 21. Examples of Detail Anchoring

## Example: EEG phase estimation

Poor:

> The analytic signal is constructed from the original signal and its Hilbert transform.

Better:

> **System problem:** We need to know where the EEG oscillation is in its cycle when the LC spike occurs.

> **Measurement problem:** The voltage trace gives us amplitude over time, but we want an estimate of instantaneous phase.

> **Mechanism:** The Hilbert-transform approach creates a representation from which that phase angle can be estimated.

Then allow the reader to explore the waveform and phase relationship.

---

## Example: Confidence interval

Poor:

> A 95% confidence interval is calculated from the sampling distribution...

Better:

> **Larger problem:** We measured an effect from one finite dataset. How much could that estimate move if we repeated the experiment with similar data?

Then show repeated simulated samples or a distribution before introducing the formal statistical machinery.

---

## Example: Computer vision architecture

Poor:

> The model uses token pruning at layers 8, 12, and 16.

Better:

> **System problem:** Visual processing produces more information than the downstream system needs.

> **General idea:** The architecture is deciding what information remains worth carrying forward as computation progresses.

Then show where pruning occurs and allow the reader to inspect what is retained or discarded.

---

# 22. Agent Workflow

When assigned an HTML Interactive Report, do not immediately begin coding.

## Stage 1 — Understand the Research

Determine:

* the project question;
* why the report exists;
* what decisions it may support;
* what evidence is available;
* what remains uncertain.

---

## Stage 2 — Identify the Big Idea

Write down privately:

> What is the largest useful mental model that organizes this report?

If no project-specific system exists, identify the larger scientific or engineering system.

---

## Stage 3 — Build the Conceptual Map

Map:

**project question → system → components → mechanisms → measurements → technical details → evidence**

Identify which connections matter most.

---

## Stage 4 — Identify Friction Points

Determine which concepts are likely to become difficult, boring, abstract, or excessively detailed.

For each one, ask:

> Can this be converted into a visual, mechanism, comparison, or interaction?

---

## Stage 5 — Design the Learning Experience

For every proposed visual or interaction, specify:

* what concept it teaches;
* what the reader does;
* what changes;
* what the reader should notice;
* how it connects to the larger system.

Delete interactions without a clear learning purpose.

---

## Stage 6 — Map Claims to Evidence

Before finalizing the report, ensure major claims have identifiable sources.

Distinguish:

* evidence;
* synthesis;
* interpretation;
* hypothesis;
* schematic illustration.

---

## Stage 7 — Build

Prefer a self-contained HTML/CSS/JavaScript report when practical.

The report should work by opening it normally in a modern browser.

Keep dependencies minimal.

If external libraries are genuinely helpful, use stable, pinned versions and document them.

---

## Stage 8 — Scientific Verification

Perform a separate verification pass.

Check:

* scientific claims;
* paper attribution;
* species/population/context;
* numerical values;
* visual representations;
* methodological descriptions;
* whether schematics could be mistaken for data;
* whether interpretations are presented as facts.

---

## Stage 9 — Interaction QA

Test every control.

Check:

* buttons;
* sliders;
* toggles;
* tabs;
* expandable sections;
* paper links;
* plots;
* animations;
* responsive behavior;
* default states;
* edge cases.

No visible control should be decorative or broken.

---

## Stage 10 — Learning QA

Finally ask:

> If the reader spends only ten minutes exploring this report, will they leave with the correct large-scale mental model?

Then ask:

> If the reader becomes interested and spends an hour exploring, can they reach the technical details and original evidence necessary for serious scientific reasoning?

A good report should support both.

---

# 23. Minimum Quality Requirements

Every completed HTML Interactive Report should allow the reader to answer:

1. **What is the big question?**
2. **What larger system or idea does this belong to?**
3. **What are the important components, mechanisms, or alternatives?**
4. **Why do the technical details matter?**
5. **What evidence supports the important claims?**
6. **What remains uncertain?**
7. **What does this mean for the current project?**

If the report cannot answer these questions, it is not complete.

---

# 24. Anti-Patterns

Do not produce:

### A webpage-shaped PDF

Large amounts of linear prose divided into cards.

### Dashboarditis

Many charts, gauges, panels, and controls without a coherent scientific story.

### Decorative interaction

Buttons and animations that do not improve understanding.

### Detail dumping

Technical information presented merely because it exists.

### Forced analogy

A weak analogy invented because the playbook requests conceptual connections.

### False visual authority

Beautiful simulated graphics presented like experimental evidence.

### Hidden provenance

Claims whose supporting evidence cannot easily be found.

### Premature certainty

One clean narrative created from genuinely conflicting literature.

### Mandatory depth

Forcing the reader through implementation details before allowing them to understand the larger system.

### Endless summarization

Repeatedly telling the reader what they have already learned.

---

# 25. Final Principle

When deciding what to build, remember:

> **Give the reader the world before giving them the pieces.**

When giving them the pieces:

> **Show where each piece belongs.**

When the pieces become technical:

> **Explain why descending to that level is necessary.**

When the reader wants evidence:

> **Make the path from idea to evidence short.**

And when there is more information than the reader needs:

> **Make it explorable rather than mandatory.**

The purpose of an HTML Interactive Report is not to prove that the agents did a large amount of research.

It is to turn that research into an environment where the human collaborator can **understand, question, explore, and make better scientific decisions.**
