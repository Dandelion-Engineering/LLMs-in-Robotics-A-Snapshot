"""Create a compact public upload and verify each archived byte against audited exports."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

REPO=Path(__file__).resolve().parents[2]
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'


def digest(raw): return hashlib.sha256(raw).hexdigest()


def main(source,destination,verification_job):
    if destination.exists() or destination.with_suffix('.manifest.json').exists(): raise ValueError('Fresh archive and manifest required')
    official=json.loads(subprocess.run([sys.executable,'-X','utf8','-B',str(QUEUE),'status',verification_job],check=True,capture_output=True,encoding='utf-8').stdout)
    if official['id']!=verification_job or official['state']!='succeeded' or type(official['exit_status']) is not int or official['exit_status']!=0:
        raise ValueError('Authenticated independent audit success/int0 required')
    if '--output' not in official['argv'] or Path(official['argv'][official['argv'].index('--output')+1]).resolve()!=source.resolve():
        raise ValueError('Audit job belongs to a different derived corpus')
    verification=json.loads((source/'verification.json').read_text('utf-8'))
    if verification['passed'] is not True or len(verification['runs'])!=10: raise ValueError('Ten independent run checks required')
    bound={r['path']:r for r in json.loads((source/'build.json').read_text('utf-8'))['outputs']}
    files=[source/name for name in ('README.md','FORMAT.md','schema.json','index.json','verification.json')]
    files+=sorted(p for p in (source/'runs').rglob('*') if p.is_file())
    entries=[]
    for p in files:
        name=p.relative_to(source).as_posix();raw=p.read_bytes()
        if p.is_symlink() or '..' in Path(name).parts: raise ValueError('Unexpected linked/traversing export')
        if name!='verification.json' and (name not in bound or digest(raw)!=bound[name]['sha256'] or len(raw)!=bound[name]['bytes']): raise ValueError('Audited output changed before packaging')
        entries.append({'path':name,'sha256':digest(raw),'bytes':len(raw)})
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in files: archive.write(p,p.relative_to(source).as_posix())
    expected={r['path']:r for r in entries}
    with zipfile.ZipFile(destination) as archive:
        if len(archive.infolist())!=len(expected) or set(archive.namelist())!=set(expected): raise ValueError('Archive scope/content inventory mismatch')
        if archive.testzip() is not None: raise ValueError('ZIP CRC check failed')
        for info in archive.infolist():
            raw=archive.read(info);r=expected[info.filename]
            if digest(raw)!=r['sha256'] or len(raw)!=r['bytes']: raise ValueError('Archive bytes differ from audited originals')
    # Guard original sources again after the only material transformation, compression.
    guards=json.loads((source/'guards.json').read_text('utf-8'))['inputs']
    for g in guards:
        raw=Path(g['path']).read_bytes()
        if digest(raw)!=g['sha256'] or len(raw)!=g['bytes']: raise ValueError('Original evidence changed during archive creation')
    raw=destination.read_bytes()
    receipt={'schema':'behavioral-evidence-portable-archive-1','passed':True,'archive':destination.name,
        'sha256':digest(raw),'bytes':len(raw),'uncompressed_public_bytes':sum(r['bytes'] for r in entries),
        'entries':entries,'verification_job':official,'verification_sha256':digest((source/'verification.json').read_bytes()),
        'exact_archive_entries_checked':len(entries),'original_inputs_unchanged_after_pack':len(guards),
        'included_scope':'Ten normalized public behavioral corpora, complete retained final files, evidenced/requested versions, source identities, schema, navigation and independent audit',
        'omitted_scope':'Original raw client/response envelopes, hidden reasoning, credentials, protected assessor internals, administrative build tools and guard files',
        'no_new_experiment':True}
    destination.with_suffix('.manifest.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n','utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('entries','verification_job')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--verification-job',required=True);a=p.parse_args()
    main(a.source.resolve(),a.destination.resolve(),a.verification_job)
