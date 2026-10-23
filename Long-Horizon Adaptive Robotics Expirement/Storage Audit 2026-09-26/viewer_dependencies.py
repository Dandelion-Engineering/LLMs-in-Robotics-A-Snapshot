"""Read bounded viewer manifests and stat original frames; do not read pixels."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SITE=HERE.parent/'Engineering Investigation 007/site-r4-003'
payload=(SITE/'package-manifest.json').read_bytes()
package=json.loads(payload)
all_refs={};run_rows=[];read_bytes=len(payload)
for trace in package['trace_checks']:
    ref=trace['package']['manifest']
    data=(SITE/ref['href']).read_bytes();read_bytes+=len(data)
    assert len(data)==ref['bytes'] and hashlib.sha256(data).hexdigest()==ref['sha256']
    manifest=json.loads(data);refs={}
    for event in manifest['event_headers']:
        for kind in ('rgb','depth'):
            a=event.get('artifact_refs',{}).get(kind)
            if not a or a.get('state')!='available':continue
            path=(SITE/unquote(a['href'])).resolve()
            assert path.is_relative_to(ROOT)
            assert path.stat().st_size==a['bytes']
            refs[str(path)]=(kind,a['bytes'])
    all_refs.update(refs)
    run_rows.append(dict(run_id=trace['run_id'],events=len(manifest['event_headers']),
                         **{kind:dict(files=sum(k==kind for k,s in refs.values()),bytes=sum(s for k,s in refs.values() if k==kind)) for kind in ('rgb','depth')}))
out=dict(package_manifest_sha256=hashlib.sha256(payload).hexdigest(),metadata_bytes_read=read_bytes,
         missing_files=0,size_mismatches=0,frame_content_hashes_rechecked=False,
         totals={kind:dict(files=sum(k==kind for k,s in all_refs.values()),bytes=sum(s for k,s in all_refs.values() if k==kind)) for kind in ('rgb','depth')},runs=run_rows,
         limitations='Only original RGB/depth refs in available event headers. Excludes package assets, raw source click-throughs, and rebuild inputs. Hashes verify trace manifests, not all image bytes.')
with (HERE/'viewer-dependencies.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
print(json.dumps({k:v for k,v in out.items() if k!='runs'},indent=2))
