"""Queued bounded development comparison. Never used as release qualification."""
from pathlib import Path
import hashlib
import json
import time
import gzip
import shutil
import recorder

HERE=Path(__file__).resolve().parent


def main(generation):
    output=HERE/'pilots'/generation; output.mkdir(parents=True,exist_ok=False)
    before={p.name:recorder.file_digest(p) for p in HERE.glob('*.py')}
    reports=[]
    for label in ('high-observation-volume','large-input-failure'):
        source=HERE/'pilots'/'qualification-003'/label
        reader=recorder.Reader(source); events=list(reader.events()); motion=list(reader.motion())
        docs={key:reader.document(key) for key in ('manifest','result')}; reader.close()
        expected=hashlib.sha256(recorder.pack(events)+recorder.pack(motion)).hexdigest()
        for threshold in (2048,8192,1_000_000_000):
            recorder.INTERN_BYTES=threshold
            target=output/(label+'-'+str(threshold)); writer=recorder.Recorder(target,run_id=label,
                core_quota_bytes=200_000_000,policy=recorder.ImagePolicy(image_quota_bytes=0))
            started=time.perf_counter()
            for event in events: writer.event(event)
            for row in motion: writer.motion(row)
            for key,value in docs.items(): writer.document(key,value)
            writer.close(); elapsed=time.perf_counter()-started
            reader=recorder.Reader(target)
            observed=hashlib.sha256(recorder.pack(list(reader.events()))+recorder.pack(list(reader.motion()))).hexdigest()
            assert observed==expected
            for key,value in docs.items(): assert recorder.pack(reader.document(key))==recorder.pack(value)
            tables={table:reader.db.execute('SELECT COUNT(*),SUM(LENGTH(payload)) FROM '+table).fetchone()
                    for table in ('objects','telemetry','events','motion','documents')}
            reader.close()
            packed=target/'development-container.sqlite.gz'
            with (target/'evidence.sqlite').open('rb') as source_stream,gzip.open(packed,'wb',compresslevel=6) as destination_stream:
                shutil.copyfileobj(source_stream,destination_stream,1024*1024)
            restored_hash=hashlib.sha256()
            with gzip.open(packed,'rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''): restored_hash.update(block)
            assert restored_hash.hexdigest()==recorder.file_digest(target/'evidence.sqlite')
            report={'label':label,'intern_threshold':threshold,'codec':recorder.VERSION,
                'database_bytes':(target/'evidence.sqlite').stat().st_size,'record_elapsed_s':elapsed,
                'development_finalized_gzip_bytes':packed.stat().st_size,
                'finalized_gzip_roundtrip_database_sha256':restored_hash.hexdigest(),
                'exact_event_motion_sha256':observed,'table_rows_payload_bytes':tables,
                'source_database_sha256':recorder.file_digest(source/'evidence.sqlite')}
            reports.append(report); print(json.dumps(report),flush=True)
    assert before=={p.name:recorder.file_digest(p) for p in HERE.glob('*.py')}
    (HERE/(generation+'.json')).write_text(json.dumps({'scope':'Bounded development comparison; not full qualification',
        'implementation_hashes':before,'reports':reports},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--generation',required=True);main(p.parse_args().generation)
