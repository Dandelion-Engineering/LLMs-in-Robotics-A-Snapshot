"""Queued bounded development comparison. Never used as release qualification."""
from pathlib import Path
import hashlib
import json
import time
import recorder

HERE=Path(__file__).resolve().parent


def main():
    output=HERE/'pilots'/'optimization-004'; output.mkdir(parents=True,exist_ok=False)
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
            report={'label':label,'intern_threshold':threshold,'codec':recorder.VERSION,
                'database_bytes':(target/'evidence.sqlite').stat().st_size,'record_elapsed_s':elapsed,
                'exact_event_motion_sha256':observed,'table_rows_payload_bytes':tables,
                'source_database_sha256':recorder.file_digest(source/'evidence.sqlite')}
            reports.append(report); print(json.dumps(report),flush=True)
    assert before=={p.name:recorder.file_digest(p) for p in HERE.glob('*.py')}
    (HERE/'optimization-004.json').write_text(json.dumps({'scope':'Bounded development comparison; not full qualification',
        'implementation_hashes':before,'reports':reports},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': main()
