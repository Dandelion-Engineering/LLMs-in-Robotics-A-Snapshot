"""Linux diagnostic wrapper, profiles restore only; does not alter persisted data."""
import cProfile
import json
from pathlib import Path
import pstats
import sys
import time

source=Path(sys.argv.pop(1));profile_output=Path(sys.argv.pop(1))
sys.path.insert(0,str(source))
import journal_service
repo=Path(sys.argv[sys.argv.index('--repo')+1])
sys.path.insert(0,str(repo/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-005'))
import journal_fs
original=journal_fs.JournalFS.__init__
def measured(self,*args,**kwargs):
    begin=time.monotonic_ns();profile=cProfile.Profile();profile.enable()
    try:return original(self,*args,**kwargs)
    finally:
        profile.disable();elapsed=time.monotonic_ns()-begin
        profile.dump_stats(str(profile_output.with_suffix('.pstats')))
        stats=pstats.Stats(profile)
        rows=[dict(file=k[0],line=k[1],function=k[2],primitive_calls=v[0],calls=v[1],self_s=v[2],cumulative_s=v[3]) for k,v in stats.stats.items()]
        profile_output.write_text(json.dumps(dict(restore_elapsed_ns=elapsed,top=sorted(rows,key=lambda x:x['cumulative_s'],reverse=True)[:80])))
journal_fs.JournalFS.__init__=measured
journal_service.main()
