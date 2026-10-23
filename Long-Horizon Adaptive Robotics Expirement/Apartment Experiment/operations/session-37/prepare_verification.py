from attempts import *
assert complete('recorder001','Ten actual-physics recording cases, three independently derived two-hour schedules and a bit-exact legacy-physics comparison passed. This verifies recording only and is not commissioning.'),'Recorder gate failed; stop under Randy authority'
cases=read(PRIOR/'verification001/manifest.json')['cases']
cases.append(dict(id='recorded_long_non_grid_sampling',seconds=7200,sample_interval=.037))
files=[(p,p.name) for p in APP.glob('*.py')]
files += [(HERE/'physics_matrix.py','physics_matrix.py'),(HERE/'endpoint_schedule.py','endpoint_schedule.py'),(PRIOR/'matrix001/initial.npz','initial.npz')]
register('verification001','verify_candidate.py','Repeat the original 26 physics cases and three integrated regression groups with actual terminal recording; add one bounded 7200-second non-grid-sampling case. All original gates are unchanged; endpoint and actual-step accounting are additionally required. Failure stops the session without retry or launch.',cases,files,rerun='APARTMENT-cup-verification001')
build()
