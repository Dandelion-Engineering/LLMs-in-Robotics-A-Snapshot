# Session-006 navigation and constrained arm evidence

Source: public commands/status, head RGB-D observations 133–144 and 172–176, all cited images rendered with robot_image. Coordinates are approximate dead reckoning, not surveyed truth. This is curated evidence rather than a complete raw log.

## Departure obstruction and recovery

Started at kitchen charger (4.114,-.941), yaw 10.1334, empty gripper and arm (.22,0,.70). Observation 133 showed the nearby backstop. Rear observation 134 showed clear floor and extended drawers. Backed .65 m to (4.608,-.518), turned -2.28 to north, and observed the drawer fronts (135). Advancing .78 m to y=.261 completed, but a +1.5708 turn toward west was blocked near (4.713,.318), yaw 9.3257. Request f76a24712e774d15b08da3e9b4ab200f reported blocked at sim 3692.868. Gripper effort rose and arm encoders departed from their requested values. Observation 136 showed the near drawer front/handle immediately beside the arm.

An attempted disengagement toward arm (.20,.15,.55), pitch 0, completed at sim 3707.736 but remained constrained: lift encoder .27285, lateral .08266, reach .11928. The base shifted to (4.725,.383). A following .65 m forward request c2867cbf2ffc46b2897dd133c7808413 was blocked at sim 3711.048, only moving near (4.709,.454). This was not a successful westward clearance path. Exact contact bodies were not identified; appearance and prior layout put the obstruction by the near drawer A, but no isolated drawer operation was intended or established.

Next requested arm (.20,.30,1.25), pitch 0 over 2 s. Request 1aa9c294580a409d8be85f6bf6b39467 completed at sim 3719.628. Status at 3720.000 still had lift encoder **.13564**, lateral .30002, reach .11986: the commanded high pose was not achieved. Observation 137 showed the arm low beside the drawer. Base was approximately (4.681,.449), yaw 9.3274.

A +1.5708 base turn toward south completed at sim 3733.212 (request 87423cb13b8647a082415fc865d11647), reaching about (4.761,.448), yaw 10.8760. With **no intervening arm command**, lift encoder was now **.81948**, consistent with the earlier requested z=1.25. This directly demonstrates delayed arm motion after clearance changed in this episode; persistent target tracking is a plausible interpretation, not a claim based on controller internals. Any recovery movement must allow for the entire outstanding arm target as well as current measured pose.

Recentered arm at (.22,0,1.20), verified actual lift encoder about .770, advanced .43 m south to y=.025, turned -1.4512 toward west, and observed open aisle (139). High retracted travel then succeeded: 1.30 m west to (3.410,.024); turn -.10; 1.40 m to (2.019,.163); another 1.40 m to (.623,.302), with intermediate images 140–142. Lidar showed very close side geometry while passing the bin; this path should not be considered a generous-clearance reusable route. No further base segment was blocked.

Turned +.552 toward the origin, inspected image 143, drove .69 m to (.004,.001), then turned +1.1188 to the pedestal-facing heading 10.9958. Observation 144 and fresh depth projection established pickup geometry. No throwing attempt preceded arrival and confirmed scene clearance.

The previous B/cup completion was not reevaluated by the throwing assignment's task_success signal. No cup or B manipulation was intended. Both drawers were visibly extended at departure; precise drawer displacements after incidental contact were not measured.

## Living-room charging approach

At base (.002,.003), yaw 12.2456, empty arm already stowed (.22,0,.70), observation 172 reidentified green pad, yellow stripe and backstop. Stripe pixel (231,176) projected to base-relative (-1.5781,-1.5727,.0106), consistent with the known living-room pad.

First recorded warning was sim 4195.640. Turned -2.3562 to yaw 9.8894, centered head pan with tilt .55, then drove 1.20, .70 and .20 m in separate segments with images/lidar between them. Final pose was approximately (-1.875,-.938), yaw 9.8893, equivalent -2.6771. After .5 s settling and observation 176, docking succeeded on the first attempt at sim 4233.624. [Raw final status](session-006-final-status.json) confirms no active action and empty gripper. No physical command followed docking.
