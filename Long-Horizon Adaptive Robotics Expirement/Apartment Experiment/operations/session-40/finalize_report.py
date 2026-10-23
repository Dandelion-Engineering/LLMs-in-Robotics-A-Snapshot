"""Write the storage-only handoff after every cleanup/verification gate passes."""
import json
from pathlib import Path
from storage_audit import HERE,REPO,now,save,sha,volumes

def read(p):return json.loads(p.read_bytes())
def gib(n):return f'{n/1024**3:.6f}'

def main():
    census=read(HERE/'census001/result.json');plan=read(HERE/'cleanup-plan.json');clean=read(HERE/'cleanup-result.json');verify=read(HERE/'verification.json');preserve=read(HERE/'parallel002/preservation-before/result.json');quiet=read(HERE/'quiescence-after002.json')
    assert all(x['passed'] for x in (census,clean,verify,preserve,quiet))
    assert len(plan['targets'])==clean['deleted_targets']
    end=volumes();start=census['volumes_before'];delta={d:end[d]['free']-start[d]['free'] for d in ('C','D')};shortfall=max(0,50*1024**3-end['D']['free'])
    measured=dict(measured_at=now(),interval_start=census['started'],interval='Census start through final report construction, before Git closeout; later Git publication adds a small unmeasured volume change.',volumes_before=start,volumes_after=end,net_free_change_bytes=delta,combined_net_free_change_bytes=sum(delta.values()),deletion_interval_change_bytes={d:clean['volumes_after'][d]['free']-clean['volumes_before'][d]['free'] for d in ('C','D')},removed_logical_bytes={'C':clean['logical_bytes'],'D':0},removed_file_allocation_bytes={'C':clean['file_allocated_bytes'],'D':0},D_required_bytes=50*1024**3,D_shortfall_bytes=shortfall)
    save(HERE/'final-measurements.json',measured)
    assets={}
    for rel in ['census001/files.jsonl.gz','parallel002/preservation-before/session39-inventory.json.gz']:
        p=HERE/rel;assets[rel]=dict(bytes=p.stat().st_size,sha256=sha(p),retention='Retained locally on C, intentionally outside Git; do not delete. Canonical original evidence remains at its original paths.')
    save(HERE/'local-artifacts.json',assets)
    hist=preserve['checks']['historical_full_rehash'];s39=preserve['checks']['session39_full_rehash']
    table='\n'.join(f'| {d}: | {start[d]["free"]:,} | {end[d]["free"]:,} | {delta[d]:+,} | {gib(delta[d])} | {gib(end[d]["free"])} |' for d in ('C','D'))
    root_labels=['C: repository','D: apartment experiment','D: CodexEvidence/LLMs-in-Robotics','D: Campaign 004 exports','D: Campaign 005 exports']
    roots_table='\n'.join(f'| {label} | {x["files"]:,} | {gib(x["logical_bytes"])} | {gib(x["allocated_path_bytes"])} |' for label,x in zip(root_labels,census['roots'][:5]))
    hardlinks=read(HERE/'census001/hardlinks.json')
    summary=f'''# Session 40 — Project storage audit and verified cleanup

**Storage assignment complete. Removed {plan['totals']['files']:,} disposable environment cache files and {plan['totals']['empty_trees']} empty project temporary trees on C:. No D: files were deleted. D: has {gib(end['D']['free'])} GiB free and remains {gib(shortfall)} GiB below the unchanged 50 GiB admission gate. No experiment preparation, model call, launch, recovery, comparison or monitor was started.**

The deleted files contained **{clean['logical_bytes']:,} bytes ({gib(clean['logical_bytes'])} GiB)**; Windows reported **{clean['file_allocated_bytes']:,} bytes ({gib(clean['file_allocated_bytes'])} GiB)** of file allocation. Every removed bytecode file had readable, unchanged Python source and no content-bound package RECORD entry. All installed source/dependency files remain. Only demonstrably empty, project-named temporary directory trees were removed. No duplicate evidence copy was admitted for deletion; therefore no surviving-copy substitution is being claimed.

## Actual volume observations

These are measured free-space differences, not sums of nominal file sizes. The interval is {census['started']} through {measured['measured_at']}, before final Git closeout.

| Volume | Before free bytes | After free bytes | Net free change bytes | Net change GiB | New free GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
{table}

**Combined observed net change: {sum(delta.values()):+,} bytes ({gib(sum(delta.values()))} GiB).** During the narrower deletion interval, C: changed by {measured['deletion_interval_change_bytes']['C']:+,} bytes and D: by {measured['deletion_interval_change_bytes']['D']:+,} bytes. The full interval includes new audit evidence and other host writes; it cannot be attributed solely to cleanup. FILE_STANDARD_INFO allocation excludes directory/filesystem metadata, and resident data/hardlinks can differ from volume-level recovery. A negative net change means free space decreased despite deleting the safe candidates. Large local audit inventories are hash-bound in `local-artifacts.json` and retained outside Git.

## Why the large items remain

The census inspected **{sum(x['files'] for x in census['roots']):,} files across {len(census['roots'])} explicit roots**, including hidden/ignored repository files, installed dependencies, four project-owned D: roots and 26 named C: temporary trees. It reported no traversal or allocation errors and no reparse points. Linux project namespace storage was accounted separately in `linux-inventory.json`; shared WSL infrastructure and other projects were outside deletion scope. There is one Git worktree. No unrelated drive contents or shared caches were selected.

| Measured root | Files | Logical GiB | File-allocation GiB, path sum |
| --- | ---: | ---: | ---: |
{roots_table}

The C: path sum repeats {hardlinks['repeated_allocated_bytes']:,} allocated bytes across identified hardlinks; adjusted regular-file allocation is {gib(census['roots'][0]['allocated_path_bytes']-hardlinks['repeated_allocated_bytes'])} GiB. Removing extra model paths would not release that repeated amount. Directory/filesystem metadata is outside these regular-file totals.

D: is exFAT with **1,048,576-byte allocation units**; C: is NTFS with 4,096-byte units. The apartment root contains **18,611,761,770 logical bytes (17.334 GiB)** but uses **510,255,955,968 file-allocation bytes (475.213 GiB)**. Session 39 alone uses 134.890 GiB of file allocation for 2.985 GiB of data. This overhead explains why deleting a few generic caches cannot solve the D: gate.

The official v2/v3 roots, failed launches, Sessions 36–39 qualifications, original journal/replay/sensor records, checkpoint and schedule histories, published v2 robot filesystems and qualified release remain intact. Apparent restoration/staging copies are retained when referenced by source manifests, certificates, historical preservation inventories or analysis. The large `D:/CodexEvidence/LLMs-in-Robotics` development/recovery trees hold distinct original attempts; the Campaign 004/005 exports support audit/replay readers. C: raw evidence, historical viewer packages, models and Git history remain. Model hardlinks were identified separately in `census001/hardlinks.json`; repeated path sizes are not reclaimable duplicate bytes. See `retained-candidates.json` for 19 high-value retained groups and their dependency evidence.

## Verification and continuation

The first deletion submission failed before changing files because Windows PowerShell could not load Get-FileHash. All 4,068 targets were independently confirmed present, and the unchanged script/manifest succeeded under the installed PowerShell 7 executable. The failed receipt/log and successful receipt remain separate.

The initial serial hash audit was canceled for I/O execution cost, and its queued cleanup-plan job was canceled before starting. Both terminal records and the incomplete log are retained. A fresh eight-worker read-only pass restarted from the beginning with the same comparison gates; the canceled output was not accepted as completed evidence.

The first final process observation (`quiescence-after.json`) flagged this audit's parent Python stdin wrapper as unexpected. Its failed guard is retained. Running the same checker directly after that wrapper exited produced `quiescence-after002.json`; the process filter was not relaxed. No experiment process was observed in either check.

Before deletion, full SHA-256 comparison matched **{hist['roots']} historical apartment roots, {hist['files']:,} files and {hist['bytes']:,} bytes** against the authenticated Session 39 inventory. A fresh full inventory also hashed **{s39['files']:,} Session 39 files / {s39['bytes']:,} bytes**, plus the published robot filesystems. After the strictly C-cache-only deletion, retained census files were checked for unchanged size and modification time; only routine tool/chat state and Git index/fetch metadata were excluded, with their exact paths recorded in the verification receipt. All expected absences and cache-source hashes passed. The postcheck is a metadata comparison plus critical rehashes, not a second whole-history byte rehash.

Both copies of all 263 qualified source files, the certificate, v2 checkpoint 36, v2 Maps checkpoint 22, v3 checkpoint 14 and hidden-schedule/preparation identities were rehashed after cleanup. Certificate SHA-256 remains `49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f`. Installed NumPy/MuJoCo/websockets imports, source syntax and Git connectivity passed. Process/queue/mount readbacks found no project experiment or orphaned runtime. `apartment-v4` remains absent. Shared-queue terminal receipts, exact deletion plan/status and verification are retained beside this report.

| Evidence | Contents |
| --- | --- |
| [Final volume measurements](final-measurements.json) | Exact before/after capacities, observed changes and remaining D: shortfall |
| [Deletion plan](cleanup-plan.json), [actual status](deletion-status.jsonl), [result](cleanup-result.json) | Every exact target, classification, justification, source proof, sizes and deletion outcome |
| [Surviving sources](cache-source-proof.json) | Per-source hashes for all removed bytecode |
| [Retained candidates](retained-candidates.json) | Large protected or uncertain groups and reference/dependency reasons |
| [Full protected hash baseline](parallel002/preservation-before/result.json), [postcheck](verification.json) | Preservation scope, source/certificate/checkpoint identities and environment checks |
| [Final runtime readback](quiescence-after002.json), [monitor state](monitor-status.json) | Process, queue, mount and paused-monitor observations |
| [Census](census001/result.json), [Linux inventory](linux-inventory.json), [local inventory identities](local-artifacts.json) | Measured scope, volume allocation and retained external-to-Git inventories |
| [Reader change](reader-change.json), [failed deletion disposition](cleanup-attempt001-disposition.json) | Explicit canceled/failed maintenance attempts and why their output was not accepted |

This session stops at the storage handoff. No further disposable D: data was demonstrated, and no gate was relaxed. Any future evidence-storage migration or new preparation attempt requires later direct human direction; old once-only helpers remain used and must not be rerun. The Session 39 commissioning result and all prior failed attempts retain their original status.
'''
    (HERE/'REPORT.md').write_text(summary,encoding='utf-8')
    human=f'''# Session 40 — Verified storage cleanup; D: capacity still blocked

Measured {measured["measured_at"]}; Git closeout follows this report.

Removed **{plan['totals']['files']:,} regenerable environment cache files and {plan['totals']['empty_trees']} empty project temporary trees** from C:. The caches contained {clean['logical_bytes']:,} bytes ({gib(clean['logical_bytes'])} GiB); their reported file allocation was {clean['file_allocated_bytes']:,} bytes. Every source survives unchanged. No D: deletion candidate met the evidence/dependency requirements.

| Volume | Observed net free change | Final free capacity |
| --- | ---: | ---: |
| C: | {delta['C']:+,} bytes ({gib(delta['C'])} GiB) | {gib(end['C']['free'])} GiB |
| D: | {delta['D']:+,} bytes ({gib(delta['D'])} GiB) | {gib(end['D']['free'])} GiB |

Combined observed change: {sum(delta.values()):+,} bytes. These full-session observations include audit artifacts and other host activity; they are distinct from the safely removed files. The narrower deletion interval is recorded in the [detailed audit](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-40/REPORT.md). Measurements precede final Git closeout.

D: remains **{gib(shortfall)} GiB short of 50 GiB**. Its 1 MiB exFAT allocation units cause major overhead: the apartment artifacts contain 17.33 GiB but occupy 475.21 GiB in file allocation. Large original runs, failed qualifications, checkpoint histories, repeated-but-referenced staging trees, published robot filesystems, model assets and Git history remain protected. No uncertain candidate was removed.

Full pre-cleanup hashes matched all {hist['files']:,} previously inventoried historical files, and a fresh inventory covered {s39['files']:,} Session 39 files. Post-cleanup retained metadata, critical hashes, all 263 working/frozen source pairs, the unchanged commissioning certificate, cache-source hashes, environment imports, Git connectivity and project process/mount checks passed. The detailed report states the exact verification scope and links the deletion manifest, queue receipts and retained-candidate reasoning.

The assignment ends here. **No preparation helper, v4 creation, model call, Baseline/Maps launch, recovery, comparison or monitor was started.** A later direct instruction is required for any further storage change or experiment preparation. Current release002 and prior experiment states remain as recorded in Session 39.
'''
    (REPO/'agents/Codex/Session Summaries/HumanReport40.md').write_text(human,encoding='utf-8')
    continuity=f'''# Codex continuity — Session 40 storage handoff

**The authorized C:/D: storage audit and verified cleanup are complete. D: remains below the fixed 50 GiB gate. Stop; do not resume preparation, launch, recovery or monitoring automatically.** [HumanReport40](Session%20Summaries/HumanReport40.md) and the [storage report](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-40/REPORT.md) contain the evidence and actual volume observations.

Session 40 pulled main first to c8058506 and followed Randy's October 9 19:08 PDT cleanup-only authority. It removed {plan['totals']['files']} regenerable venv cache files ({clean['logical_bytes']} logical bytes; {clean['file_allocated_bytes']} reported allocated bytes) and {plan['totals']['empty_trees']} empty C: project temp trees. No D: file, original evidence, installed source/dependency, Git history or published robot filesystem was removed. All uncertain/referenced copies were retained. A full 1,208,520-file census covered 31 explicit roots; Linux project data was separately accounted. Large local inventories remain on C: outside Git, hash-bound by session-40/local-artifacts.json; do not mistake them for disposable caches.

At {measured['measured_at']}, before Git closeout, C: free was {end['C']['free']} bytes ({gib(end['C']['free'])} GiB), D: free {end['D']['free']} bytes ({gib(end['D']['free'])} GiB); D: shortfall {shortfall} bytes ({gib(shortfall)} GiB). Full-session volume changes were C: {delta['C']:+} and D: {delta['D']:+} bytes, including audit output and other host writes. Refresh capacity before any later decision. ExFAT uses 1 MiB clusters: the apartment root alone is 17.33 GiB logical / 475.21 GiB file allocation. No safe D: deletion target was established; a future storage migration is a separate human decision.

Full hashes matched the 75-root historical inventory ({hist['files']} files / {hist['bytes']} bytes); Session 39 and published filesystems were freshly hashed. Postcheck verified retained metadata and critical identities; it was not a second full byte rehash. Qualified release002 remains at D:/Dandelion-Apartment-Experiment/engineering/commissioning-session39/release002/frozen_repository, revision APARTMENT-s39-release002. Its manifest SHA-256 remains d7d28df30a01ff7ee11bfa2f8025ccc1499856d3ba6e6e76fabb44735d979d3a; audit003/output/certificate.json remains 49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f. All 263 current/frozen source pairs match; critical checkpoint/schedule hashes, environment imports and Git connectivity passed.

Session 39 freeze001 already failed once before its first official directory copy. Never rerun its preparation/completion helpers. V4 is still absent, no official submission exists and old monitors remain paused. A future separately authorized continuation needs a new preparation-attempt identity, fresh certificate/source/environment/capacity readback, unused pair path, both actual pristine templates and the authenticated original hidden21 schedule, then independent preflight. No prior or pilot learning may enter new guests.

V2 Baseline remains completed at checkpoint 36; v2 Maps hibernated at checkpoint 22. Failed v3 Baseline retains checkpoint 14 and original false retirement receipts; v3 Maps remains pristine. All Session 36–39 failed/passed attempts, including release001 native001 and freeze001, are unchanged. No experiment process or apartment mount was introduced by cleanup. This is storage maintenance, not a scientific result.

Codex is the sole standing agent. Use the project venv with -X utf8 -B, supported chat/work/map tools and shared compute queue. Read the human inbox for later direction. After normal Session 40 Git closeout, any further work belongs to a new Development session.
'''
    (REPO/'agents/Codex/Summary of Only Necessary Context.md').write_text(continuity,encoding='utf-8')
    body=f'''Session 40 storage cleanup is complete. I deleted {plan['totals']['files']:,} regenerable environment cache files ({clean['logical_bytes']:,} logical bytes) and {plan['totals']['empty_trees']} empty project temporary trees on C:. I found no D: candidate that could be deleted without breaking the preservation/dependency requirements, so no D: files were removed.

The observed full-session free-space change was C: {delta['C']:+,} bytes ({gib(delta['C'])} GiB) and D: {delta['D']:+,} bytes ({gib(delta['D'])} GiB), combined {sum(delta.values()):+,} bytes. New free capacities are C: {gib(end['C']['free'])} GiB and D: {gib(end['D']['free'])} GiB. These volume deltas include audit artifacts and other host activity; exact deletion-interval observations and removed allocation are in the report. D: remains {gib(shortfall)} GiB below the unchanged 50 GiB gate. Its 1 MiB exFAT allocation units are the main finding: apartment files hold 17.33 GiB of content but occupy 475.21 GiB in file allocation.

The historical hash baseline, qualified release/certificate, retained-file metadata, critical checkpoint/schedule hashes, surviving cache sources, environment imports, Git connectivity and process/mount checks passed. All original experiment/engineering evidence and uncertain candidates remain intact. No preparation, v4, model call, launch, recovery, comparison or monitoring occurred. I am ending this Development session at the requested storage boundary.

Detailed audit and exact manifests: Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-40/REPORT.md. Human handoff: agents/Codex/Session Summaries/HumanReport40.md.
'''
    (HERE/'handoff-body.md').write_text(body,encoding='utf-8')
    print(json.dumps(measured,indent=2))
if __name__=='__main__':main()
