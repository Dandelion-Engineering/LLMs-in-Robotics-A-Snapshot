# Recovery outcome: activation-001

Run episode-feba3fead8f14219; invocation pilot-412a819bc501; fixed order revision 1.

The supervisor accepted handback request pilot-412a819bc501-handback-v2, request event 3040, terminal completed at simulation time 302.358 s. Response: ok true, owner conventional, authority_epoch 4; verification state public_resumption_conditions, next_operation transport. This is an acknowledged transfer of ownership, not proof that the remaining order is complete.

Recovery used two physical actions:
- pilot-412a819bc501-clear-home-a-v1 relocated A1 from insert_home_A to parking1. Terminal event 1140; post-motion public-effect verification event 1143 / observation sequence 1121.
- pilot-412a819bc501-setup-b-v1 returned insert_A home and installed insert_B. Terminal 266.066 s; public-effect support sequence 2635. Fresh structured status sequence 2679, capture 270.478 s, confirmed both insert locations, A1 parking1, idle station/arm and .080 m open jaws without a visibly held object.

First handback pilot-412a819bc501-handback-v1 was rejected unsupported_resumption after A1 relocation; setup B resolved the remaining prerequisite before the successful second handback.

Continuity was atomically committed before the accepted handback (sha256 9e303fbf3bd4f76d943410fa2ec072b09d763bf4b76bcd5d58216211dec2eb33). The subsequent read-only status request was denied with invocation_capability_denied, so no further robot requests or continuity commit were attempted. This local outcome note supplements the last protected continuity note; the public handback receipt is authoritative.

Remaining uncertainty/work: B2 loading, recipe B processing, linked passing inspection and delivery of the one ordered B part to tray2 have not been verified by this agent. These remain with the conventional controller. No additional operator help requested. No PNG content inspected. No current actuation authority retained; end activation.
