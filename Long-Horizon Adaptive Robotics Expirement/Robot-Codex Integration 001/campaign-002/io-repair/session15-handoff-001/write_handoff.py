"""One-shot documentation handoff; no experiments, tracing or record promotion."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IO = HERE.parent
C = IO.parent
ROOT = C.parents[2]
BASE = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002'


def digest(data):
    return hashlib.sha256(data).hexdigest()


CURRENT = """**Campaign 002 is unfinished; scoring remains closed at an administrator-access boundary.** Fresh V29 passed Raw019, Transport022, Host029, Native028 (66 checks across six references) and Boundary029 (12 checks). Smoke027 then failed its queue job with integer exit 1. No resume, Pilot026 or scored slot ran. Never restart V29 unchanged. The fixed twenty-slot allocation and every evidence, timing and security gate remain unchanged.

The [pre-exit drain repair](io-repair/native-pre-exit-drain-001/DECLARATION.md) requires genuine EOF and complete transport retirement before stdin closure, inside the original deadlines. Its development checkpoint passed **1,137 tests**: 1,003 harness/assessment, 96 qualification and 38 admission. In Smoke027, the safeguard failed closed. The [ordered diagnosis](io-repair/smoke027-queue-failure-diagnosis-001/FINDINGS.md) locates WinError10053 in channel 1 upload read **7.2268 ms before actual stdin closure**. Both channels lacked genuine EOF; matched observed bytes do not establish EOF. This rules out the later stdin operation for this event, while the OS/native cause remains unknown. The earlier Native004 diagnostic completed without reproducing the abort and remains unassessed, not a qualification pass.

**Next step requires an elevated PowerShell session for the [bounded no-model TCP trace coverage plan](io-repair/smoke027-os-trace-readiness-001/PLAN.md).** The actual read-only preflight found an unelevated token and Packet Monitor access denied. Two synthetic closure controls passed locally, but OS trace coverage is not yet established. Randy's September 27 18:10 direction explicitly requires stopping at a genuine physical/admin-access boundary. No trace, filter, security setting, spending or further model launch was performed for this handoff. The plan first tests whether a narrowly filtered trace captures both known FIN and RST controls; any later native diagnostic needs its own prospective declaration and fresh identities.

At **2026-09-29 18:54:45.716054 UTC**, [Session15 accounting](registration/session15-accounting.json) records **122 jobs: 104 succeeded, 18 failed, zero active in that accounting scope**, and 26,952.061177 terminal queue seconds. Observed model starts are a **31 lower bound** (19 assessable plus 12 diagnostic); 20 literal requests are counted separately. Exact generations and billing remain unknown. Scored starts and registrations are zero. All 913 previous source bindings and Session14 accounting bytes remain intact; the new artifact has 960 bindings.

[Canonical history](investigation/qualification-history.json) now contains **129 rows**, with Smoke027 the latest failed basis and latest model qualifier. The three Session15 append receipts preserve all 122 earlier raw rows and 19 exports. Report-reader/QA checks passed 151 tests, and the additive accounting checks passed eight. Generated HTML remains an explicitly historical snapshot; the local-URL browser-policy verification limit remains. Campaign001 is frozen at six valid successes, four invalid and fourteen unrun slots. The [Session15 report](../../../agents/Codex/Session%20Summaries/HumanReport15.md) explains the evidence, retained failures and access dependency.
"""

REPORT = """# Session 15 — Campaign 002 stopped at a concrete admin-access boundary

Campaign 002 is **not complete**. The repaired shutdown sequence passed its development checks and the first five fresh qualification gates, then Smoke027 failed during interruption. Zero of the twenty scored slots have started or been registered. The next useful measurement requires an elevated Windows session; the current token cannot access Packet Monitor.

## What changed and what ran

The [declared pre-exit drain repair](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/native-pre-exit-drain-001/DECLARATION.md) makes genuine transport EOF, byte completion, finished namespace state and completed handlers prerequisites for closing native stdin. It operates inside the original five/ten-second native bounds and 25-second bridge bound. An independent verifier checks the source closure, transport ledger and performance-counter ordering. The final source-bound development checkpoint passed 1,137 tests: 1,003 harness/assessment, 96 qualification and 38 admission. Earlier development failures and their corrections remain retained.

Before that repair, Native004/dev092 asked a separately declared timing question. Its single queue invocation completed with exit 0 and reached the interruption trigger, but the abort did not recur. Its genuine EOF, durable evidence and retirement observations are diagnostic only. The map records completed/unknown/not-assessed; no qualification was inferred from queue success.

| Fresh V29 gate | Original outcome |
|---|---|
| Raw019, Transport022, Host029 | Independently passed after official success; Host029 passed all eight checks |
| Native028/dev094 | All 66 checks across six reference episodes passed |
| Boundary029/dev095 | All 12 checks passed |
| Smoke027/dev096 | Queue failed with integer exit 1; no scientific assessment; task outcome unknown |
| Resume, both Pilot026 stages, scored campaign | Not launched |

The stopped coordinator is retained at [final-qualification-029](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/qualification/final-qualification-029). Do not restart it. Prepared downstream V29 operators were never executed.

## What the failure establishes

The [bounded diagnosis](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/smoke027-queue-failure-diagnosis-001/FINDINGS.md) authenticates 243 transport ledger rows. The first fault was channel 1 upload-read ConnectionAbortedError, errno/winerror 10053. It occurred 0.5954 ms after the observed thread-closed notification and **7.2268 ms before actual stdin closure**. The later stdin operation therefore cannot explain this particular earlier abort. That observation does not identify the kernel, peer or host-network cause and does not retroactively resolve Smoke026.

Both channels lacked genuine EOF/upload drain despite matching observed endpoint bytes and zero active H2 streams. The new barrier failed closed; forced owned retirement followed within the existing bounds. The retained interruption, old-token denial, durable retention and three namespace-retirement records remain evidence of their individual checks, not a successful smoke qualification. Nothing was relaxed to promote the result.

## Exact human dependency

The [prepared trace packet](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/smoke027-os-trace-readiness-001/PLAN.md) needs an **elevated PowerShell session**. The actual read-only preflight found `elevated_administrator=false` and `pktmon status` exit 5, Access denied. No capture or filter was changed. Randy's September 27 18:10 instruction says to stop at a genuine "physical/admin access" boundary and explain the needed decision; this is that specific boundary, not a request for general campaign approval.

The first elevated action is a no-model coverage test: fresh output directory, the fixture's exact loopback port, FIN/RST-only filters, header-prefix capture, 16 MiB ceiling, at most 30 seconds and owned cleanup. Its two synthetic controls already distinguish orderly EOF from a deliberate reset; whether OS tracing sees both is still unknown. A separately declared native diagnostic follows only if coverage is adequate. Existing deadlines stay fixed. Suppressing the abort or treating byte equality as EOF would weaken the gate; closing the relay earlier may interrupt a required native cleanup RPC. Source-level transport changes or a different host are larger, unqualified alternatives. The evidence does not establish a permanent impossibility.

## Preserved records and validation

[History](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/investigation/qualification-history.json) has 129 entries; all 122 earlier raw entries and 19 exports are preserved. Native004 has a finite completed-unassessed report branch, verified by 151 reader/QA tests. Smoke027 remains failed/invalid/unknown. Its first settlement helper failed before map mutation; the retained reconciliation verified absence and settled exactly once. Initial history preparation's wrong declaration path and all earlier failed development checks remain available.

[Session15 accounting](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/registration/session15-accounting.json), authenticated at 18:54:45.716054 UTC on September 29, contains 122 jobs (104 succeeded, 18 failed, none active in scope), 26,952.061177 terminal queue seconds, 31 observed model starts as a lower bound, and 20 separately counted literal requests. Exact service generations and billing remain unknown. Its eight adversarial tests passed; all 913 prior bindings and Session14 bytes were preserved, with 960 current bindings.

[Final validation](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Robot-Codex%20Integration%20001/campaign-002/io-repair/session15-final-validation.json) records current/archive source identity, original framework and Campaign001 preservation, map/hash checks, documentation links and the exact closeout scope. Campaign001 remains six valid successes, four invalid and fourteen unrun slots. The generated HTML is a historical snapshot, and the existing local-URL browser-policy block remains a verification limitation.

The director-requested Audit Storage and Long-Horizon Adaptive Robotics Experiment chats were concluded with byte-identical transcripts and concise summaries. No subagents were used. This session's scopes are closed in Work/Done, including [the repair](../../../Work/Done/enforce-native-transport-drain-before-process-exit.md), [V29 execution](../../../Work/Done/run-fresh-v29-final-qualification.md), [diagnosis](../../../Work/Done/diagnose-smoke027-pre-exit-failure.md), [trace preparation](../../../Work/Done/prepare-bounded-windows-tcp-trace-coverage.md), [accounting](../../../Work/Done/reconcile-session15-campaign-accounting.md) and [this handoff](../../../Work/Done/document-session15-admin-trace-boundary.md). Closing the session does not complete the campaign.
"""

CONTEXT = """# Codex resume — Session15 administrator-access handoff

Randy's Sep29 10:00 PDT direction: the rate limit is resolved; continue until Campaign002 is finished. Sep27 18:10 authorizes bounded infrastructure repair, fresh full qualification, the fixed20 campaign and actual-results investigation without routine approval stops, but explicitly stops at genuine physical/admin access or other human-only boundaries. **Do not use subagents.** No goal, automation, reset, spending or memory update was requested. Campaign002 is unfinished with zero scored starts/registrations. Campaign001 stays frozen at6 valid successes/4invalid/14unrun.

## Immediate next action and boundary

Read IO/smoke027-os-trace-readiness-001/PLAN.md. OS socket-closure attribution needs an elevated PowerShell session; current read-only preflight found an unelevated token and `pktmon status` exit5 AccessDenied. No trace/filter/security change was performed. The prepared first step is a fresh, no-model synthetic coverage test, narrowly filtered to exact loopback port and FIN/RST, 40-byte header prefix,16MiB cap,30s bound, complete loss/wrap checks and owned cleanup. Current installed `pktmon filter remove` removes ALL filters; use only if entire current list is exactly the two owned filters and was initially empty. No arbitrary providers or unrestricted capture. Synthetic development001 passed orderly EOF and deliberate reset; OS loopback visibility is UNVERIFIED. Only after adequate coverage may a new prospectively declared native diagnostic use fresh IDs and original bounds. This is an admin-access dependency, not general launch approval; do not repeat failed qualifiers unchanged or assume tracing will work.

## Decisive evidence

V29 stopped permanently at Smoke027/dev096, job20260929T182650537335Z-49496959 failed integer1 at2026-09-29T18:31:48.027499UTC. Coordinator38867 ended exit1. No resume, Pilot026 or scored slot ran. Q/final-qualification-029/coordinator-launch-receipt.json SHAabc79d255b77da974c9472d396ac16cadec2554c2e331047f96b9fde4f7ba937. Original failed/invalid/unknown Q/RCI001-C02-smoke-027/queue-failure.json; no scientific assessment exists. Never restart V29 or use its partial passes for campaign admission.

IO/smoke027-queue-failure-diagnosis-001/{analysis.json,ordered-analysis.json,FINDINGS.md}:243 hash-linked transport rows. First channel1 upload_read ConnectionAbortedError(errno10053,winerror10053),seq216 atperf564192858042400ns. Thread-closed observed564192857447000ns; actual stdin close begins564192865269200ns. Abort is0.5954ms after observed thread closure and7.2268ms BEFORE stdin closure. This rules out that later operation for this event, not the native/kernel cause or prior Smoke026 cause. Both channels lacked EOF/upload drain, though observed bytes match and active H2 streams=0. New pre-exit barrier failed closed; forced owned retirement, native exit0, host0 and three qualified namespace retirements retained. No success sidecars. Bounded diagnosis only after fresh failed/int1 official status. First settlement helper errored before map writes; reconciliation verified absence and settled once. Do not settle again.

Native004/dev092 job20260929T172359627310Z-e9b8409e succeeded int0, reached interruption, one genuine EOF, no abort, native/host0, all retirements. It did not reproduce the error and is completed/unknown/not_assessed, NOT qualification. IO/native004-diagnosis-001/observations.json SHA9662b75391f74af9f87af2d80bc8c9d199eb8c1933a64fd0ec315afea9ba924a. Earlier Native003 usage-limit and Smoke026 failure remain unchanged. Listener-lifetime no-model matrix was exploratory: actual18-byte tail differed from declared17; retained as deviation, not conforming qualification.

## Implemented repair and frozen lineage

IO/native-pre-exit-drain-001/DECLARATION.md prospectively requires actual EOF, complete bytes, qualified FINISHED namespace and joined handlers BEFORE native stdin closes. H/native_exit_drain.py and H/native_quiescence.py enforce original5sgraceful/10stotal (bridge25s unchanged); missing closure fails closed. Bridge/runtime callback and bounded16KiB sidecars bind old ledger/clock/cleanup. A/pre_exit_integrity.py verifies finite frozen method/helper closure and original gates independently. No model/task/recovery policy, timing, evidence or security relaxation.

Full checks037:445H+558A=1003pass. Final lineage003 reuses unchanged Q96 and passes38admission:1137total.234 measured Python sources unchanged. Test/freeze evidence IO/native-pre-exit-drain-001/{production-state-004.json,lineage-checks-003/receipt.json}, IO/checks-037/repair-test-receipt.json SHA63025c37296fc74ed3bd4575cea5f47868a57764cd3f4294835fcca8fd009ae8. Earlier failed checks retained; do not rerun completed checks without cause.

Q/prepare_model_v21.py and Q/run_final_qualification_v29.py allocate dev093anchor→dev094Native028→dev095Boundary029→dev096Smoke027+Pilot026. Raw019/Transport022/Host029 passed independently; Host0298checks. Native028job20260929T181722001854Z-0969aa67 passed66checks/sixreferences; Boundary029job20260929T182552773823Z-c7a26e97 passed12. Readiness029 SHAa4485adf87eeaeb990a06481213957a4ecac6153c25228fd866687a1a88703d0 binds712core sources. Dev096 contains958sources; final current/archive check is IO/session15-final-validation.json. Original624source identities remain protected. IO/control_campaign_admission_v29.py and launch_campaign_v29.py were prepared/compile-checked ONLY; do not execute after failed V29. C/registry_session15.py is CLI-only, not an importable finish API.

## Current records

I/qualification-history.json129rows SHAcc2bc83f1c7b887c3e8f16d0cab65beb509f1f7e55e44310833725000375590e. Both latest basis and latest model qualifier are Smoke027failed. Session15 appended7records in3batches, preserving122prior raw rows and19exports. Receipts I/qualification-history-append-session15-receipt.json and I/v29-append-staging/{native-boundary-publication-receipt.json,smoke027-publication-receipt.json}. Completed-unassessed Native004 branch in report/QA is exact-source/identity-bound;151tests passed. Generated HTML remains historical, not rebuilt. Existing local-URL browser-policy denial remains a verification limit.

REG/session15-accounting.json SHA3bcdf068f2eb9c7714a68020d156b920e55c6627656914573f8d08fcbfa6df97 at2026-09-29T18:54:45.716054UTC:122jobs104succeeded18failed0active in scope;26952.061177terminal queue seconds;31observed model-start lower bound=19assessable+12diagnostic;20literalrequests separate; exact generations/billing unknown;0scored.960bindings/all913prior preserved,19exportsunchanged. Session14artifact SHA c0422c911e5a85f9e98497800865c4f4763a00dc18b6778f44cdc3a344bd1ee4 remains unchanged. New assembler eight adversarial tests passed; do not rerun its one-shot assembly.

Map154revisions471runs471results5architectures12notes, independently structural/hash validated.1054protected files and5original map prefixes remain protected. Read HumanReport15 for failures, source reviews and paths. Claims closed in Work/Done; no active experiment/runner. AuditStorage and Long-HorizonAdaptiveRoboticsExperiment transcripts were concluded byte-identically at director request, with summaries. Session15closeout scopes IO/session15-closeout-paths.json; successful tool commit/push is final project action, no checks afterward. Do not blindly pull a dirty tree.

## Non-negotiable resumption rules

Fresh official `succeeded` plus genuine integer0 before scientific output reads/hashes; independent assessment still required. Fresh failed/int1 allows only prospectively declared bounded infrastructure diagnostics with taskunknown. Never read/hash active outputs. Some operators run actions without argparse; inspect source rather than trying --help. record_checks can exit0 with passedfalse; inspect receipt.

After supported repair, require full fresh Raw/Transport/Host/native/boundary/smoke+both pilots before fixed20 registration/sealing/scoring. World173, sensors23001–23020 alternating reverse pairs,10/family; fresh GPT6Astra/max via existing ChatGPT; sole exact bootstrap `Follow the instructions in RobotAgentPrompt.md.`; empty continuity.600model/900sim/1100hostwall/150followthrough seconds;20actions50observations512MiB;lag<100ms,1sRTF[.95,1.05],<1%badwindows. Invalid consumes slot;2consecutive ordinaryinvalid stop; severe integrity/isolation/evidence/retirement/capacity failure stops immediately.100GBreserve+2GBheadroom. No replacements, new spending/accounts/API billing, security weakening, deletion/relocation or physical deployment.

Qualification stop is NOT campaign_terminal. Eventual actual-results report recipe IO/v28-terminal-report-recipe-001.md requires actual qualifier ledger and20slot plan/stop/dispositions; preserve19exports and original recordings, missing explicit, no privileged reconstruction. Full denominators C00124/C00220 and valid bounds separate. No causal reliability claim.

Paths: C=Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002;R=C.parent;IO=io-repair,Q=qualification,H=harness,A=assessment,I=investigation,REG=registration;MAP=Long-Horizon Adaptive Robotics Expirement/Architecture Map. Python `.\\venv\\Scripts\\python.exe -X utf8 -B`; queue `C:\\Users\\cresp\\Documents\\Dandelion Engineering\\tools\\compute_queue\\compute_queue.py`. Supported chat tool only, exactUTF8prefix+oneheader verification; latest handoff receipt IO/session15-handoff-001/chat-receipt.json. Scoped whitespace check with core.whitespace=cr-at-eol. No post-closeout project action.
"""


if __name__ == '__main__':
    receipt = HERE / 'documentation-write-receipt.json'
    if receipt.exists():
        raise RuntimeError('Documentation handoff already recorded')
    changed = []
    for path, title, body in [
        (C / 'README.md', '# Robot-Codex Campaign 002', CURRENT),
        (IO / 'PROGRESS.md', '# Session15 qualification and admin-access stop', CURRENT.replace('](io-repair/', '](../io-repair/').replace('](registration/', '](../registration/').replace('](investigation/', '](../investigation/').replace('](../../../agents/', '](../../../../agents/')),
    ]:
        old = path.read_bytes()
        old_text = old.decode('utf-8')
        heading, old_body = old_text.split('\n', 1)
        new = title + '\n\n' + body + '\n**Retained Session14 and earlier checkpoints — historical; current status is above.**\n' + old_body
        path.write_text(new, encoding='utf-8', newline='\n')
        assert path.read_text(encoding='utf-8').endswith(old_body.replace('\r\n', '\n'))
        changed.append({'path': str(path), 'before_sha256': digest(old), 'after_sha256': digest(path.read_bytes()), 'historical_body_preserved': True})
    report = ROOT / 'agents/Codex/Session Summaries/HumanReport15.md'
    with report.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(REPORT)
    context = ROOT / 'agents/Codex/Summary of Only Necessary Context.md'
    before = digest(context.read_bytes())
    context.write_text(CONTEXT, encoding='utf-8', newline='\n')
    changed.extend([{'path':str(report),'after_sha256':digest(report.read_bytes())}, {'path':str(context),'before_sha256':before,'after_sha256':digest(context.read_bytes())}])
    receipt.write_text(json.dumps({'passed':True,'changed':changed},indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'written':len(changed),'receipt':str(receipt)}))
