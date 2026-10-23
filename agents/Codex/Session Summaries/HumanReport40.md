# Session 40 — Verified storage cleanup; D: capacity still blocked

Measured 2026-10-09T20:11:27.857034-07:00; Git closeout follows this report.

Removed **4,042 regenerable environment cache files and 26 empty project temporary trees** from C:. The caches contained 30,008,579 bytes (0.027948 GiB); their reported file allocation was 38,682,552 bytes. Every source survives unchanged. No D: deletion candidate met the evidence/dependency requirements.

| Volume | Observed net free change | Final free capacity |
| --- | ---: | ---: |
| C: | -319,283,200 bytes (-0.297356 GiB) | 520.466434 GiB |
| D: | +0 bytes (0.000000 GiB) | 36.895508 GiB |

Combined observed change: -319,283,200 bytes. These full-session observations include audit artifacts and other host activity; they are distinct from the safely removed files. The narrower deletion interval is recorded in the [detailed audit](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-40/REPORT.md). Measurements precede final Git closeout.

D: remains **13.104492 GiB short of 50 GiB**. Its 1 MiB exFAT allocation units cause major overhead: the apartment artifacts contain 17.33 GiB but occupy 475.21 GiB in file allocation. Large original runs, failed qualifications, checkpoint histories, repeated-but-referenced staging trees, published robot filesystems, model assets and Git history remain protected. No uncertain candidate was removed.

Full pre-cleanup hashes matched all 344,286 previously inventoried historical files, and a fresh inventory covered 137,516 Session 39 files. Post-cleanup retained metadata, critical hashes, all 263 working/frozen source pairs, the unchanged commissioning certificate, cache-source hashes, environment imports, Git connectivity and project process/mount checks passed. The detailed report states the exact verification scope and links the deletion manifest, queue receipts and retained-candidate reasoning.

The assignment ends here. **No preparation helper, v4 creation, model call, Baseline/Maps launch, recovery, comparison or monitor was started.** A later direct instruction is required for any further storage change or experiment preparation. Current release002 and prior experiment states remain as recorded in Session 39.
