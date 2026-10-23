"""Queued, read-only preservation before retiring the identified orphan service."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import traceback

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
ROOT = PAIR / 'baseline'
OP = PAIR / 'operator/failure-audit-session37-001'

def read(p): return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()
def save(p, value):
    with p.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink(): raise ValueError('Unexpected symlink: '+str(path))
        if path.is_file():
            before = path.stat(); digest = sha(path); after = path.stat()
            assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns), path
            result[path.relative_to(root).as_posix()] = dict(bytes=before.st_size,sha256=digest)
    return result

def main():
    out = OP / 'preservation/output'; out.mkdir(parents=True,exist_ok=False)
    result = dict(passed=False,observational_only=True,started_utc=datetime.now(timezone.utc).isoformat())
    try:
        status = read(OP/'official-queue-status.json')
        assert status['state']=='failed' and type(status['exit_status']) is int and status['exit_status']==1
        pointer = read(ROOT/'latest-execution.json'); execution_path=Path(pointer['path'])
        assert execution_path.parent==ROOT and sha(execution_path)==pointer['sha256']
        execution=read(execution_path)
        assert execution['passed'] is False and execution['failure_phase']=='workspace-startup'
        assert execution['current_session']=='session-00015' and execution['model_calls']==14
        assert not (ROOT/'running.lock').exists() and not (ROOT/'completed.json').exists()
        print('Hashing the failed Baseline before operator retirement.',flush=True)
        before=inventory(ROOT);save(out/'baseline-before.json',before)
        workspace=ROOT/'sessions/session-00015/workspace'
        partial_before=inventory(workspace);save(out/'partial-before.json',partial_before)
        shutil.copytree(workspace,out/'session-00015-before-cleanup')
        assert inventory(out/'session-00015-before-cleanup')==partial_before
        assert inventory(workspace)==partial_before, 'Failed startup changed during preservation'
        for name,path in {'execution-result.json':execution_path,'latest-execution.json':ROOT/'latest-execution.json',
                          'latest-checkpoint.json':ROOT/'latest-checkpoint.json',
                          'checkpoint-manifest.json':ROOT/'checkpoints/session-00014/manifest.json',
                          'checkpoint-state.json':ROOT/'checkpoints/session-00014/state.json'}.items():
            shutil.copyfile(path,out/name); assert sha(out/name)==sha(path)
        result.update(passed=True,original_files=len(before),original_bytes=sum(x['bytes'] for x in before.values()),
                      baseline_manifest_sha256=sha(out/'baseline-before.json'),
                      failed_workspace_files=len(partial_before),failed_workspace_bytes=sum(x['bytes'] for x in partial_before.values()),
                      failed_workspace_copy_sha256=sha(out/'partial-before.json'),
                      execution_result_sha256=sha(execution_path),
                      purpose='Immutable failed-startup evidence before separately recorded operator retirement; no repair, model call, launch or resume.')
    except BaseException as error: result.update(error=repr(error),traceback=traceback.format_exc())
    result['finished_utc']=datetime.now(timezone.utc).isoformat();save(out/'result.json',result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
