# Open kitchen drawer B with an open-gripper retract

## Identity

- Name: Open kitchen drawer B.
- Type: learned.
- Version: 0.1.
- Applicable robot / configuration: Apartment Cartesian-arm robot, Maps Edition.
- Created by: Codex.
- Source sessions: 008 and 015.

## Purpose

Provide a perception-directed candidate for opening the known kitchen drawer B. Two episodes produced visible extension with the gripper open; the contact mechanism remains uncertain.

## When to use

When current imagery shows B near closed and the empty robot has a clear frontal approach. Inspect an already open drawer instead of repeating the approach.

## Preconditions

- Kitchen identified, room map loaded, and B distinguished from A by current markings.
- Empty gripper; sufficient work time remains before the battery warning.
- Fresh handle geometry within arm limits and clear space for the drawer to extend.
- Base stationary and approximately normal to the drawer front.

## Inputs

Fresh base-frame surface estimates of the left handle attachment and handle bar, plus observed front and fixture geometry. These are noisy surfaces, not exact grasp centers. Episode coordinates below are evidence only.

## Outputs / success signals

Success means visible extension exposing the cavity, followed by an image confirming retained opening after disengagement. A completed command, open aperture or false bilateral-contact flag does not establish disengagement or successful opening. Cup insertion clearance is a separate check.

## Program or implementation pointer

- Positioning: `Programs/Default/position_grasp.py`, governed by `Playbooks/Default/PositionGrasp.md`.
- Retraction and disengagement: ordinary arm primitives from `RobotDetails.md`.
- No dedicated learned executable. Each geometry-dependent stage requires perception and review.

## Procedure / invocation

1. Locate the left handle attachment and nearby bar from fresh imagery and point projections. Choose a reachable open-gripper positioning target near the attachment; allow for the visible surface rather than treating it as a certified center.
2. Use the default open-gripper positioning capability. Poll completion and inspect the actual fingers, drawer and achieved encoders. Do not close automatically.
3. If imagery supports engagement and the pull corridor is clear, make a bounded arm retract toward the base, approximately along the drawer opening direction. In session 015, a roughly 0.34 m retract with a 0.055 m commanded rise opened B; inspect before further motion.
4. Once visibly extended, raise clear at the achieved short reach, then retract fully before driving. Verify the drawer remains open. Do not assume opening the jaws releases a handle.
5. If extension is absent or contact geometry is uncertain, reassess from sensing. Do not keep pulling blindly or infer an orange-fixture function.

## Safety and authority constraints

Use only current task authority and public controls. Respect arm/base limits, actual clearance and the battery warning. No base motion while still engaged. Stop task work and dock at the warning. Do not infer safe insertion from opening alone.

## Evidence

- `SessionReports/2026-10-08T192917Z-session-008.md`, observations 167–168: open positioning near the left attachment, retract and lowering produced extension. A deliberate orange-fixture approach preceded it; individual effects were not isolated.
- `SessionReports/2026-10-08T204519Z-session-015.md`, observations 313–318: fresh attachment surface approximately (0.755,0.323,0.797) m; default target (0.735,0.323,0.795). B remained near closed in 314. A single arm retract to (0.4,0.323,0.85) over 1.4 s produced the clear opening in 315. No separate lowering or deliberate orange-fixture press occurred. Raised at the same short reach to z=1.15, then retracted; opening remained visible in 316 and side view 318.

## Known limitations and failure modes

- Narrow empirical scope; not a validated general drawer controller or a cup placement procedure.
- No bilateral handle grip was established. Achieved height differed from the positioning target; interaction may constrain the arm.
- Session 015 omits a deliberate fixture press, but incidental fixture contact during positioning and inherited fixture state were not isolated. Do not claim the fixture is irrelevant or unnecessary under all initial states.
- Exact hook geometry, opening distance, forces and insertion clearance remain unresolved. The two episodes used different geometry; do not replay coordinates.

## Status

- Provisional, supported by two opening episodes; single-retract effect more closely isolated in session 015.
- Superseded by: none.
