from attempts import *
complete('matrix001','All 16 cases executed. Full and reduced models reproduce energy gain. Plane support eliminates it; smaller timestep, tighter dynamics solver and warmstart removal do not. condim6_no_rolling and frictionless are ineffective controls because default floor parameters win the contact max rule; retained explicitly and corrected prospectively. Legacy CCD leaves finite support and is not a stable replacement.',outcome='partial')
cases=[dict(id='ccd1e8',option={'ccd_tolerance':'1e-8'}),dict(id='ccd1e10',option={'ccd_tolerance':'1e-10'}),
 dict(id='ccd1e12',option={'ccd_tolerance':'1e-12'}),dict(id='ccd200',option={'ccd_iterations':'200'}),
 dict(id='singlecontact',multiccd=False),dict(id='actual_frictionless',cup={'condim':1},floor={'condim':1}),
 dict(id='actual_no_rolling',cup={'condim':6,'friction':'1 .02 0'},floor={'friction':'1 .02 0'}),
 dict(id='plane_roll',plane=True,cup={'condim':6}),dict(id='tight_roll',option={'ccd_tolerance':'1e-10'},cup={'condim':6}),
 dict(id='plane_roll_zero',plane=True,cup={'condim':6},zero_velocity=True),
 dict(id='tight_roll_zero',option={'ccd_tolerance':'1e-10'},cup={'condim':6},zero_velocity=True)]
register('matrix002','physics_matrix.py','Follow-up causal controls: isolate convex-collision precision and multi-contact geometry; correct two ineffective contact-parameter interventions from matrix001; test principled support/rolling combinations.',cases,[(ROOT/'matrix001/initial.npz','initial.npz')])
build()
