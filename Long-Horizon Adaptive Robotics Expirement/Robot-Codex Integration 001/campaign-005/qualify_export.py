"""Native journal stays protected on C; verify a closed archive on D."""
import argparse
import json
from pathlib import Path
import tarfile
import traceback
from common import HERE,save,sha
from workspace_block import WorkspaceBlock
from archive_location import locate,PUBLIC_EXPORT_ROOT
from verify_journal import verify

def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);b=None
    result={'passed':False,'model_calls':0}
    try:
        run='C004-export-'+out.name
        b=WorkspaceBlock(out/'workspace-block',{'Continuity.md':'Neutral archive qualification.\n'},run,
                         'export-fixture',sha(__file__),archive_root=PUBLIC_EXPORT_ROOT)
        native=b.close();b=None
        archive=locate(out/'workspace-block')
        raw=archive.parent/'readback';raw.mkdir()
        with tarfile.open(archive,'r:gz') as t:t.extractall(raw,filter='data')
        checked=verify(raw/'journal',run)
        assert native['passed'] and checked['passed'] and native['final_state_sha256']==checked['final_state_sha256']
        assert archive.drive.lower()=='d:' and native['records']==checked['records']
        result.update(passed=True,archive=str(archive),archive_sha256=sha(archive),native=native,
                      independent={k:v for k,v in checked.items() if k not in ('state','states','read_events')})
    except Exception as e:result.update(error=str(e),traceback=traceback.format_exc())
    finally:
        if b:
            try:b.close()
            except Exception as e:result['cleanup_error']=str(e)
        save(out/'receipt.json',result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.output))
