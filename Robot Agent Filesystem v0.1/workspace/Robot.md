# Robot

**Status:** UNCONFIGURED TEMPLATE. Descriptive documentation is not the enforcement mechanism.

## Body and environment

- Robot/body identifier and configuration revision: `{{ROBOT_ID_AND_REVISION}}`
- Fixed/mobile base, joints, end effector, and payload assumptions: `{{BODY}}`
- Work area, fixtures, devices, and relevant geometry: `{{WORK_AREA}}`
- Reach, contact, grasping, and manipulation limitations: `{{CAPABILITY_LIMITS}}`
- Units and coordinate frames, including an unambiguous orientation convention: `{{UNITS_AND_FRAMES}}`
- Available reference geometry or diagrams within the permitted workspace: `{{REFERENCE_PATHS}}`

## What can be observed

Document the sensor streams, images, depth/pose estimates, joint/gripper feedback, and device state actually exposed through `Tools.md`. For each, give acquisition timestamps, nominal freshness limits, uncertainty, visibility restrictions, and failure/missing-data meanings.

`{{SENSORS_AND_PUBLIC_STATE}}`

Explicitly identify image-derived, instrument-reported, and simulator-oracle information. Unobserved state must not silently appear as known. Record whether the configured agent can actually inspect image content.

## Existing automation

Describe the conventional sequencer, available skills, executing controller, and public feedback. Identify what continues during agent latency, who normally owns each resource, and how progress is recognized.

`{{CONVENTIONAL_STACK}}`

## Protected execution and limits

State the enforced workspace, joint, speed, acceleration/effort, collision/contact, equipment-interlock, and observation-freshness constraints. Identify known coverage gaps, including whole-arm and carried-object checks. Unsupported manual capabilities stay disabled.

`{{ENFORCED_CONSTRAINTS_AND_LIMITATIONS}}`

Document the validated response to lost agent contact, program timeout, takeover, and shutdown, including a held payload or an independently running machine cycle. “Cut power” is not a generic safe fallback.

`{{FALLBACK_AND_STOP_BEHAVIOR}}`

Simulation safeguards are not physical safety certification. This initial binding must not connect to real hardware.
