# Recovery record — agent-authored observations, not authority

Run: RCI001-C03-pilot-003-attempt. Invocation: robot-session-1.
Observed authority epoch 3, order version 1: C1 placement entirely on C_pad.

Twenty physical requests were accepted and queried to terminal completion through
the protected robot.py interface. Fresh captures followed the movements. Native
motion receipts retain verification state unknown; receipt completion alone was
not treated as grasp or placement verification.

C1 was initially identified in public RGB-D detections near (0.3805, -0.2397,
0.018) m. Source image 663 was actually inspected. The initial grasp retained a
roughly 0.042 m jaw opening during lift and transport. Public history around
events 3489–3497 subsequently showed near-zero jaw width while hovering above
C_pad, before the descent. Thus the first grasp was lost. Image 3865 showed an
unmarked block at the pad edge, with C1's source location visually clear.

A second short, low lift and shift recentered that block, retaining roughly
0.042 m jaw opening until intentional release. Its identity as C1 is inferred
from the source image, manipulation sequence, and the other parts remaining
visible in their original locations; C1's tag is no longer detected.

Last physical request: c1-e3-final-clear, terminal completed at simulation time
637.674. It returned the arm to the clear-view pose. Final acquisition request:
c1-e3-final-view, terminal completed, observation 6336, capture time 637.878,
image publication event 6524. This image was actually inspected and shows the
unmarked block centered entirely inside C_pad. Status sequence 6338 reports TCP
near (0.2782, 0.2865, 0.4674) m, jaw width 0.080 m, no visible held identity,
idle arm resource, no active command, and idle ready station.

Remaining uncertainty: no fresh tagged C1 detection establishes its identity or
orientation at the destination. The image supports full footprint containment.
Historical terminal motions remain listed under unresolved_commands with unknown
verification; no request is still executing or awaiting a terminal receipt.

Handback request c1-e3-handback was terminal REJECTED at simulation time
720.572, event 7338, with code unsupported_resumption: "Frozen conventional
controller lacks a currently supported next action". Conventional resumption
is not established. Subsequent public status still reports robot ownership,
epoch 3, idle arm, clear-view TCP, open jaws, and no tagged C detection. No
further physical motion was attempted. The invocation ends with this unresolved
condition. Reconcile current public authority and observations before new work.

programs/reconcile_c1.py is only a public query/capture/status helper. It issues
no physical commands and does not retry mutations. This record grants no
authority and its past coordinates are not prescriptions for a future job.
