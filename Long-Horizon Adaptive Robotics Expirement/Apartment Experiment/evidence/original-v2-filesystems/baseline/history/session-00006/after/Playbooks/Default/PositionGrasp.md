# Position an open gripper from perception

Scope: generic grasp positioning for a reachable object; no closure or acquisition decision.

Inspect the RGB-D observation and estimate an appropriate grasp point in the base frame. Pixel-to-point is available in the primitive client, but returns a surface; reason about visible geometry before choosing a center and height. Ensure a collision-free approach and place the base within reach.

Run `python3 Programs/Default/position_grasp.py --x X --y Y --z Z`. This requests an open .15 m aperture and a Cartesian approach at the provided perception-derived coordinates. It stops before closure. Poll status and inspect alignment. You decide closure using live measured width, effort, contact and lifting feedback. It contains no object identities, dimensions, drawer procedure or throw parameters.

Implementation: Programs/Default/position_grasp.py invokes the protected position_grasp control. Evidence and limits: engineering qualification covers aperture remaining open and geometric positioning; noisy depth, occlusion and collisions can still prevent a valid grasp. It does not certify task success.
