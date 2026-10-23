"""Finalize Session 19 navigation from authenticated terminal artifacts."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
INV = HERE.parent
C = INV.parent
REPO = C.parents[2]
MAP = REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map'
AGENT = REPO/'agents/Codex'
OUT = HERE/'handoff-001'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def bind(path):
    raw = path.read_bytes()
    return {'path':str(path.resolve()), 'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw)}

def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')

def main():
    if '--resume_after_timezone_failure' not in sys.argv:
        OUT.mkdir(exist_ok=False)
        for job_id, name in [('20260930T235021451489Z-98739620','map'),
                             ('20260930T234616978587Z-963b61f6','final-verification'),
                             ('20260930T234143037668Z-6e29b119','final-build')]:
            proc = subprocess.run([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),
                                   'status',job_id], cwd=REPO,capture_output=True,text=True,encoding='utf-8',check=True)
            value = json.loads(proc.stdout)
            assert value['state']=='succeeded' and type(value['exit_status']) is int and value['exit_status']==0
            save(OUT/(name+'-official-status.json'),value)
        assert read(HERE/'map-comparison-001/receipt.json')['passed'] is True
        assert read(HERE/'browser-001/receipt.json')['passed'] is True
        verification=read(HERE/'verification-003/verification.json')
        assert verification['passed'] is True
        assert verification['report_files']['report.html']['sha256']==bind(INV/'report.html')['sha256']
        summary=read(C/'registration/session19-accounting-001/final-001/summary.json')
        assert summary['job_count']==74 and summary['states']=={'failed':10,'succeeded':64}
        sources=read(MAP/'releases/RCI001-C02-dev-114/snapshot.json')['sources']
        checked=[]
        for path, expected in sources.items():
            actual=bind(REPO/path)
            assert actual['sha256']==expected['sha256'] and actual['bytes']==expected['bytes'],path
            checked.append(actual)
        save(OUT/'frozen-source-check.json',{'passed':True,'snapshot':bind(MAP/'releases/RCI001-C02-dev-114/snapshot.json'),
             'source_count':len(checked),'sources':checked,'scope':'All current frozen apparatus source bytes equal the final pre-scoring snapshot.'})
        capacity={drive:{'total':shutil.disk_usage(drive).total,'free':shutil.disk_usage(drive).free} for drive in ('C:/','D:/')}
        save(OUT/'capacity.json',{'measured_at':datetime.now(timezone.utc).isoformat(),'bytes':capacity,
             'reserve_bytes':100_000_000_000,'retirement_headroom_bytes':2_000_000_000,
             'scope':'Fresh filesystem free capacity, not physical reclamation or model billing.'})
        old_report=AGENT/'Session Summaries/HumanReport19.md'
        archive=HERE/'session19-engineering-chronology.md'
        with archive.open('xb') as stream:
            stream.write(old_report.read_bytes())
        save(OUT/'chronology-archive.json',{'source_before_rewrite':bind(old_report),'archive':bind(archive),
             'original_location':'agents/Codex/Session Summaries/HumanReport19.md',
             'scope':'Exact pre-final in-progress chronology. Its historical relative links resolve from the original location, not this archival copy. Superseded active statuses are preserved as history.'})
    else:
        assert (OUT/'preparation-interruption.json').exists()
        assert read(OUT/'frozen-source-check.json')['passed'] is True
        summary=read(C/'registration/session19-accounting-001/final-001/summary.json')
        sources=read(MAP/'releases/RCI001-C02-dev-114/snapshot.json')['sources']
        checked=read(OUT/'frozen-source-check.json')['sources']
        capacity=read(OUT/'capacity.json')['bytes']
        old_report=AGENT/'Session Summaries/HumanReport19.md'
        archive=HERE/'session19-engineering-chronology.md'
        assert old_report.read_bytes()==archive.read_bytes()
    local_now=datetime.now().astimezone()
    assert local_now.utcoffset().total_seconds()==-7*3600
    stamp=local_now.strftime('%Y-%m-%d %H:%M')+' PDT'
    prefix='../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/'
    report=f'''# Session 19 — Campaign 002 completed at the prescribed stop

September 30, 2026, 09:54 PDT through handoff preparation at {stamp}. Git closeout follows this report.

**Campaign 002 is terminal: 10 valid successes, one infrastructure-invalid attempt with unknown task outcome, and nine not run.** The unchanged coordinator applied the immediate evidence stop at ordinal 11, Home06, and settled all twenty original slots. The campaign and investigation are complete; the next step is Randy's review when convenient. Nothing requires his presence now. No attempt was replaced or retried.

Open the [interactive investigation]({prefix}investigation/report.html) for the system explanation, campaign comparison, original images and synchronized episode evidence. The [qualification companion]({prefix}investigation/session19-history-001/candidate-005/html/qualification-report.html) preserves all 156 historical rows, including failures and unassessed diagnostics.

| Campaign | Planned | Valid successes | Valid task failures | Infrastructure-invalid | Not run |
|---|---:|---:|---:|---:|---:|
| 001, unchanged | 24 | 6 | 0 | 4 | 14 |
| 002 | 20 | 10 | 0 | 1 | 9 |

The ten successes comprise five per known family. Each passed all 41 original independent checks after authentic queue success. Valid-trial success is 5/5 per family, with a descriptive 95% Wilson interval of 56.6–100%; pooled 10/10 gives 72.2–100%. These intervals assume independent trials and condition on validity and early stopping. All-planned operational completion is 10/20, with unresolved sensitivity bounds of 50–100%. Two known simulated fixtures are two scenarios, regardless of repeat count. This is no causal estimate of the repair's effect, high-reliability certification, unseen-task result or evidence of physical transfer.

## What the robot did, and why execution stopped

[Stock01]({prefix}investigation/stock01-investigation.md) moved A1 into the fixture and handed control back; the conventional controller then processed, inspected and placed it in tray1. Stock02 also used direct placement, while Stock03–05 used parking1. All five valid Home attempts first received an `unsupported_resumption` handback rejection, then set up B and completed successfully. In [Home01]({prefix}investigation/home01-investigation.md), the second handback succeeded and the conventional controller processed B2 into tray2. Public model messages explicitly left later completion unverified; protected independent evaluation established success. The report links observations, tool choices, actions, authority changes, continuity and follow-through rather than treating the model's assertion as a result.

[Home06]({prefix}investigation/home06-investigation.md), job `20260930T231138503466Z-c3a5f10f`, ended failed/int1. Bounded infrastructure inspection found `Supervisory heartbeat lease expired`: a 5.490-second supervisory `adapter_step` coincided with a configured two-second heartbeat lease. Frozen source refreshes the heartbeat before draining synchronous persistence. A prolonged drain is a plausible hypothesis; the retained measurements do not establish a disk, scheduling or other root cause. Separate clean namespace/process receipts cannot restore the missing assessment and revocation proof. The task outcome remains unknown. No failed-task evaluator, model transcript or images were used to invent a recovery result.

The prespecified last episodes, [Home10]({prefix}investigation/home10-investigation.md) and [Stock10]({prefix}investigation/stock10-investigation.md), remain explicitly unrun. They were not replaced by more favorable episodes. The original [stop accounting]({prefix}execution/campaign-stop.json) closes remaining admission.

## What changed and what was verified

The session repaired native shutdown by proving protocol quiescence before closing stdin, then requiring genuine EOF, exact bytes/hashes, joined handlers, retirement and normal native exit within the existing caps. Diagnostic005 retained its timeout; its qualified OS trace located reset after forced cleanup without resolving old Smoke027 causality. Diagnostic006 demonstrated one complete bounded drain. Subsequent V30, V31 and V32 failures remain intact. Finite source-reader and fixture corrections led to [V33 qualification]({prefix}io-repair/print-recipe-execution-001/FINDINGS.md): 2,731 regression tests, fresh prerequisites, Native032 66/66, Boundary033 12/12, Smoke031 62/62 and both pilots 38/38 with valid success. No threshold was relaxed. [Engineering chronology]({prefix}investigation/session19-results-001/session19-engineering-chronology.md) preserves the exact earlier progress record; its statuses are historical and its relative links retain their original report base.

The first Map registration failed before writing canonical records. [Metadata reconciliation]({prefix}registration/session19-campaign-001/RECONCILIATION.md) copied the exact sealed plan and manifests inside the permitted Map folder; apparatus bytes and admission remained unchanged. The final [source check]({prefix}investigation/session19-results-001/handoff-001/frozen-source-check.json) matches all 974 frozen source files. The Map now retains all 518 runs/results and comparison note `RCI001-C02-terminal-investigation-001`.

The final report [verification]({prefix}investigation/session19-results-001/verification-003/verification.json) checks all twenty dispositions, eleven official job states and 200 input identities. Static QA verifies 2,660 linked files and 64 byte-identical original PNGs. [Browser QA]({prefix}investigation/session19-results-001/browser-001/receipt.json) covers controls, invalid/unrun empty states, reciprocal reports, desktop/mobile layout and an empty warning/error console. Image-publication selection and narrow-screen overflow found during QA were fixed only in report presentation. Earlier builds and failed checks remain preserved. In-app JSON previews are blocked; static file/hash checks establish those links separately.

[Final queue accounting]({prefix}registration/session19-accounting-001/final-001/summary.json) retains all 74 session jobs: 64 succeeded, 10 failed, none active; total queue child occupancy is 11,570.324 seconds (192.84 minutes). This includes qualification and reporting, is not model time or session duration, and does not measure inference count or billing. [Fresh capacity]({prefix}investigation/session19-results-001/handoff-001/capacity.json) remains above the 100 GB reserve plus 2 GB retirement headroom on both drives.

Randy's approved observer completed before he left; subsequent work required no new UAC or physical action. No API billing, new account, external contact or deployment occurred. Stop here for review. Any further scored work or apparatus change requires a new direction and a prospective protocol; Campaigns 001 and 002 remain immutable evidence.
'''
    old_report.write_text(report,encoding='utf-8')
    campaign_readme='''# Robot-Codex Campaign 002

**Campaign 002 and its investigation are complete.** The original immediate infrastructure/evidence stop at ordinal 11 settled all twenty slots: **10 valid successes, one infrastructure-invalid attempt with unknown task outcome, and nine not run**. The coordinator exited normally after recording the stop. Remaining admission is closed; no retry, replacement or resume is authorized. The next boundary is Randy's review when convenient.

Start with the [interactive investigation](investigation/report.html), [Session 19 handoff](../../../agents/Codex/Session%20Summaries/HumanReport19.md), or [compact continuation](../../../agents/Codex/Summary%20of%20Only%20Necessary%20Context.md). The [original stop](execution/campaign-stop.json) and [all dispositions](execution/) preserve full accounting. Five valid successes per known family do not establish unseen-task performance, physical transfer or a causal repair effect.

## Investigation and exact evidence

- [Stock01](investigation/stock01-investigation.md) and [Home01](investigation/home01-investigation.md) connect original observations, actions, continuity, handback and protected completion. All five valid Home episodes first received a handback rejection, then successfully set up B.
- [Home06 infrastructure investigation](investigation/home06-investigation.md) retains the heartbeat-lease failure and unknown task outcome. A long synchronous drain is a hypothesis, not an established root cause or a passing assessment.
- [Home10](investigation/home10-investigation.md) and [Stock10](investigation/stock10-investigation.md) were preselected last episodes and remained unrun; no substitute was chosen.
- [Final verification](investigation/session19-results-001/verification-003/verification.json), [static QA](investigation/qa.json), and [browser QA](investigation/session19-results-001/browser-001/receipt.json) bind the final report. Direct JSON previews are blocked in the in-app browser; file and hash checks are separate static evidence.
- [Terminal qualification companion](investigation/session19-history-001/candidate-005/html/qualification-report.html) retains all 156 historical rows with their original verdicts. [Publication receipt](investigation/session19-history-001/candidate-005-publication/receipt.json) and [browser receipt](investigation/session19-history-001/browser-005/receipt.json) bind this snapshot. Earlier exports, including root historical build006, remain intact.
- [Final queue accounting](registration/session19-accounting-001/final-001/summary.json) records 74 terminal jobs: 64 succeeded and 10 failed. Queue occupancy is not model time or billing.

## Qualification and immutable protocol

[V33 findings](io-repair/print-recipe-execution-001/FINDINGS.md), [sealed admission](admission/sealed-v1/seal.json), [registration reconciliation](registration/session19-campaign-001/RECONCILIATION.md), and [coordinator records](registration/session19-campaign-001/reconciled-launch-001/) retain the admission trail. Final source checking matches all [974 frozen files](investigation/session19-results-001/handoff-001/frozen-source-check.json). Earlier Diagnostic005/006 and V30–V32 failures remain historical evidence; later success never rewrites them.

The [pre-outcome plan](PLAN.md) fixes twenty slots, ten per known family, world seed173 and sensor seeds23001–23020. Original caps, strict timing, evidence, retirement and stopping rules are unchanged. The sole bootstrap was `Follow the instructions in RobotAgentPrompt.md.`, using existing ChatGPT GPT-6 Astra/max with initially empty continuity and no API billing or subagents. Report presentation edits are outside the apparatus freeze.

[Campaign 001](../campaign-001/investigation/report.html) remains six valid successes, four infrastructure-invalid attempts and fourteen not run among twenty-four planned slots. The [Architecture Map](../../Architecture%20Map/README.md) records comparison note `RCI001-C02-terminal-investigation-001`, with exact sets, denominators, evidence and limits. No model process, campaign coordinator, elevated observer or required human action remains active from this session.
'''
    (C/'README.md').write_text(campaign_readme,encoding='utf-8')
    inv_readme=(INV/'README.md').read_text(encoding='utf-8')
    new_intro='''# Campaign 002 investigation

The completed [actual-results report](report.html) covers all twenty original
terminal dispositions: ten valid successes, one infrastructure-invalid attempt
with unknown task outcome, and nine not run after the fixed immediate stop.
It compares the unchanged Campaign 001 with full denominators and limitations.
No campaign resume or replacement is authorized; the next boundary is Randy review.

The [current qualification companion](session19-history-001/candidate-005/html/qualification-report.html)
preserves all 156 original history rows and the terminal campaign metadata.
The root `qualification-report.html` remains historical build006 with 37 rows;
all earlier exports are retained. The actual builder explicitly binds the current
companion without replacing those historical snapshots.

Start with [Stock01](stock01-investigation.md), [Home01](home01-investigation.md),
the outcome-selected [Home06 infrastructure failure](home06-investigation.md),
or the explicitly unrun preselected [Home10](home10-investigation.md) and
[Stock10](stock10-investigation.md). [Verification](session19-results-001/verification-003/verification.json),
[static QA](qa.json), and [browser QA](session19-results-001/browser-001/receipt.json)
bind the final report and its 64 original PNGs. The bounded Home06 diagnostic
does not consume failed-task outcomes or promote cleanup into qualification.

These builders read authenticated evidence. They never launch a model, simulate
a trajectory, relax the all-twenty-terminal gate or alter an original outcome.
Report-only changes are outside the frozen apparatus inventory. The Campaign 001
sources and investigation remain unchanged.

'''
    (INV/'README.md').write_text(new_intro+'## Permanent qualification companion'+inv_readme.split('## Permanent qualification companion',1)[1],encoding='utf-8')
    v30=C/'io-repair/graceful-process-qualification-001/README.md'
    text=v30.read_text(encoding='utf-8')
    text=text.replace('Session19 continuation of the authorized Campaign002 repair. Randy left the desktop at approximately 11:15 PDT September30; unattended work remains authorized, and any new UAC/physical-presence step must be deferred. The earlier Diagnostic005 elevated observer completed and exited; no further elevation is part of V30.',
        'This is the historical V30 checkpoint. Session19 subsequently qualified V33 and completed the fixed Campaign002 and investigation; see the [terminal campaign handoff](../../README.md). Randy left after the approved Diagnostic005 observer completed. No new UAC or physical-presence action was needed.')
    text=text.replace('Use the one-shot `control.py` actions only after their declared prerequisites pass. It authenticates official success before reading outcomes and independently replays prerequisites.',
        'The historical one-shot `control.py` authenticated official success before reading outcomes and independently replayed prerequisites. Do not run it again.')
    v30.write_text(text,encoding='utf-8')
    readme=AGENT/'README.md'
    text=readme.read_text(encoding='utf-8').replace('- [Session19 current work](Session%20Summaries/HumanReport19.md) — completed apparatus repair and qualification, sealed Campaign 002 execution, and the actual-results investigation; the report remains in progress until closeout.',
        '- [Session19 Campaign 002 investigation](Session%20Summaries/HumanReport19.md) — terminal 10-success / 1-invalid / 9-unrun accounting, original episode evidence, qualification history and review handoff.')
    readme.write_text(text,encoding='utf-8')
    readme=AGENT/'Session Summaries/README.md'
    text=readme.read_text(encoding='utf-8').replace('Latest working report: [HumanReport19](HumanReport19.md), explicitly marked in progress until session closeout. The prior completed session is [HumanReport18](HumanReport18.md).',
        'Latest report: [HumanReport19](HumanReport19.md), the completed Campaign 002 investigation and review handoff. [HumanReport18](HumanReport18.md) preserves the preceding diagnostic preparation.')
    readme.write_text(text,encoding='utf-8')
    context='''# Resume after Session 19 — Campaign 002 review boundary

Campaign 002 and its investigation are complete. **Stop for Randy review; do not resume or replace any slot, modify the frozen apparatus, or invent another campaign.** Check the human inbox for new direction before further work. Project completion is not claimed: this is the plan's explicit review boundary.

Randy authorized this repair/qualification/campaign/investigation without routine reapproval, then left after the approved Diagnostic005 UAC observer finished. All later work was autonomous. No pending UAC, credentials, spending, physical action or user task remains. No model, coordinator or elevated observer remains active. No API billing or subagents were used. All Session19 work claims are closed at handoff; the final closeout commit is discoverable in Git.

## Start here

- [HumanReport19](Session%20Summaries/HumanReport19.md): concise findings, verification and resource accounting.
- [Actual investigation](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/investigation/report.html): system, comparison, original images and episode explorer.
- [Qualification companion](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/investigation/session19-history-001/candidate-005/html/qualification-report.html): all156 original historical rows and terminal metadata.

Below, C = `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002`, I = C/investigation, and MAP = `Long-Horizon Adaptive Robotics Expirement/Architecture Map`. Use project `venv/Scripts/python.exe -X utf8 -B`. Shared queue is `../tools/compute_queue/compute_queue.py`; official status syntax is `status JOB_ID`. Authentic succeeded plus genuine integer0 must precede outcome reads; execution success alone is not qualification.

## Immutable terminal result

- Sealed revision `RCI001-C02-frozen-001`. All20 original dispositions settled; coordinator18144 exited0 at23:15:05UTC September30. `C/execution/campaign-stop.json` closes remaining admission.
- First10, Stock01–05/Home01–05: valid protected successes, all41 independent checks each. Ordinal11 Home06 job `20260930T231138503466Z-c3a5f10f` failed/int1; infrastructure-invalid, task unknown. Ordinals12–20 not_run, no queue submission. Never relaunch `launch_reconciled.py` or an old control/coordinator.
- Full20-slot denominator:10validsuccess/0validfailure/1invalid/9unrun. All-planned completion50%, unresolved bounds50–100%. Valid5/5 per family Wilson95%56.6–100%; pooled10/10 72.2–100%, descriptive under independence and conditional on validity/early stop.
- Campaign001 remains immutable24planned/6validsuccess/4invalid/14unrun. Only two known simulated fixtures; no causal repair, unseen-task, physical-transfer or deployment claim.
- Prespecified Stock01/Home01 explain successful action/authority/continuity/follow-through. All5validHome episodes first had unsupported_resumption handback rejection, then setupB. Stock01/02 direct fixture; Stock03–05 parking1. Last Home10/Stock10 remained unrun. No valid task failure occurred.
- Home06 bounded diagnosis: host reported Supervisory heartbeat lease expired; configured2s lease, supervisory adapter_step5.4901152s. Frozen source refreshes heartbeat before synchronous persistence drain. Long drain is a hypothesis, not device/scheduler causality. Partial clean process/namespace receipts do not restore absent assessment or revocation proof. Failed-task outcomes were not consumed. `I/home06-investigation.md` and `session19-results-001/home06-diagnostic-001/inspection.json` retain the evidence; diagnostic job20260930T232409086429Z-1ceed9ce succeeded0.

## Evidence ready for review

- Final actual build005 job20260930T234143037668Z-6e29b119 succeeded0. Report SHA256 `8c40958896ce7e9edad72053b6e79adba181adf3829e69b9d7cda2426cf1d8d9`. Final verification003 job20260930T234616978587Z-963b61f6 succeeded0; SHA256 `6afd7c9f47b9a4d1a5e0c14a47f08e2ee982c208cf3207c27f28cdd9f33a7717`.
- `I/session19-results-001/verification-003/verification.json`:20 dispositions,11 original official states,200 input identities, failed/unrun-output exclusion, frozenC001counts. `I/qa.json`:2660linkedfiles,5281displayedevents,64byte-identicalPNG/3993463bytes.
- `I/session19-results-001/browser-001/receipt.json`:controls, empty states, source/report navigation, frame-publication regression, desktop/mobile375 and zero warning/error console. Prior failed presentation checks remain. JSON previews blocked by in-app browser; no bypass. Static hashes are separate evidence. Use local HTML or a temporary loopback preview as documented; Session19's temporary server was stopped at closeout.
- Canonical `I/qualification-history.json` SHA256 `4d6cf33cd5b54a6cddf5c0e45bff6735ca7ba44e2724a0785e905a3b8902e869`. Candidate005 job20260930T232408556059Z-c03a60a9 succeeded0,156unchangedrows,3676links. `session19-history-001/candidate-005-publication/receipt.json` and `browser-005/receipt.json` bind publication and inherited full control coverage. Root37-row build006 and all intermediate exports remain historical.
- MAP comparison note `RCI001-C02-terminal-investigation-001` appended and validated by job20260930T235021451489Z-98739620, succeeded0. Map has518runs/518results/13notes. `I/session19-results-001/map-comparison-001/receipt.json` preserves exact sets, evidence and original notes prefix.
- `C/registration/session19-accounting-001/final-001/summary.json`:74terminalsessionjobs,64succeeded/10failed,11570.324257queue-child seconds. No active jobs; model calls and billing unknown. `I/session19-results-001/handoff-001/capacity.json` records reserve/headroom and fresh C/D free bytes.

## Qualification and provenance, only if needed

V33 passed2731regressions, fresh Raw023/Transport026/Host033 and allfive finalgates: Native03266/66, Boundary03312/12, Smoke03162/62, Stock/HomePilot03038/38 each with validsuccess. `C/io-repair/print-recipe-execution-001/FINDINGS.md` and `C/qualification/final-qualification-033/completed.json`. All V30–V32 failures, old Smoke027unknown resetcause and diagnostics remain preserved. `I/session19-results-001/session19-engineering-chronology.md` is an exact historical progress copy, with original-report-relative links and superseded statuses.

Snapshot dev114 SHA256 `7fe9c49414ecc988c6781b2a417fd4e489d505c476e2940be5213be3367cf91a`; all974 frozen source bytes match the final handoff check. Report edits are outside that inventory. CertificateSHA `47e8430b60edd5289f318eaa9ed576e2d6d1ce59dda1b13505e15f6fca0f4244`; planSHA `c62c43e60ce6b1be5f0fd0d8383b7c68d8779cf6baf0c1aa744bcaa235176bb5`. First Map registration failed before canonical write; exact-plan metadata reconciliation succeeded without changing apparatus, admission or manifests. `C/registration/session19-campaign-001/RECONCILIATION.md` preserves both.

Never read/copy/print the external observer private configuration key. No elevated helper remains. Keep human inbox/work claims and supported append-only chat tools. Before chat posts, record UTF8 physical tail, line count/hash; verify exact old prefix and one new header afterward. Final closeout.py must be the last project action, after settled reports/claims/handoff and final inbox. No memory writes unless Randy explicitly requests them.
'''
    (AGENT/'Summary of Only Necessary Context.md').write_text(context,encoding='utf-8')
    changed=[old_report,C/'README.md',INV/'README.md',v30,AGENT/'README.md',
             AGENT/'Session Summaries/README.md',AGENT/'Summary of Only Necessary Context.md']
    assert all(str(p.relative_to(REPO)).replace('\\','/') not in sources for p in changed)
    save(OUT/'receipt.json',{'finalized_at':stamp,'passed':True,'frozen_sources_unchanged':True,
         'navigation_outside_frozen_inventory':True,'files':[bind(p) for p in changed],
         'historical_chronology':bind(archive),'all_terminal_queue_jobs':summary['job_count']})
    print(json.dumps({'passed':True,'finalized_at':stamp,'frozen_source_count':len(checked),
          'report_words':len(report.split()),'context_lines':len(context.splitlines()),'capacity':capacity}))

if __name__ == '__main__':
    main()
