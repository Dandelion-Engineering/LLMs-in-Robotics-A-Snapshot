"""Prepare unchanged content-store bytes through native Windows I/O.

This bounded worker has no model, simulator or guest access. Linux independently
checks every restored content hash before committing the initial journal record.
No runtime journal format, chunk size, compression or durability rule changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from content_store import Store, encoded, digest
from workspace_lifecycle import Progress, atomic

def prepare(namespace,objects,destination,progress_path,run_id):
    start=time.monotonic();progress=Progress(progress_path,run_id);progress.advance('bootstrap')
    state=json.loads(Path(namespace).read_bytes());objects=Path(objects);destination=Path(destination)
    progress.advance('inputs');destination.mkdir();(destination/'objects').mkdir()
    used=0
    def charge(size):
        nonlocal used
        if used+size>3*1024**3-1024**2:raise ValueError('Restored journal storage bound')
        used+=size
    store=Store(destination,charge);store.create();files=bytes_done=0;seen={}
    progress.advance('restoring')
    for node in state['nodes'].values():
        key=node.get('sha256')
        if not key:continue
        if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Invalid restore content key')
        if key not in seen:
            raw=(objects/key).read_bytes()
            if len(raw)!=node['size'] or digest(raw)!=key:raise ValueError('Restored namespace blob differs')
            if store.put(raw)!=key:raise ValueError('Prepared content identity differs')
            seen[key]=len(raw)
        if seen[key]!=node['size']:raise ValueError('Conflicting sizes for one content hash')
        files+=1;bytes_done+=node['size'];progress.advance('restoring',files,bytes_done)
    receipt=dict(run_id=run_id,namespace_sha256=digest(encoded(state)),files=files,unique_objects=len(seen),
                 logical_bytes=bytes_done,stored_bytes=used,elapsed_s=time.monotonic()-start,
                 format='unchanged-apartment-content-2',durable_before_admission=True)
    atomic(destination/'prepared.json',receipt);progress.advance('initial_committed')
    return receipt

def main():
    p=argparse.ArgumentParser()
    for name in ('namespace','objects','destination','progress','run-id'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.namespace,a.objects,a.destination,a.progress,a.run_id)))

if __name__=='__main__':main()
