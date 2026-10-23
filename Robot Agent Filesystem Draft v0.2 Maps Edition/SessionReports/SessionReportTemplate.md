# Session Report Template

Create one new report for each completed or terminated agent invocation. Once written, a session report is immutable. Corrections or supersessions should be recorded in a later report rather than editing historical reports.

Suggested filename: `YYYY-MM-DDTHHMMSSZ-session-<id>.md`

## Session identity

- Session ID:
- Start time:
- End time:
- Agent / model:
- Runtime / configuration:
- Project revision:
- Robot configuration revision:

## Startup context consulted

Record what the session actually inspected at startup.

- `RobotDetails.md`:
- `ProjectDetails.md`:
- `Maps/Apartment.md`:
- Current room map:
- `SummaryOfOnlyNecessaryContext.md`:
- Additional files / reports / artifacts consulted:

## Objective on entry

What task or problem did this session believe it owned?

## Starting state

Record only the starting state relevant to understanding the work, including important uncertainty.

## Work performed

Summarize the meaningful actions, investigations, decisions, and changes made during the session.

Do not reproduce hidden reasoning. Record observable actions, decisions, evidence, and outcomes.

## Results and evidence

For each important result:
- result;
- evidence or observation supporting it;
- confidence / status;
- relevant file, log, image, measurement, or event pointer.

Clearly separate confirmed results from hypotheses or interpretations.

## Robot / world state at exit

Describe the actual known end state relevant to safe continuation.

- Robot state:
- Environment / object state:
- Active or pending actions:
- Authority / control state:
- Safety state:
- Important uncertainty:

## Spatial map use and updates

Record the spatial maps actually used or changed this session.

- Current room(s) identified:
- Room-map files loaded:
- New fixed landmarks / room connections added:
- Corrections to prior map information:
- Perceptual evidence supporting additions or corrections:
- Important map uncertainty:

Do not report movable-object positions here as persistent map facts.

## Durable artifacts created or materially changed

For each artifact:
- path;
- purpose;
- what changed;
- why it may matter later;
- known limitations;
- whether it was actually tested / used successfully.

Do not claim an artifact is useful merely because it exists.

## Learned constraints, procedures, or reusable knowledge

Record information that may plausibly help a future session, including negative results and failure modes. This section records candidates for future reuse; it does **not** by itself promote anything into a future long-term-memory system.

## Failures and negative results

Record failed approaches, rejected actions, invalid assumptions, and other information that would prevent unnecessary repetition.

## Unresolved work

State precisely what remains incomplete, blocked, uncertain, or worth investigating.

## Corrections / supersessions of earlier reports

If this session discovered that earlier historical information was wrong or obsolete, identify the earlier report and explain the correction. Do not edit the earlier report.

## Summary update

Record the meaningful changes made to `SummaryOfOnlyNecessaryContext.md`.

## Session ending

- Task status: complete / incomplete / blocked / invalid / other
- Reason for ending:
- Robot left in safe unambiguous state: yes / no / unknown
- Anything a future session must verify immediately:
