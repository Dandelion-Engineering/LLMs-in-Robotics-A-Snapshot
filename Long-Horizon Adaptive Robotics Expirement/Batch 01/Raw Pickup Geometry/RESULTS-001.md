# Raw pickup geometry diagnostic 001 results

**Selected shared repair: 95 mm row pitch with constant row-zero y = -373 mm for all populations.** It is the smallest of the tested 90/95/100 mm alternatives with no negative native hand distances in the declared cases and successful static IK for all ten slots. The fourth nominal row remains at -88 mm. This is a static development selection, not dynamic validation or a qualification grant.

The [official receipt](../../Evidence/queue-receipts/20260923T074445531735Z-21f143f7.json) reports job `20260923T074445531735Z-21f143f7` **succeeded, exit status 0**, running 2026-09-23 07:44:46.003624–07:44:49.881318 UTC. The [completed summary](../../Evidence/diagnostics/raw-pickup-geometry-001/summary.json) reports unchanged pinned sources and **zero simulation steps**. The [prospective plan](PLAN-001.md) defines the exact finite alternatives and measurement scope.

## Native geometry and reach

Each variant has **1,630 prescribed hand-pose samples**: two geometric conditions × five planar observation offsets × 163 TCP heights from 18 through 180 mm at 1 mm spacing. Across five variants there are **8,150 hand-pose samples**, **52,975 neighbor/pose minimum-distance measurements**, and **4,036 whole-Panda IK waypoints over 50 paths**. Each neighbor distance is minimized over the native hand/finger collision geoms. Negative-count columns count neighbor/pose measurements, not impacts or physical episodes.

| Variant | Minimum distance, seed-2 positions + offsets (mm) | Minimum distance, inward-6 mm pairs + offsets (mm) | Negative measurements: seed 2 / inward | IK converged | IK waypoints | Waypoints with native robot/other-stock penetration |
|---|---:|---:|---:|---:|---:|---:|
| Current 74 mm | -16.442524 | -18.855166 | 135 / 270 | 10/10 | 787 | 30 |
| 90 mm | -1.178736 | -3.591378 | 4 / 24 | 10/10 | 813 | 0 |
| **95 mm** | **+3.591198** | **+1.178556** | **0 / 0** | **10/10** | **821** | **0** |
| 100 mm | +8.361132 | +5.948489 | 0 / 0 | 10/10 | 828 | 0 |
| Current grid, 90° yaw | -3.863027 | -8.361312 | 16 / 156 | 10/10 | 787 | 1 |

The current grid also penetrates at **zero observation offset**: A3-relative B6 has minimum native signed distance **-12.626577 mm** across the height samples. Thus the source geometry supplies a collision mechanism without needing the added observation offset. This supports the A3/B6 interference hypothesis; it does not reconstruct the exact dynamic contact that tipped B6 in C0-007. A quarter-turn shifts the interference to the column neighbor B2 and is not a demonstrated cure.

For 95 mm, the smallest declared hand distance is **0.0011785557467558036 m**, at TCP z=18 mm, 4 mm offset toward the north neighbor, with pairwise inward relative jitter 6 mm. With zero observation offset, the minima are +7.407145 mm at seed-2 positions and +4.994503 mm for inward pairs. The 95 mm full-arm paths have maximum position residual **0.0009890136315140144 m**, maximum true orientation error **0.0030099178558507214 rad**, and minimum joint-limit margin **0.1326605929750917 rad**. The actual seed-2 southern row targets are A1 `(0.318569673,-0.374209053)`, B2 `(0.406885354,-0.375448504)`, and A3 `(0.490600603,-0.371628637)` m; all three are included in the converged paths.

**The 1.178556 mm separation is not unused tracking allowance.** The hand-distance probe prescribes an exact pose; the separate IK residual and orientation error are not subtracted from that number to manufacture a combined guarantee. No servo tracking, contact dynamics, sensing quality, continuous segment clearance, successful grasp/carry, or full task performance was established. Frozen boxes use an upright center-z=18 mm proxy. Pairwise inward extrema are separate conservative neighbor tests, not a claim that all those extrema form one jointly realizable layout. All failed alternatives remain in the evidence.

## Provenance

The [diagnostic manifest](../../Evidence/diagnostics/raw-pickup-geometry-001/manifest.json), source archive and [evidence index](../../Evidence/diagnostics/raw-pickup-geometry-001/evidence-index.json) retain every consumed asset, exact selected functions, generated XML and per-sample records. The summary's present bytes were checked against its indexed SHA-256.

- C0-007 source `cell.py`: `ac13595b62ae51bb1cc5dd7387ab0ec605253fa65a0a276c5c85395929cb40fa`.
- Native Panda files were checked against cal005 manifest `6572278756b0491719d68d285518d4b5bcfa24411ce892837adcaecb02e265e0`; finger mesh `finger_0.obj`: `215098c0fcdf7192f6c503a37cf49e3efecf8a9e1320f02b17c5584d89cc5b2c`.
- Diagnostic source archive: `b4fbcfb7546d7d3c3736d0a56f3ae83b215d547c0f90b9cb30a68baedbdd47a3`; completed summary: `ae4dd791f4ebffb5a4cd8a7ce0e0c98fb401475efb0847d3c9e1c91a01f2fcc6`.

## Qualification fixture audit after grid selection

A bounded read-only audit found **no old raw-grid coordinates or row-pitch literals in Recovery Qualification's source, declarations or documentation**. `run_screen.make_loop` calls the current `Cell.build_scene(n, world_seed, layout_seed)`; `fixture.construct_xml` changes only declared main-geom mass/friction before compilation. Independent validation retains the generator's original XML bytes. `PhysicalLoop` obtains current `Cell`, `ZONES` and `zone_half`; geometry sampling derives transforms and extents from that compiled model. Construction/validation seeds, populations, lexical payload IDs, source height, trigger, five-second trial and full admission-window hold checks remain applicable without positional substitutions.

The fixture therefore inherits the repaired grid once the shared generator and its protected descriptor checks agree. Its new source archive/XML/class spec will bind that grid at execution. This audit is not a new physical readiness pass: fresh physical calibration and construction/validation must establish performance under the changed pickup locations. No Runtime or Recovery Qualification file was modified by this audit.
