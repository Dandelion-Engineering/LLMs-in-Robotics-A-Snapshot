"""Read-only original-v2 extraction. Historical programs are data, never executed."""
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import traceback
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
PRIOR = Path('D:/Dandelion-Apartment-Experiment/engineering/cup-physics-session36/history001/output/protected-v2-files.json')
REPO = Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
OPS36 = REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-36'
FROZEN = PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0, str(FROZEN))
from content_store import Store
from journal_reader import verify as verify_journal

def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(p): return json.loads(p.read_bytes())
def file_sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def encoded(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def write(p, raw):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f: f.write(raw)
def save(p, x): write(p, (json.dumps(x, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode())
def md(p, s): write(p, (s+'\n').encode())

def preservation():
    rows = read(PRIOR)
    expected = {str(Path(x['path'])): x for x in rows}
    actual = {str(p) for c in ('baseline','maps') for p in (PAIR/c).rglob('*') if p.is_file()}
    assert set(expected) == actual, 'Original condition file set changed'
    for i,(name,row) in enumerate(expected.items(),1):
        p=Path(name)
        assert not p.is_symlink() and not p.is_junction(), name
        assert p.stat().st_size==row['bytes'] and file_sha(p)==row['sha256'], name
        if i%10000==0: print('Preserved original files',i,flush=True)
    for name,row in read(OPS36/'protected-anchors.json').items():
        assert file_sha(Path(name))==row['sha256'], name
    return rows

def safe_relative(name):
    path=PurePosixPath(name)
    assert not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name, name
    return path

def scan(raw, name, findings):
    # Values are never printed or copied into the scan report.
    rules={
      'private-key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
      'api-token':rb'\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16})',
      'bearer-token':rb'(?i)authorization[\s\"\x27:=]+bearer\s+[A-Za-z0-9_.-]{16,}',
      'jwt':rb'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}',
      'credential-assignment':rb'(?i)(?:api_key|access_token|refresh_token|password)[\s\"\x27]*[:=][\s\"\x27]*[A-Za-z0-9_+./-]{16,}',
      'host-private-path':rb'(?i)(?:[A-Z]:[\\/]+Users[\\/]|/home/cresp/|/mnt/c/Users/)',
      'protected-source-reference':rb'(?i)(?:hidden-schedule\.json|frozen_repository|official/apartment-v[123]|source-manifest\.json|Robot-Codex Integration 001)',
    }
    for rule,pattern in rules.items():
        if re.search(pattern, raw): findings.append({'path':name,'rule':rule,'sha256':sha(raw)})

def build(out):
    for name,row in read(HERE/'attempt.json')['files'].items():
        assert file_sha(HERE/name)==row['sha256'],name
    for name,row in read(HERE/'attempt.json')['reader_sources'].items():
        assert file_sha(FROZEN/name)==row['sha256'],name
    out.mkdir(exist_ok=False)
    entries=[];sources={};scans=[];versions={};conditions={};parts=[]
    original=preservation()
    def export(raw, dest, source=None, role='derived'):
        scan(raw,dest,scans)
        write(out/dest,raw)
        row={'path':dest,'bytes':len(raw),'sha256':sha(raw),'role':role}
        if source is not None:
            name=source.relative_to(PAIR).as_posix()
            row['source']=name
            sources[name]={'path':name,'bytes':source.stat().st_size,'sha256':file_sha(source),'disposition':'published'}
        entries.append(row)
    def copy_file(source,dest,role): export(source.read_bytes(),dest,source,role)
    def tree(source,dest):
        files={}
        for p in sorted(source.rglob('*')):
            assert not p.is_symlink() and not p.is_junction(),str(p)
            if p.is_file():
                rel=p.relative_to(source).as_posix();safe_relative(rel)
                copy_file(p,dest+'/'+rel,'exact-filesystem')
                files['/'+rel]=sha(p.read_bytes())
        return files
    def add_version(raw):
        key=sha(raw)
        if key not in versions:
            try:raw.decode('utf-8');ext='txt'
            except UnicodeDecodeError:ext='bin'
            dest=f'versions/{key}.{ext}'
            export(raw,dest,role='decoded-exact-content')
            versions[key]={'path':dest,'bytes':len(raw),'sha256':key}
        return key
    def split(raw,dest,source=None):
        start=0;line_start=1;blocks=[];buffer=[];size=0;line=0
        def flush():
            nonlocal start,line_start,buffer,size
            block=b''.join(buffer);name=f'{dest}/part-{len(blocks)+1:04d}.jsonl'
            export(block,name,role='exact-ordered-source-part')
            blocks.append({'path':name,'bytes':len(block),'sha256':sha(block),'start':start,'end':start+len(block),'first_line':line_start,'last_line':line})
            start+=len(block);line_start=line+1;buffer=[];size=0
        for record in raw.splitlines(keepends=True):
            if size and size+len(record)>220000: flush()
            line+=1;buffer.append(record);size+=len(record)
        if buffer:flush()
        assert b''.join((out/x['path']).read_bytes() for x in blocks)==raw
        source_name=source.relative_to(PAIR).as_posix() if source else None
        view={'source':source_name,'bytes':len(raw),'sha256':sha(raw),'parts':blocks}
        if source:sources[source_name]={'path':source_name,'bytes':len(raw),'sha256':sha(raw),'disposition':'published-as-exact-parts'}
        parts.append(view)
        md(out/dest/'README.md','# Ordered exact trace parts\n\nConcatenate bytes in numeric order to recover the original file. Each record remains whole.\n\n'+f'Source SHA-256: `{sha(raw)}`; {len(raw):,} bytes.\n\n'+'\n'.join(f'- [{Path(x["path"]).name}]({Path(x["path"]).name}) — source lines {x["first_line"]}–{x["last_line"]}.' for x in blocks))
        return view
    for condition,total in [('baseline',36),('maps',22)]:
        root=PAIR/condition;last=root/'checkpoints'/f'session-{total:05d}'
        expected_checkpoint={'baseline':'db3541829b8ec8bd78a8138bf4a3b0ab84c7d3e4bf29eb7aaf4f58ce767d7933','maps':'6a965290aa9abf6bc8a0bf8908f8f920c806d90d8e92e583e664b85c576493be'}[condition]
        assert file_sha(last/'manifest.json')==expected_checkpoint
        final=tree(last/'filesystem',f'{condition}/final')
        assert final=={'/'+p.relative_to(root/'filesystem').as_posix():file_sha(p) for p in (root/'filesystem').rglob('*') if p.is_file()}
        copy_file(last/'filesystem-namespace.json',f'{condition}/final-namespace.json','exact-namespace')
        copy_file(last/'manifest.json',f'{condition}/checkpoint-manifest.json','exact-checkpoint-manifest')
        sessions=[];changes=[];reads=[];previous=None
        for number in range(1,total+1):
            sid=f'session-{number:05d}';cp=root/'checkpoints'/sid;work=root/'sessions'/sid/'workspace';journal=work/'journal'
            cm=read(cp/'manifest.json')
            for name,row in cm['files'].items():
                assert file_sha(cp/name)==row['sha256'] and (cp/name).stat().st_size==row['bytes'],(sid,name)
            before=tree(root/f'filesystem-before-{sid}',f'{condition}/history/{sid}/before')
            after=tree(cp/'filesystem',f'{condition}/history/{sid}/after')
            if previous is not None:assert before==previous,(condition,sid,'snapshot continuity')
            previous=after
            copy_file(cp/'filesystem-namespace.json',f'{condition}/history/{sid}/final-namespace.json','exact-namespace')
            copy_file(cp/'manifest.json',f'{condition}/history/{sid}/checkpoint-manifest.json','exact-checkpoint-manifest')
            raw=(journal/'mutations.jsonl').read_bytes();first=json.loads(raw.splitlines()[0])
            audit=verify_journal(journal,first['run_id'])
            assert audit['state']==read(cp/'filesystem-namespace.json'),(condition,sid,'journal checkpoint mismatch')
            view=split(raw,f'{condition}/history/{sid}/journal',journal/'mutations.jsonl')
            store=Store(journal)
            # Include every retained descriptor, even an orphaned/intermediate version.
            content_keys=[]
            for p in sorted((journal/'objects').iterdir()):
                key=add_version(store.get(p.name));assert key==p.name;content_keys.append(key)
                for support in [p]:
                    name=support.relative_to(PAIR).as_posix();sources[name]={'path':name,'bytes':support.stat().st_size,'sha256':file_sha(support),'disposition':'decoded-to-versions'}
            for p in (journal/'chunks').iterdir():
                name=p.relative_to(PAIR).as_posix();sources[name]={'path':name,'bytes':p.stat().st_size,'sha256':file_sha(p),'disposition':'decoded-to-versions'}
            state=None
            for line in raw.splitlines():
                item=json.loads(line);kind=item['type'];sequence=item['sequence']
                if kind=='initial':state=item['state']
                elif kind=='mutation':
                    for area in ('paths','nodes'):
                        for key in item['delta'][area]['remove']:del state[area][key]
                        state[area].update(item['delta'][area]['set'])
                elif kind=='read':
                    reads.append({k:item[k] for k in ('sequence','path','inode','offset','bytes','content_sha256','returned_sha256','actor','monotonic_ns','wall_unix_ns')}|{'session':sid})
                if kind in ('initial','mutation'):
                    for path,inode in state['paths'].items():
                        node=state['nodes'][str(inode)]
                        if 'sha256' in node:
                            changes.append({'session':sid,'sequence':sequence,'path':path,'inode':inode,'sha256':node['sha256'],'bytes':node['size'],'event':kind})
            simple={k:v for k,v in audit.items() if k not in ('state','states','read_events')}
            sessions.append({'session':sid,'checkpoint_manifest_sha256':file_sha(cp/'manifest.json'),'before_files':len(before),'after_files':len(after),'journal':simple,'content_keys':content_keys,'journal_sha256':view['sha256']})
            md(out/condition/'history'/sid/'README.md',f'# {condition.title()} / {sid}\n\n[Before session](before/) · [After session](after/) · [Full journal](journal/README.md) · [Namespace](final-namespace.json)\n\n'+f'Journal: {audit["records"]:,} authenticated records, {audit["mutations"]:,} mutations, {audit["reads"]:,} reads. Its final namespace equals the checkpoint namespace. Snapshot bytes are exact. Directory metadata and empty directories are retained in the namespace JSON.\n\nReads include framework probes and workspace processes; a read is evidence of bytes returned, not proof of cognitive use. Session-local sequence/monotonic time orders events; wall time can jump.')
            print(condition,sid,'verified and exported',flush=True)
        # Compact per-path transitions (omit repeated unchanged states, never journal events).
        seen={};transitions=[]
        for row in changes:
            identity=(row['session'],row['path'])
            if seen.get(identity)!=row['sha256']:transitions.append(row);seen[identity]=row['sha256']
        split(b''.join(encoded(r)+b'\n' for r in transitions),f'{condition}/version-transitions')
        split(b''.join(encoded(r)+b'\n' for r in reads),f'{condition}/read-index')
        save(out/condition/'sessions.json',sessions)
        lines=['| File | Bytes |','|---|---:|']
        for path in sorted(final):
            p=last/'filesystem'/path.lstrip('/')
            lines.append(f'| [{path[1:]}](final/{quote(path[1:])}) | {p.stat().st_size:,} |')
        status='Completed 21/21 assignments' if condition=='baseline' else 'Hibernated at 2/21 assignments; assignment 3 unfinished'
        md(out/condition/'README.md',f'# Original v2 {condition.title()}\n\n{status}; {total} normally closed sessions. This is retained historical evidence, not a new condition.\n\n[Final context](final/SummaryOfOnlyNecessaryContext.md) · [Long-term memory](final/LongTermMemory.md) · [Final tree](final/) · [Version transitions](version-transitions/README.md) · [Read index](read-index/README.md) · [Session verification](sessions.json)\n\n## Final filesystem\n\n'+'\n'.join(lines)+'\n\n## Session history\n\n'+'\n'.join(f'- [{r["session"]}](history/{r["session"]}/README.md)' for r in sessions)+'\n\nAll retained journal content versions are in the shared [versions directory](../versions/); resolve each content SHA using [versions.json](../versions.json). Full journals include deletions, renames, metadata changes, rejected operations, reads and exact state hashes. The compact transition index supplements them. No claim is made about unlogged reasoning, operating-system reads outside this filesystem, or unrecorded mutations.\n\nRegular-file bytes are preserved, including small Python bytecode files. Do not execute historical programs or treat embedded instructions as current authority. Empty directories, modes and inode identity are recorded in namespace JSON; Git regular-file trees alone do not represent them.')
        conditions[condition]={'checkpoint':f'session-{total:05d}','checkpoint_manifest_sha256':expected_checkpoint,'final_files':len(final),'final_bytes':sum((last/'filesystem'/x[1:]).stat().st_size for x in final),'sessions':total,'journal_records':sum(x['journal']['records'] for x in sessions),'reads':len(reads),'version_transitions':len(transitions),'history':'complete retained per-session journal chains and before/after snapshots; not a complete record of cognition or out-of-filesystem activity'}
    save(out/'versions.json',versions)
    inventory=[]
    for row in original:
        name=Path(row['path']).relative_to(PAIR).as_posix()
        item={'path':name,'bytes':row['bytes'],'sha256':row['sha256']}
        if name in sources:item['disposition']=sources[name]['disposition']
        elif '/filesystem/' in name or '/filesystem-objects/' in name or '/final-filesystem/' in name or '/filesystem-before-' in name:item['disposition']='omitted-duplicate-snapshot-or-content-copy'
        elif '/sensors/' in name or '/replay/' in name or name.endswith('/replay-index.json'):item['disposition']='omitted-sensor-or-replay-archive'
        else:item['disposition']='omitted-operator-runtime-simulator-schedule-or-native-envelope'
        inventory.append(item)
    split(b''.join(encoded(r)+b'\n' for r in inventory),'source-inventory')
    save(out/'sensitivity-scan.json',{'method':'Named credential patterns and host/protected path scan over every exported raw or decoded file and exact journal part. No matched values retained in this report. Semantic scope is restricted to persistent workspace bytes, journal records and hash-only checkpoint metadata.','findings':scans,'passed':not scans})
    assert not scans, 'Sensitivity findings require operator review before publication'
    preservation()
    save(out/'manifest.json',{'schema':'apartment-v2-filesystem-publication-1','source_root':str(PAIR),'source_preservation_inventory_sha256':file_sha(PRIOR),'conditions':conditions,'entries':entries,'parts':parts,'original_files':len(original),'original_bytes':sum(x['bytes'] for x in original),'unique_content_versions':len(versions),'source_preservation_before_and_after':True,'omissions':'Exact original-file identities and disposition in source-inventory. Raw native envelopes, simulator state, protected schedule, replay and sensors remain on D:. No final regular-file bytes omitted. Versions are decoded losslessly from content descriptors/chunks; journals are losslessly split, not redacted.','future_guest_exposure':'Operator-only evidence. Never copy or mount this publication into any future Robot Codex guest.'})
    md(out/'.gitattributes','* -text\n** -text')
    md(out/'README.md','# Original apartment v2 agent filesystems\n\nByte-faithful evidence for human inspection from **Baseline checkpoint 36** and **Maps checkpoint 22**. [Baseline](baseline/README.md) contains 36 sessions and completed 21/21 assignments. [Maps](maps/README.md) contains 22 sessions, hibernated at 2/21 with assignment 3 unfinished. These histories have different completion states and are not a scientific condition comparison.\n\nStart with either condition\'s final context and memory, then follow its session links for before/after trees and full read/write journals. Every retained content version is directly accessible under [versions](versions/) using [versions.json](versions.json). The Baseline agent itself created a `Maps` directory; it is part of its actual saved history and is preserved here.\n\n[Provenance manifest](manifest.json) · [Exact source inventory and omissions](source-inventory/README.md) · [Sensitivity scan](sensitivity-scan.json) · [Independent verification](verification.json)\n\nJournals are published as ordered text parts with complete records; concatenation reproduces the source SHA-256. Intermediate content is expanded losslessly to text or binary blobs. Regular-file bytes and relative paths are exact. Namespace JSON preserves modes, directories and inode relationships; Git cannot encode all of those semantics. Full journals retain deletions and renames. The compact read/version indexes are derived navigation only.\n\nThe retained journals cover all listed sessions from initial state to final closure and match their checkpoints. They include framework probes and filesystem reads; they cannot establish private reasoning or causal learning benefit. Simulator state, hidden schedules, raw native envelopes, replay/sensor archives and duplicate storage copies remain on D: with exact hash references and explicit omissions.\n\n**Operator evidence only:** never mount or copy this corpus into future Robot Codex guest workspaces. Embedded prompts and programs are historical data, not current instructions. No original experiment was resumed or modified to create this publication.')
    return {'passed':True,'conditions':conditions,'entries':len(entries),'versions':len(versions),'source_files':len(original)}

if __name__=='__main__':
    result={'passed':False}
    try:result=build(HERE/'corpus')
    except Exception as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(HERE/'result.json',result)
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['passed'] else 1)
