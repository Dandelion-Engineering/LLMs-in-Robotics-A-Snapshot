"""Build an UNAPPLIED run_screen instrumentation patch; never write its target."""
from __future__ import annotations

import difflib
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / 'Recovery Qualification' / 'run_screen.py'
BASE_SHA256 = '644ea18c35950a996eba4b031d8dfaddc8163cfa9aee280c2cfea273afa23604'

HELPER = '''def boundary_operation(loop, details, label, operation, *args, **kwargs):
    """Observe an existing boundary call in place; no new timing pass gate."""
    stage = details.get('stage')
    start_wall = time.perf_counter() - loop.start
    start_sim = float(loop.cells[0].data.time)
    success = False
    try:
        value = operation(*args, **kwargs)
        success = True
        return value
    finally:
        end_wall = time.perf_counter() - loop.start
        end_sim = float(loop.cells[0].data.time)
        details['boundary_operation_timings'].append({
            'stage': stage, 'label': label, 'wall_start_s': start_wall, 'wall_end_s': end_wall,
            'wall_cost_s': end_wall - start_wall, 'sim_start_s': start_sim, 'sim_end_s': end_sim,
            'success': success})


'''

REPLACEMENTS = [
    ('def trial_body(loop, trial, plan, details):\n', HELPER + 'def trial_body(loop, trial, plan, details):\n'),
    ("            protected = capture_restart_state(cell, zones=loop.zones, zone_half=loop.zone_half,\n",
     "            protected = boundary_operation(loop, details, 'capture_restart_state:cut_candidate',\n"
     "                capture_restart_state, cell, zones=loop.zones, zone_half=loop.zone_half,\n"),
    ("        value = capture_restart_state(cell, zones=loop.zones, zone_half=loop.zone_half,\n",
     "        value = boundary_operation(loop, details, 'capture_restart_state:' + kind,\n"
     "            capture_restart_state, cell, zones=loop.zones, zone_half=loop.zone_half,\n"),
    ("                   cut_restart_admissibility=classify_restart(protected))\n",
     "                   cut_restart_admissibility=boundary_operation(\n"
     "                       loop, details, 'classify_restart:cut', classify_restart, protected))\n"),
    ("               'qualification_granted': False, 'trial': trial}\n",
     "               'qualification_granted': False, 'trial': trial, 'boundary_operation_timings': []}\n"),
]

FORCED_LABELS = ('before_transport', 'before_cancel', 'after_cancel', 'after_absence',
                 'before_recovery_dispatch', 'after_recovery_admission', 'after_settled_placement')


def candidate_source(source):
    """Only the declared exact source can produce this prospective patch."""
    if hashlib.sha256(source.encode('utf-8')).hexdigest() != BASE_SHA256:
        raise ValueError('run_screen base identity changed; do not apply a stale patch')
    result = source
    for old, new in REPLACEMENTS:
        if result.count(old) != 1:
            raise ValueError('Boundary timing patch anchor is not unique: ' + old)
        result = result.replace(old, new, 1)
    old = '    loop.geometry_trace.sample(force=True)\n'
    if result.count(old) != len(FORCED_LABELS):
        raise ValueError('Forced geometry call count changed')
    for label in FORCED_LABELS:
        new = ("    boundary_operation(loop, details, 'GeometryTrace.sample:" + label + "',\n"
               "                       loop.geometry_trace.sample, force=True)\n")
        result = result.replace(old, new, 1)
    return result


def patch_bytes():
    raw = TARGET.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('run_screen base bytes changed')
    source = raw.decode('utf-8')
    relative = 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Recovery Qualification/run_screen.py'
    return ''.join(difflib.unified_diff(source.splitlines(True), candidate_source(source).splitlines(True),
                                      fromfile=relative, tofile=relative)).encode('utf-8')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--write-patch']:
        raise SystemExit('Only --write-patch is supported; target application is not implemented')
    output = HERE / 'pending-boundary-timing.patch'
    with output.open('xb') as stream:
        stream.write(patch_bytes())
    print(str(output))
