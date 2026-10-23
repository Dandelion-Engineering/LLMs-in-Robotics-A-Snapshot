"""Closeout-only preservation audit. Cannot commission, certify or launch."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
OPS=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-36'
def read(p):return json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
 out=HERE/'output';out.mkdir(exist_ok=False);r=dict(passed=False,scope='Original evidence preservation only; failed commissioning is not retried',checks={})
 try:
  for n,v in read(HERE/'manifest.json')['files'].items():assert sha(HERE/n)==v['sha256']
  rows=read(ROOT/'history001/output/protected-v2-files.json');expected={x['path']:x for x in rows}
  actual={str(p) for c in ['baseline','maps'] for p in (PAIR/c).rglob('*') if p.is_file()}
  assert actual==set(expected)
  for i,row in enumerate(rows,1):
   p=Path(row['path']);assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],str(p)
   if i%10000==0:print('Verified original files',i,flush=True)
  r['checks']['all_original_v2_file_bytes_unchanged']=True
  for n,v in read(OPS/'protected-anchors.json').items():assert sha(Path(n))==v['sha256'],n
  r['checks']['v1_v2_pair_anchors_and_checkpoint_identities_unchanged']=True
  frozen=PAIR/'frozen_repository';manifest=read(frozen/'source-manifest.json')
  actual={p.relative_to(frozen).as_posix() for p in frozen.rglob('*') if p.is_file() and p.name!='source-manifest.json'}
  assert actual==set(manifest)
  for n,v in manifest.items():assert sha(frozen/n)==v['sha256'],n
  r['checks']['original_frozen_apparatus_unchanged']=True
  assert not (PAIR.parent/'apartment-v3').exists()
  assert not any((PAIR/c/'running.lock').exists() for c in ['baseline','maps'])
  assert read(PAIR/'baseline/completed.json')['assignments']==21
  assert read(PAIR/'maps/latest-checkpoint.json')['session']==22
  r['checks']['no_replacement_pair_or_original_runtime_lock']=True
  r.update(passed=True,protected_files=len(rows),protected_bytes=sum(x['bytes'] for x in rows),frozen_source_files=len(manifest),
   original_maps_checkpoint_sha256=sha(PAIR/'maps/checkpoints/session-00022/manifest.json'),original_baseline_checkpoint_sha256=sha(PAIR/'baseline/checkpoints/session-00036/manifest.json'),
   commissioning_passed=False,official_launched=False)
 except Exception as e:r.update(error=repr(e),traceback=traceback.format_exc())
 save(out/'result.json',r);print(json.dumps(r),flush=True)
 return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
