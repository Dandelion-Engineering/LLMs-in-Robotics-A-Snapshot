from attempts import *
cases=[{'id':name,'seconds':seconds,'sample_interval':interval} for name,seconds,interval in [
    ('zero',0.0,.04),('one_step',.004,.04),('aligned_endpoint',.04,.04),
    ('forced_endpoint',.104,.04),('non_grid_interval',.104,.013),
    ('non_grid_duration',.103,.013),('interval_below_timestep',.04,.003),
    ('longer_than_duration',.104,1.0),('short_exact',2.0,.04),('short_non_grid',2.0,.037)]]
files=[(HERE/'physics_matrix.py','physics_matrix.py'),(HERE/'endpoint_schedule.py','endpoint_schedule.py'),
       (APP/'scene.py','scene.py'),(PRIOR/'matrix001/initial.npz','initial.npz'),
       (APP/'operations/session-36/physics_matrix.py','legacy_matrix.py')]
register('recorder001','test_recorder.py','Frozen recorder verification: ten real-physics endpoint/sampling cases, independent exact-rational two-hour sampling schedules at 0.04/0.037/0.003-second intervals, and bit-exact short-run comparison against the preserved old diagnostic. No gate relaxation, synthetic terminal times or old-evidence edits.',cases,files)
build()
