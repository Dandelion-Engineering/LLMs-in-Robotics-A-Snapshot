"""Unapplied scheduler fragment for operator review; no physical work on import.

Call only between the after-absence observation group and the pre-dispatch
observation/control group. Do not insert it inside a cut/cancel or admission
group. The existing loop remains the sole owner of physics and all limits.
"""
import time


def wait_recovery_boundary_ready(loop, timeout_s):
    """Service ordinary steps to a fixed entry-wall target and fresh sensing.

    No clock reset, monitor clear, threshold, new wait predicate on physical
    success, snapshot reuse or direct cell.tick. loop.until intentionally keeps
    its existing at-least-one-step behavior and original timeout/cap checks.
    """
    entry_wall = time.perf_counter() - loop.start
    entry_sim = loop.elapsed
    loop.monitor.observe(entry_wall, entry_sim)
    target_sim = max(entry_sim, entry_wall)
    loop.until(lambda: loop.elapsed >= target_sim and loop.public_ready(), timeout_s)
    exit_wall = time.perf_counter() - loop.start
    exit_sim = loop.elapsed
    loop.monitor.observe(exit_wall, exit_sim)
    return {'rule': 'ordinary_steps_to_fixed_entry_wall_target_then_public_ready',
            'entry_wall_elapsed_s': entry_wall, 'entry_sim_elapsed_s': entry_sim,
            'target_sim_elapsed_s': target_sim, 'exit_wall_elapsed_s': exit_wall,
            'exit_sim_elapsed_s': exit_sim, 'advanced_sim_s': exit_sim - entry_sim,
            'elapsed_wall_s': exit_wall - entry_wall,
            'residual_lag_s': exit_wall - exit_sim,
            'scope': 'Prospective scheduling only; actual hold/geometry/clock observations stay on every ordinary step.'}
