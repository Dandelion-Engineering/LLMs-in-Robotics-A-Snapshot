# Session 25 — generous limits, repaired retirement, and a valid pilot failure

Campaign 003 has a qualified live apparatus, but its required full three-encounter pilot has not passed. **No scored allocation was frozen and no scored model ran.** The latest pilot placed C geometrically, lost public tagged confirmation, received a rejected handback and ended normally. It is a valid task failure under the approved generous envelope.

Start with [the pilot readback](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-003/investigation-002/pilot-003-behavior-readback.md) or [the synchronized pilot replay](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-003/investigation-002/replays/pilot-003-002/index.html). The replay is local-only; its compact evidence, source and browser captures are retained in Git.

## What changed and what happened

Main was pulled to `93e4d109`. Randy's time revision was frozen before any new model invocation at 60 model / 70 simulation / 75 wall minutes per C encounter. His separate approval added 120 physical actions per activation, 256 MiB native core evidence per block and 2 GiB total host evidence per block. Observation/image allowances, scientific thresholds, Astra/max, the sole bootstrap, isolation and the 100 GiB reserve plus 2 GiB retirement headroom stayed unchanged. [The runtime record](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-003/runtime-revision-001/README.md) preserves the evidence-based selection and exact authorization.

| Attempt | Retained outcome |
|---|---|
| live002 | Qualified: accepted handback, conventional resumption, terminal continuity, actual image viewing and independent evidence checks passed. |
| pilot002 | Three observed accepted handbacks, then failed journal retirement. Infrastructure-invalid; task outcome unknown. Postmortem recovery does not rescue it. |
| live003 | Fresh qualification after the supported retirement repair. All seven independent checks passed. |
| pilot003 | Infrastructure-valid task failure in encounter 1; encounters 2 and 3 not run. No accepted handback or terminal append. |

Pilot002 exposed a real infrastructure defect: a cloned FUSE mount in another Linux namespace kept the journal daemon alive after the outer unmount. The prospective repair uses an authenticated retirement request, checks the owned run/mount/handle state, records durable closure and binds native exit behavior to independent evidence. Both ordinary and retained-mount mechanics passed, followed by all 16 unchanged full-system checks and fresh live003. The failed mechanical fixture, earlier qualification command/path failures and original failed pilot remain recorded. No background service was signaled or changed. See [the repair lineage](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-003/retirement-revision-001/README.md).

## What the behavior shows

In pilot003, protected placement passed at simulation time 626.938 s. Handback was rejected at 720.572 s with `unsupported_resumption`. The surrounding public packets contained no C detection and failed the unchanged public-completion predicate. The exact internal preview packet was not separately retained. The camera and source explain the gap between geometric placement and controller acceptance without establishing why the tag became unseen.

The model used 20 completed physical requests out of 120, 21 explicit observations out of 50 and four actual image-tool deliveries. It ended normally after about 13 minutes of invocation wall time, well before its 60-minute allowance. No observed time/action/storage cap caused this stop.

It saved a query/capture/status helper, a recovery note and matching canonical continuity. The helper has no physical commands; it is not a saved C-placement procedure. The note honestly preserves uncertain identity and rejected handback. With only one attempted encounter, later reuse and useful transfer are unassessed.

Separately authenticated postmortem evidence from invalid pilot002 shows session 3 reading two prior programs and four result files, then adapting their structure into new session-specific programs. This is observed adaptation, not rediscovery from scratch. The invalid block cannot establish qualified useful transfer, and causal contribution remains unknown. [Its readback](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-003/investigation-002/pilot-002-behavior-readback.md) preserves that distinction.

## Inspection, storage and remaining decision

The current replay exposes 88 recorded frames, 8,795 journal records, the public stream, exact file versions/diffs, fresh-session boundaries and rejected handback. Nine independent data checks and actual browser QA passed, including all 44 semantic jumps and all five workspace-boundary jumps. Failed analysis/viewer/checker revisions remain retained. Desktop/mobile captures are linked from [the investigation handoff](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-003/investigation-002/README.md). Temporary preview services and browser tabs are closed.

Final reader `20261004T053027732238Z-ec67750e` succeeded with integer exit 0 and all seven checks passed. It verified original inventories, exact qualified sources, replay/capture bytes, provenance link bytes and 16,409 historical files. Pilot002 retains its explicitly documented postmortem daemon-log append; other original files remain unchanged. Campaigns 001/002 and the original short-envelope failures remain unchanged.

C: had **113.68 GiB free (122.06 GB)** at final readback; D: had 465.11 GiB. Evidence remains local, with no deletion or D: migration. A future allocation would still need to meet the frozen capacity admission rules.

**Human decision:** retain the current stopped qualification outcome, or authorize a prospective review of the qualification/handback contract before further model runs. The evidence does not justify raising limits again. Randy's October 3 instructions condition scoring on the full pilot and prohibit unchanged favorable retries or scientific changes in response to behavior. No supported remaining infrastructure defect was identified. Scored tooling is prepared and admission-tested, but the failed pilot does not authorize using it. Campaign 003 remains incomplete at this explicit boundary.
