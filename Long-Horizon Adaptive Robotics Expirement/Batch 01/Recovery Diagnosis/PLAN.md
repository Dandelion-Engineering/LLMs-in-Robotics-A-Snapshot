# Retained-state kinematic diagnostic 001

This queue-only diagnostic investigates physical-calibration-002's two held-recovery planning failures. It reconstructs the exact public robot telemetry at each post-absence snapshot and uses the archived Cell.ik implementation and retained XML. It does not advance physics or change any Runtime source.

The fixed methods are original endpoint IK, straight Cartesian continuation with maximum 20 mm steps, continuation with maximum 10 mm steps, and 20 mm continuation through the declared inspection-pad position. All use the same vertical orientation, 120-iteration solver, joint bounds and convergence tolerances. Each method attempts lift, travel and release in order, stops at its first failure, and retains its q waypoints and failed residual. Eleven evenly spaced joint-interpolation FK samples per successful segment expose intermediate TCP and orientation excursions. Seven predetermined seeds separately test each pad's raised and release endpoints; a successful alternate seed is not a valid route.

The same job evaluates the separately retained 19 insert-pickup snapshots using insert_fk_replay.py. Those protected FK/contact reconstructions are offline diagnostics, never service-planner or candidate inputs.

Every boolean/scalar in output is converted to a JSON-native type. The driver verifies the installed queue's ownership and exact entrypoint before importing MuJoCo or doing kinematics. A zero exit means the diagnostic completed, even if every route failed. Root must retain the official queue receipt. No returned convergence, FK geometry, or contact reconstruction establishes a collision-free trajectory, preservation of a grasp, restart admissibility, or physical recovery. Any common planner change requires a fresh queued physical carry probe with unchanged physical/evaluator criteria.

Output should be a fresh directory named Evidence/calibration/recovery-kinematics-001. No implicit retries or adaptive variant expansion are part of this screen.
