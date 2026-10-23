# Protected restart capture integration

The instrumented seed-0 A1 carry recovery to parking2 passed the unchanged physical checks and actual-host timing gate. This is the same measured one-second absence scope as calibration005; it is not a complete task or qualification for other states/worlds.

[Plan006](physical-calibration-plan-006.json) was written before execution. Job `20260923T063944015754Z-3980a35f` ran from06:39:44.464 to06:40:04.450UTC on2026-09-23; its [official receipt](../Evidence/queue-receipts/20260923T063944015754Z-3980a35f.json) reports succeeded/exit0. The [physical result](../Evidence/calibration/physical-calibration-006/held-recovery/result.json), original events, source archive and evidence index are retained. All source hashes stayed unchanged.

Both rich captures—at the cut and after the one-second absence—exported `source-bound-restart-export-1` with `export_state: pass`. Maximum lag was0.03428980000065884s; the largest timing-sample gap was0.037608300000101735s. All15 complete one-second windows stayed within the existing real-time-factor tolerance; the trailing partial window was0.3607943s. This measures actual integrated behavior, not only isolated exporter cost.

The prior [descriptor probe001](../Evidence/calibration/descriptor-probe-001/summary.json) passed model/mutation checks but took roughly0.25–0.27s per export. [Probe002](../Evidence/calibration/descriptor-probe-002/summary.json) replaced Python scalar finite checking with equivalent NumPy array validation and measured all nine exports at0.0237636–0.025152s. Both are compiled-model probes without physics. Their originals and official receipts remain distinct from this physical test.

The root applied the regenerated descriptor/class compatibility patch before006. All408 Runtime tests then passed in43.196s, including actual sandbox checks, in official job `20260923T063840299334Z-dc3095a6` ([receipt](../Evidence/queue-receipts/20260923T063840299334Z-dc3095a6.json)). The preceding failed suite is preserved: one sensor-worker test still expected two task segments after the continuation repair; its assertion was corrected, including a test flag that had shadowed unittest's failure method. No physical threshold was relaxed.

The descriptor pins source/compiler/assets and permitted parameter variation. A compatible descriptor is not a recovery measurement. No qualified state cells or protected calibration loader were supplied during006, and scored readiness remains false. Complete development episodes are the next evidence stage.
