# Campaign 001: repeated recovery with RCI001-wsl-010d

Status: pre-outcome plan; no scored attempt has started. Admission is separate from this plan and remains closed until its storage, timing and release requirements are supported. Randy authorized this campaign on September 27 at 11:20 PDT. That authorization supersedes the Session 10 review stop, but does not expressly replace the previously adopted storage ceiling.

## Question and scope

How consistently does the exact qualified filesystem-native agent restore useful conventional operation on the two existing recovery fixtures? Test only `RCI001-wsl-010d`, GPT-6 Astra / Max, existing ChatGPT authentication, and the sole bootstrap `Follow the instructions in RobotAgentPrompt.md.`. Keep all 624 frozen sources and runtime instructions byte-identical. Keep the conventional baseline, evaluator, reference machinery, robot, sensing and WSL2/bubblewrap boundary unchanged.

This is a repeated fixed-fixture engineering experiment. The fixtures were used in development; fresh sensor seeds and fresh model invocations do not make their geometry, task or recovery concept held out. Claims concern repeatability under these conditions, not general recovery reliability, physical deployment, superiority over another framework, or a causal benefit from memory. The new experiment does not repeat Batch 01's architecture matrix.

## Fixed allocation and rationale

Predeclare **24 attempts: 12 misplaced-stock and 12 blocked-insert-home**. Each attempt has a new runtime workspace, a fresh model invocation, empty initial continuity, world seed 173, and a unique sensor noise seed in 22001–22024. A seed and family schedule is generated and sealed before admission. Family order alternates within each pair, reversing the first family on alternating pairs. This balances early/late scheduling without adapting to outcomes.

The world seed stays fixed because these are the two exact qualified fixtures, including forced challenge placements. Sensor seeds introduce repeated sensing variation; the model service has no controllable sampling seed. Fresh processes do not prove service-level independence. Report that limitation and time-of-run patterns.

Twelve attempts per fixture give a 93.1% chance of observing at least one failure if its fixed-fixture failure probability is 20%, assuming independent trials. The worst-case 95% Wilson half-width is about 24.6 percentage points per fixture; the equally weighted 24-attempt mixture has about 18.6 points. This precision supports finding recurring failure patterns, not a tight reliability guarantee. Even 12/12 successes would not establish near-perfect reliability.

The reproducible [Batch 01 analysis](design/README.md) records measured durations, exclusions, seed/replicate behavior and hashes of the actual inputs. Batch 01 required 264 planned dispositions, including failures and one administrative interruption. Its 263 measured episode durations total about 34.96 hours; recorded queue occupancy is about 38.01 hours and calendar span about 59.86 hours. Those measures answer different questions and are not interchangeable.

With the existing 1,100-second host cap, 24 episodes allow 7.33 hours of host time, before outer launch/teardown/queue waiting. A conservative scheduling allowance of 1,500 seconds per attempt is 10 hours; it is a planning allowance, not a newly enforced launcher timeout. The single 252-second Session 10 queue pilot would extrapolate to about 1.68 hours, but one successful stock recovery is an optimistic scenario, not a reliable prediction for both families. Report actual elapsed and queue occupancy separately.

## Execution and controls

Use the unchanged Session 10 `orchestrator/physical.py --mode pilot` for every attempt, through the shared compute queue, with its exact 600-second single model invocation and 150-second conventional follow-through window. Host limits are 900 simulation seconds, 1,100 wall seconds and 512 MiB; activation budgets remain 20 actions and 50 explicit observations. Physics advances during inference. No injected restart is added in this first campaign. Observe continuity writes, unresolved actions, programs and handback within each episode; the existing interruption smoke remains prior qualification evidence, not a new campaign result or a memory-effect estimate.

The frozen host requires its historical `development-only` manifest label and the runtime task file says development pilot. Preserve these bytes. The outer campaign protocol declares prospectively scored repeated use of that exact development-qualified fixture. Do not relabel the host's retained evidence or imply unseen challenge evaluation. A future metadata-only map freeze must identify identical implementation bytes and distinguish campaign protocol from framework revision.

Existing baseline/reference fixture checks establish the missing baseline rules and physically demonstrated solutions. They are controls supporting fixture construction, not a concurrent statistical baseline comparison. Every new episode also runs the frozen conventional worker before activation and after accepted handback. New failures are retained even when an earlier reference recovery succeeded. Do not modify the fixture to improve its outcomes.

## Outcomes, validity and stopping

Primary task outcome is the protected independent evaluator's completed order, recipe/inspection provenance, settled placement and absence of violations. Separately report protected handback, subsequent conventional work, task completion, elapsed time, model/tool use, duplicate or unresolved requests, rejected commands, and retained continuity/program evidence. A model's claim or a terminal command receipt cannot establish task success.

Inspect completed attempt outputs only after their official queue receipt is `succeeded` with integer exit status 0. Queue completion authenticates execution, not success. A clean model timeout, refusal, unhelpful recovery or exhausted action budget remains a task failure when infrastructure, protected shutdown and evidence are intact. Missing/corrupt evidence, host failure, actual isolation breach, wrong source/model/bootstrap, or unresolved lifecycle retirement are infrastructure-invalid. Failed queue outputs remain diagnostic evidence with unknown task outcome.

**No replacement attempts and no retries.** The maximum is 24 model invocations. Invalid attempts consume their scheduled slot. Stop immediately for a source/isolation/evaluator breach, evidence-integrity failure, storage/reserve breach or inability to verify namespace retirement. Stop admission after two consecutive ordinary infrastructure-invalid attempts; mark remaining slots not run. Do not stop early for good or bad robot performance. Never tune the framework, prompts, seeds or limits after seeing scored outcomes. Any necessary change ends this campaign for review.

The known natural-host-closure path is a separate lifecycle evidence branch: require a clean host terminal, protected episode-stop record, accepted handback/epoch transfer, observed namespace retirement and durable retained bytes. Preserve absent late operator-retirement and token-denial receipts as absent; do not turn them into passed checks. For a live host, require explicit retirement and stale-token denial. The [assessment implementation](assessment/README.md) and its tests distinguish task outcomes from these gates.

List all 24 planned slots, all starts, every failure and invalidity, and every unrun slot. Report valid-trial Wilson intervals by fixture, with numerator/denominator and invalidity beside them. Also give all-planned operational completion counts and bounds treating unresolved slots as all failures versus all successes. Do not hide infrastructure trouble by reporting only valid successes. The pooled result is an equal-fixture descriptive mixture, not 24 independent challenge families.

## Evidence, storage and admission

Preserve every attempt's manifests, source verification, queue receipt, effective startup/model configuration, full retained model/tool trace, requested/admitted/dispatched/terminal/verified action chain, protected history and evaluator outcome, continuity versions, program admissions, actual workspace exports and retirement records. Portable protected event archives omit endpoint credentials. Native numerical/image bulk retains exact hashes and availability locations. Reuse the frozen sparse-image policy; unavailable imagery is explicitly unavailable, not recreated historical pixels.

Reserve a conservative **1 GiB per attempt** across host, model traces, exported/backing workspace bytes and compact records, plus 2 GB investigation and 1 GB qualification/administration: 28.770 GB permanent allowance. A 25% margin plus 2 GB temporary allowance gives **37.962 GB peak projection**, below the previously adopted 30 GB target / 40 GB admission ceiling. This is a reservation proposal, not measured proof of aggregate enforcement. Measure prior Robot-Codex workloads and qualify external admission/accounting before launch; existing per-component limits do not bound arbitrary aggregate shell output.

The existing 150 GB project-evidence ceiling remains a distinct gate; a large free disk does not waive it. A fresh read-only [admission census](admission/) must count existing evidence and distinguish hardlinked model overcount. No deletion, compaction, movement or reduction of historical scientific evidence is authorized by this plan. If the existing ceiling cannot admit the campaign, obtain a specific one-campaign allowance or a separately authorized normalization plan before launching.

Timing qualification must retain both maximum lag and the frozen one-second RTF criterion, including sample spacing and interpolation limits. The prior pilot's scalar lag alone does not prove all timing gates. Any reconstruction from protected journal timestamps must be labeled as such; it cannot be represented as unrecorded per-tick windows. Record unresolved timing qualification rather than silently changing to a permissive timing track.

Before the first scored attempt: complete admission, seal this protocol and assessment/source/seed manifests, register the exact frozen release and each immutable attempt, verify all current source hashes and required assets, and check the human inbox. The preparation seal is not an admission certificate. A legitimate protocol-only correction before any model outcome receives a new seal and an explicit supersession; earlier artifacts remain.

## Investigation and stopping point

After the campaign, build the human investigation from actual evidence. Provide a sortable full disposition table; a system/ownership diagram; synchronized observations, decisions, command states and continuity writes; and exact trace links. Preselect the first and last scheduled episode of each fixture for representative examination regardless of outcome. Additionally inspect the first valid failure in each fixture and each distinct infrastructure/unexpected behavior category, labeled outcome-selected. Prefer retained data; reconstructed views must be labeled and cannot fill missing original images.

Explain successes and failures through observed chains, with interpretations and unresolved causes separate. Stop for Randy's review after this campaign. No ablation, simpler-agent comparison, expanded challenge family, new architecture or Maps + Attention work follows automatically.
