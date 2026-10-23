"""Additive, fail-closed r4 image retirement. No recursive deletion is used.

Manifests use deterministic gzip JSONL to version millions of exact paths without
placing expanded bulk records in Git. Original evidence outside exact frame
paths is never mutated. Each command writes a new immutable output generation.
"""
from __future__ import annotations
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import gzip
import hashlib
import functools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parent
R4 = EXP / 'Evidence/releases/batch01-eval-r4'
ATTEMPTS = R4 / 'attempts'
PATTERN = re.compile(r'^(\d{6})(-depth\.npz|\.png)$')
POLICY = 'r4-selected-imagery-retention-001'
GATES = {'no_writers','audit_consistent','retained_dependencies','retained_hashes',
         'staged_investigation','explorer','aggregate','diagnostics_continuity',
         'windows_complete','reconciled_bytes'}

def now(): return dt.datetime.now().astimezone().isoformat()
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()
def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=False); f.write('\n');f.flush();os.fsync(f.fileno())
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        for line in f:
            if line.strip(): yield json.loads(line)
class Writer:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.raw = path.open('xb')
        self.f = gzip.GzipFile(filename='', mode='wb', fileobj=self.raw, mtime=0)
        self.count = self.bytes = 0
    def put(self, row):
        self.f.write((json.dumps(row, separators=(',', ':'), ensure_ascii=False)+'\n').encode())
        self.count += 1; self.bytes += row.get('logical_bytes', 0)
    def close(self): self.f.close(); self.raw.close()

@functools.lru_cache(maxsize=2048)
def checked_directory(directory, root):
    """Cache invariant ancestor checks; each leaf still resolves and lstats."""
    if directory.resolve(strict=True)!=directory:raise ValueError('directory path alias')
    for ancestor in [directory, *directory.parents]:
        if ancestor==root.parent:break
        if getattr(ancestor.lstat(),'st_file_attributes',0)&0x400:raise ValueError('reparse directory')
    return directory

def safe_frame(relative, check_exists=True):
    """Resolve and constrain every actual unlink to an exact r4 frames leaf."""
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or '\\' in relative: raise ValueError('unsafe path')
    absolute = ROOT / p
    resolved = absolute.resolve(strict=check_exists)
    base=checked_directory(ATTEMPTS,ROOT)
    if not resolved.is_relative_to(base): raise ValueError('outside r4 attempts')
    parts = resolved.relative_to(base).parts
    if len(parts) != 4 or parts[1:3] != ('evidence', 'frames') or not PATTERN.fullmatch(parts[-1]):
        raise ValueError('not exact approved RGB/depth leaf')
    if resolved != absolute: raise ValueError('path alias')
    checked_directory(absolute.parent,ROOT)
    try:
        leaf=absolute.lstat()
        if getattr(leaf,'st_file_attributes',0)&0x410:raise ValueError('reparse or directory leaf')
    except FileNotFoundError:
        if check_exists:raise
    return absolute

def census(args):
    out = HERE/'records'/args.name
    out.mkdir(parents=True, exist_ok=False)
    catalog = HERE/'manifests'/f'{args.name}-frame-catalog.jsonl.gz'
    writer = Writer(catalog)
    start = now(); before = shutil.disk_usage(ROOT.anchor)._asdict()
    counts = collections.defaultdict(lambda: [0, 0]); protected = []
    errors = []; skipped = []; stack = [ROOT]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for e in entries:
                    p = Path(e.path); rel = p.relative_to(ROOT).as_posix()
                    try:
                        st = e.stat(follow_symlinks=False)
                        if getattr(st, 'st_file_attributes', 0) & 0x400:
                            skipped.append(rel); continue
                        if e.is_dir(follow_symlinks=False): stack.append(p); continue
                        if not e.is_file(follow_symlinks=False): skipped.append(rel); continue
                        area = ('/'.join(p.relative_to(ROOT).parts[:2]) if p.is_relative_to(EXP) else p.relative_to(ROOT).parts[0])
                        for key in {'.', area}:
                            counts[key][0] += 1; counts[key][1] += st.st_size
                        if not p.is_relative_to(R4): continue
                        counts['r4'][0] += 1; counts['r4'][1] += st.st_size
                        r = p.relative_to(ATTEMPTS) if p.is_relative_to(ATTEMPTS) else None
                        match = PATTERN.fullmatch(p.name) if r and len(r.parts)==4 and r.parts[1:3]==('evidence','frames') else None
                        if match:
                            row=dict(path=rel,run_id=r.parts[0],artifact_type='depth' if match[2].startswith('-') else 'rgb',logical_bytes=st.st_size,frame_id=int(match[1]),mtime_ns=st.st_mtime_ns)
                            writer.put(row)
                            counts['r4_frames'][0]+=1; counts['r4_frames'][1]+=st.st_size
                        else:
                            if '/frames/' in rel: raise ValueError('unexpected frame leaf')
                            protected.append(dict(path=rel,logical_bytes=st.st_size,mtime_ns=st.st_mtime_ns))
                    except Exception as exc: errors.append([rel,repr(exc)])
        except OSError as exc: errors.append([str(directory), repr(exc)])
    writer.close()
    emit(out/'protected-metadata.json', protected)
    result=dict(schema='retention-census-1',started=start,finished=now(),root=str(ROOT),counts=dict(counts),disk_before=before,disk_after=shutil.disk_usage(ROOT.anchor)._asdict(),errors=errors,skipped=skipped,catalog=dict(path=catalog.relative_to(ROOT).as_posix(),sha256=sha(catalog),files=writer.count,logical_bytes=writer.bytes),limitations='Logical pathname totals, not physical allocation. Concurrent implementation outputs may be included. No reparse traversal. Original frame contents not read.')
    emit(out/'summary.json',result); print(json.dumps(result,indent=2))
    if errors or skipped: raise RuntimeError('census incomplete')

def partition(args):
    source = read(HERE/'records'/args.census/'summary.json')
    assert not source['errors'] and not source['skipped']
    catalog = ROOT/source['catalog']['path']; assert sha(catalog)==source['catalog']['sha256']
    needed = {}
    for row in rows(Path(args.required)):
        p = row['path']
        if p in needed: raise ValueError(f'duplicate required input {p}')
        needed[p] = row
    retained = Writer(HERE/'manifests'/f'{args.name}-retained.jsonl.gz')
    deleted = Writer(HERE/'manifests'/f'{args.name}-deletion.jsonl.gz')
    seen = set(); hash_bytes = 0
    for row in rows(catalog):
        if row['path'] in needed:
            p = safe_frame(row['path']); st=p.stat()
            if st.st_size != row['logical_bytes'] or st.st_mtime_ns != row['mtime_ns']: raise ValueError('changed retained input')
            row.update(needed[row['path']]); row['sha256']=sha(p)
            if row.get('expected_sha256') and row['sha256']!=row['expected_sha256']:
                raise ValueError('Retained content differs from historical authenticated artifact hash: '+row['path'])
            st2=p.stat()
            if (st2.st_size,st2.st_mtime_ns)!=(st.st_size,st.st_mtime_ns): raise ValueError('changed during hash')
            row['policy']=POLICY; retained.put(row); seen.add(row['path']); hash_bytes+=st.st_size
        else:
            row['policy']=POLICY; row['reason']='Outside current dependencies and bounded outcome-selected diagnostic windows; intentional retirement of arbitrary pixel/depth reassessment'
            deleted.put(row)
    retained.close(); deleted.close()
    if seen != set(needed): raise ValueError(f'{len(set(needed)-seen)} required paths absent from census')
    assert retained.count+deleted.count==source['catalog']['files']
    assert retained.bytes+deleted.bytes==source['catalog']['logical_bytes']
    manifests={}
    for kind,w in [('retained',retained),('deletion',deleted)]:
        p=HERE/'manifests'/f'{args.name}-{kind}.jsonl.gz'
        manifests[kind]=dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),files=w.count,logical_bytes=w.bytes)
    emit(HERE/'records'/f'{args.name}-partition.json', dict(schema='retention-partition-1',policy=POLICY,created=now(),census=args.census,required_input_sha256=sha(args.required),manifests=manifests,retained_content_bytes_hashed=hash_bytes))
    print(json.dumps(manifests,indent=2))

def validate(args):
    part=read(HERE/'records'/f'{args.name}-partition.json')
    counts={}; errors=[]
    for kind,ref in part['manifests'].items():
        mf=ROOT/ref['path']; assert sha(mf)==ref['sha256']
        n=b=0
        def check_row(row):
            try:
                p=safe_frame(row['path'],check_exists=not(args.after and kind=='deletion'))
                if args.after and kind=='deletion':
                    if p.exists(): raise ValueError('retired file still present')
                else:
                    st=p.stat()
                    if (st.st_size,st.st_mtime_ns)!=(row['logical_bytes'],row['mtime_ns']): raise ValueError('identity mismatch')
                    if kind=='retained' and sha(p)!=row['sha256']: raise ValueError('retained SHA mismatch')
                return row['logical_bytes'],None
            except Exception as exc:
                return 0,[row['path'],repr(exc)]
        # Read-only verification is bounded and parallel. Every row still gets
        # the same path resolution, identity and content checks. map preserves
        # manifest order. Actual unlink remains serial in delete().
        with ThreadPoolExecutor(max_workers=8) as pool:
            batch=[]
            def check_batch(batch):
                nonlocal n,b
                for size,error in pool.map(check_row,batch):
                    if error: errors.append(error)
                    else: n+=1;b+=size
                if len(errors)>100: raise RuntimeError(errors)
            for row in rows(mf):
                batch.append(row)
                if len(batch)==256: check_batch(batch);batch=[]
            if batch: check_batch(batch)
        assert (n,b)==(ref['files'],ref['logical_bytes']) if not errors else True
        counts[kind]=dict(files=n,logical_bytes=b)
    protected=read(HERE/'records'/part['census']/'protected-metadata.json')
    for row in protected:
        try:
            st=(ROOT/row['path']).stat()
            if (st.st_size,st.st_mtime_ns)!=(row['logical_bytes'],row['mtime_ns']): raise ValueError('protected metadata changed')
        except Exception as exc: errors.append([row['path'],repr(exc)])
    result=dict(created=now(),phase='post' if args.after else 'pre',status='passed' if not errors else 'failed',partition_sha256=sha(HERE/'records'/f'{args.name}-partition.json'),counts=counts,protected_nonframe_metadata_checked=len(protected),errors=errors)
    emit(HERE/'records'/f'{args.name}-{args.phase}-validation.json',result);print(json.dumps(result,indent=2))
    if errors: raise RuntimeError('validation failed')

def delete(args):
    part_path=HERE/'records'/f'{args.name}-partition.json';part=read(part_path)
    gate=read(args.gate)
    if gate.get('status')!='passed' or gate.get('partition_sha256')!=sha(part_path): raise ValueError('gate does not authenticate partition')
    if gate.get('deletion_manifest_sha256')!=part['manifests']['deletion']['sha256']:raise ValueError('gate deletion mismatch')
    if set(gate.get('checks',{}))!=GATES or any(value is not True for value in gate['checks'].values()):raise ValueError('all pre-deletion gates must pass')
    if not gate.get('evidence_refs'):raise ValueError('gate lacks authenticated supporting records')
    for record in gate['evidence_refs']:
        p=(ROOT/record['path']).resolve()
        if not p.is_relative_to(HERE.resolve()) or sha(p)!=record['sha256']:raise ValueError('gate supporting record changed')
        if record.get('kind')=='official_queue_receipt':
            receipt_value=read(p)
            if receipt_value.get('state')!='succeeded' or receipt_value.get('exit_status')!=0:raise ValueError('gate queue job did not succeed')
    ref=part['manifests']['deletion']; manifest=ROOT/ref['path']
    if sha(manifest)!=ref['sha256']:raise ValueError('manifest changed')
    receipts=HERE/'records'/f'{args.name}-deletion-receipts';receipts.mkdir(exist_ok=False)
    before=shutil.disk_usage(ROOT.anchor)._asdict();start=now();n=b=0
    # Every batch receipt names the exact contiguous immutable-manifest ordinals.
    # The write-ahead file lets interruption be reconciled without guessing paths.
    batch=[];batch_size=2000;ordinal=0
    def commit_batch(batch):
        nonlocal n,b
        checked_directory.cache_clear()
        index=n//batch_size; first=n
        intent=receipts/f'{index:05d}-intent.json'
        emit(intent,dict(manifest_sha256=ref['sha256'],first_ordinal=first,count=len(batch),logical_bytes=sum(r['logical_bytes'] for r in batch),created=now()))
        removed=[]
        try:
            for row in batch:
                p=safe_frame(row['path']);st=p.stat()
                if (st.st_size,st.st_mtime_ns)!=(row['logical_bytes'],row['mtime_ns']):raise ValueError(f'identity mismatch {p}')
                p.unlink();removed.append(row['path']);n+=1;b+=row['logical_bytes']
        except Exception:
            emit(receipts/f'{index:05d}-failure.json',dict(removed=removed,created=now()));raise
        emit(receipts/f'{index:05d}-complete.json',dict(manifest_sha256=ref['sha256'],first_ordinal=first,count=len(batch),logical_bytes=sum(r['logical_bytes'] for r in batch),removed_paths_sha256=hashlib.sha256(('\n'.join(removed)+'\n').encode()).hexdigest(),finished=now()))
        if index%25==0: print(json.dumps(dict(removed_files=n,removed_logical_bytes=b)),flush=True)
    for row in rows(manifest):
        batch.append(row)
        if len(batch)==batch_size:commit_batch(batch);batch=[]
    if batch:commit_batch(batch)
    assert (n,b)==(ref['files'],ref['logical_bytes'])
    after=shutil.disk_usage(ROOT.anchor)._asdict()
    emit(HERE/'records'/f'{args.name}-deletion-complete.json',dict(status='completed',policy=POLICY,started=start,finished=now(),manifest_sha256=ref['sha256'],files=n,logical_bytes=b,disk_before=before,disk_after=after,observed_free_space_increase_bytes=after['free']-before['free'],limitations='Volume free-space delta includes unrelated activity and metadata/allocation effects; logical retired bytes are exact.'))

def availability(args):
    rel=Path(args.path).as_posix();part=read(HERE/'records'/f'{args.name}-partition.json')
    for kind,ref in part['manifests'].items():
        if sha(ROOT/ref['path'])!=ref['sha256']:raise ValueError('availability manifest changed')
        for row in rows(ROOT/ref['path']):
            if row['path']==rel:
                if kind=='retained':state='available' if (ROOT/rel).exists() else 'corrupted_or_missing'
                elif (ROOT/rel).exists():state='proposed_retirement_present'
                else:
                    completion=HERE/'records'/f'{args.name}-deletion-complete.json'
                    receipt=read(completion) if completion.exists() else {}
                    state='retired_by_policy_unavailable' if receipt.get('status')=='completed' and receipt.get('manifest_sha256')==ref['sha256'] and receipt.get('files')==ref['files'] else 'missing_without_completed_retirement_receipt'
                print(json.dumps(dict(state=state,policy=POLICY,manifest_sha256=ref['sha256'],artifact=row),indent=2));return
    raise ValueError('outside policy manifest')

def receipt(args):
    queue=ROOT.parent/'tools/compute_queue/compute_queue.py'
    raw=subprocess.check_output([sys.executable,'-X','utf8','-B',str(queue),'status',args.job])
    result=json.loads(raw)
    if result.get('state')!='succeeded' or result.get('exit_status')!=0:
        raise ValueError('Queue outputs are not authenticated successful: '+json.dumps(result))
    emit(HERE/'records'/f'queue-{args.job}.json',result)
    print(json.dumps(dict(id=result['id'],state=result['state'],exit_status=result['exit_status'])))

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('census');p.add_argument('--name',required=True)
    p=sub.add_parser('partition');p.add_argument('--name',required=True);p.add_argument('--census',required=True);p.add_argument('--required',required=True)
    p=sub.add_parser('validate');p.add_argument('--name',required=True);p.add_argument('--phase',required=True);p.add_argument('--after',action='store_true')
    p=sub.add_parser('delete');p.add_argument('--name',required=True);p.add_argument('--gate',required=True)
    p=sub.add_parser('availability');p.add_argument('--name',required=True);p.add_argument('--path',required=True)
    p=sub.add_parser('receipt');p.add_argument('--job',required=True)
    args=ap.parse_args();globals()[args.command](args)
if __name__=='__main__':main()
