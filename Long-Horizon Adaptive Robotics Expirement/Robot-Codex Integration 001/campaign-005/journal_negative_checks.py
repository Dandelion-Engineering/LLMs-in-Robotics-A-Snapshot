"""Linux protected fault fixtures; no workspace mount or model invocation."""
import errno
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from journal_fs import JournalFS,encoded,digest
from verify_journal import verify

def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);checks={}
    identity={'run_id':'fault-fixture','session_id':'fault-session','source_revision':'deterministic-fault-fixture'}
    fs=JournalFS(root/'original',identity,{'notes':None})
    fi=SimpleNamespace(fh=None,direct_io=0,keep_cache=0)
    fs.create('/notes/item',0o600,fi);fs.write('/notes/item',b'abc',0,fi)
    for name in ('space','file'):
        quota=JournalFS(root/('quota-'+name),identity,{'item':'abc'},cap=100)
        original=digest(encoded(quota.state))
        try:quota.truncate('/item',101 if name=='space' else 16*1024**2+1)
        except OSError as e:checks[name+'_quota_stops_without_state_change']=e.errno in (errno.ENOSPC,errno.EFBIG) and quota.stopped and digest(encoded(quota.state))==original
        quota.destroy(None)
    try:fs.mknod('/notes/device',0o600,0)
    except OSError as e:checks['special_file_denied']=e.errno==errno.ENOTSUP
    fs.link('/notes/alias','/notes/item');fs.rename('/notes/item','/notes/alias')
    checks['same_inode_rename_preserves_both_names']=set(fs.state['paths'])>={'/notes/item','/notes/alias'}
    fs.unlink('/notes/item');fs.unlink('/notes/alias');fs.write('/notes/item',b'!',3,fi)
    checks['open_unlinked_handle_exact']=fs.read('/notes/item',10,0,fi)==b'abc!'
    fs.release('/notes/item',fi);fs.destroy(None)
    checks['valid_replay']=verify(root/'original','fault-fixture')['passed']
    for case in ('wrong-run','missing-record','corrupt-record','missing-final','corrupt-object'):
        target=root/case;shutil.copytree(root/'original',target)
        ledger=target/'mutations.jsonl';lines=ledger.read_bytes().splitlines(keepends=True)
        if case=='missing-record':lines.pop(2);ledger.write_bytes(b''.join(lines))
        if case=='corrupt-record':lines[1]=lines[1].replace(b'"mutation"',b'"mutatioX"');ledger.write_bytes(b''.join(lines))
        if case=='missing-final':ledger.write_bytes(b''.join(lines[:-1]))
        if case=='corrupt-object':(target/'objects'/digest(b'abc')).write_bytes(b'bad')
        try:verify(target,'wrong-identity' if case=='wrong-run' else 'fault-fixture')
        except (AssertionError,KeyError,ValueError,OSError):checks[case+'_detected']=True
        else:checks[case+'_detected']=False
    # A journal write failure is terminal: never acknowledge later mutation.
    broken=JournalFS(root/'io-failure',identity,{'notes':None})
    broken.stream.close()
    try:broken.mkdir('/notes/new',0o700)
    except Exception:pass
    checks['journal_io_failure_stops']=broken.stopped
    try:broken.mkdir('/notes/later',0o700)
    except OSError as e:checks['later_write_refused']=e.errno==errno.EIO and '/notes/later' not in broken.state['paths']
    result={'passed':all(checks.values()),'checks':checks,'model_calls':0}
    (root/'receipt.json').write_text(json.dumps(result,sort_keys=True)+'\n');return result

if __name__=='__main__':
    import sys
    r=run(sys.argv[1]);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
