"""Package already staged sources after byte-exact guards; never modify Runtime."""
from pathlib import Path
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent
RUNTIME=HERE.parent.parent/'Runtime'
STAGE=HERE/'development-storage-stage'/'Runtime'
PREFIX='Long-Horizon Adaptive Robotics Expirement/Runtime/'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bases=json.loads((HERE/'development-storage-originals.json').read_text(encoding='utf-8'))
    names=[*bases,'development_storage.py','test_development_storage.py']
    chunks=[];generated={}
    for name in names:
        target=RUNTIME/name
        if name in bases:
            if sha(target)!=bases[name]['sha256']:
                raise ValueError('Runtime changed; do not generate/apply stale patch: '+name)
            before=target.read_text(encoding='utf-8')
        else:
            if target.exists():raise ValueError('Proposed new Runtime file already exists: '+name)
            before=''
        after=(STAGE/name).read_text(encoding='utf-8');compile(after,name,'exec')
        generated[name]=sha(STAGE/name)
        chunks.append('diff --git '+json.dumps('a/'+PREFIX+name)+' '+json.dumps('b/'+PREFIX+name)+'\n')
        if name not in bases:chunks.append('new file mode 100644\n')
        chunks.extend(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),
            fromfile='a/'+PREFIX+name if name in bases else '/dev/null',tofile='b/'+PREFIX+name))
    output=HERE/'development_storage.patch'
    output.write_text(''.join(chunks),encoding='utf-8',newline='\n')
    manifest={'schema_version':'unapplied-development-storage-patch-1',
              'status':'unapplied; synthetic tests only; D sandbox and performance unmeasured',
              'original_source_refs':bases,'new_runtime_files':[name for name in names if name not in bases],
              'staged_utf8_sha256':generated,'patch_sha256':sha(output),
              'runtime_sources_modified':False,'physical_runs':False,'queue_calls':False,
              'integration_note':'Require exact original hashes and absent new files before apply; external reader changes belong to Investigation'}
    (HERE/'development-storage-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
