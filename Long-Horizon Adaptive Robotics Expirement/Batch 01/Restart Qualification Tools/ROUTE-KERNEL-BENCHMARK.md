# Bounded actual-cover kernel benchmark

[benchmark_route_kernel.py](benchmark_route_kernel.py) is queue-only and read-only for inputs. It compares the original blocker expression and the unapplied validated-once replacement against completed parking1 construction evidence. It does not import/compile/call `_route`, `_calibration`, or `classify_restart`, and supplies no calibration stub or accepted qualification bundle. Runtime is unchanged.

The fixed diagnostic inputs are A1 and B10 separately, their 50 mm compact covers, and **10 mm uniform padding as an explicit diagnostic assumption**. This benchmark does not select an empirical-transfer rule. It uses every actual available same-group cut scene named by the completed compact report, rebinds each scene through `CompletedExtraction`, and retains every original trial ID/status. Other groups are not pooled. Report/cover/cut identities and successful official screen, extraction and compact receipts are required; an incomplete group is rejected rather than silently shortened.

For each scene, run one untimed pair with `valid_box` counters, then exactly five timed pairs in alternating order (original first for pairs 1/3/5, proposed first for 2/4). The timed kernels use uninstrumented validators. Record each CPU/wall duration, exact sorted blocker output, output equality, and validation counts. A common one-time corridor validity check is included in both kernels, matching the corridor part of the existing route envelope gate. Other route fields, calibration, class compatibility, bundle hashes, process restart and native physics are not measured. Timing excludes source compilation, data preparation, byte verification and report writing. These are warm local kernel comparisons, not end-to-end timing or qualification evidence.

Inputs, helper dependencies and Runtime hashes are retained before/after; the current Runtime source must be `324504b47198f46e1b33298708035ae6266f68f5a4a4eab655d81cf8ae43bb30`, and generated unapplied candidate must be `d5f354c60af83c6f9d32f6b43a893c19486ddcb1f8d2f85c78f526fe48d0273c`. The report retains exact compiled kernel text and its hashes. A mismatch cannot be called successful; all outputs remain non-authorizing.

Two tiny synthetic tests passed in **0.013 s**, covering clear and blocked scenes, five paired outputs, exact validation counts, absence of route/calibration functions, count-wrapper restoration on error, and source guards. No actual evidence processing or queue submission was done by the implementation agent.

Root may submit this command through the existing queue authority, using a fresh output directory:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement\Batch 01\Restart Qualification Tools\benchmark_route_kernel.py' --compact-report 'D:\CodexEvidence\LLMs-in-Robotics\recovery-final-compact-parking1-001\compact-corridors.json' --compact-receipt 'Long-Horizon Adaptive Robotics Expirement\Evidence\queue-receipts\20260923T094229717164Z-170731a4.json' --construction-extraction 'D:\CodexEvidence\LLMs-in-Robotics\recovery-final-construction-extraction-001\extraction.json' --screen-receipt 'Long-Horizon Adaptive Robotics Expirement\Evidence\queue-receipts\20260923T092904839719Z-04533969.json' --extraction-receipt 'Long-Horizon Adaptive Robotics Expirement\Evidence\queue-receipts\20260923T094040234587Z-68225cae.json' --output 'D:\CodexEvidence\LLMs-in-Robotics\recovery-route-kernel-001'
```

The completion marker is `kernel-benchmark.json`. Inspect it only after the successful official benchmark receipt. All original physical/timing outcomes remain unchanged.
