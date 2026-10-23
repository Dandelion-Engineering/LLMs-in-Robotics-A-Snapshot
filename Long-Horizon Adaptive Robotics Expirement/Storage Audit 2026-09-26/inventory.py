"""Read metadata only; create new audit outputs exclusively. Never follow links.

Run with project Python -X utf8 -B inventory.py. Outputs are immutable: a
second invocation needs a new output directory. No source contents are read.
"""
import collections
import datetime
import heapq
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).parent / 'measurement'
OUT.mkdir(parents=True, exist_ok=False)
started = datetime.datetime.now().astimezone().isoformat()
dirs = collections.defaultdict(lambda: [0, 0])
extensions = collections.defaultdict(lambda: [0, 0])
errors, skipped, largest = [], [], []
with (OUT / 'files.tsv').open('x', encoding='utf-8', newline='') as f:
    f.write('path\tlogical_bytes\n')
    stack = [ROOT]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            errors.append([str(directory), str(exc)])
            continue
        for entry in entries:
            p = Path(entry.path)
            rel = p.relative_to(ROOT).as_posix()
            if p == OUT:
                skipped.append([rel, 'audit output directory excluded'])
                continue
            try:
                st = entry.stat(follow_symlinks=False)
                if getattr(st, 'st_file_attributes', 0) & 0x400:
                    skipped.append([rel, 'reparse point not followed'])
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(p)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    skipped.append([rel, 'not regular file'])
                    continue
                f.write(f'{rel}\t{st.st_size}\n')
                parts = rel.split('/')
                for depth in range(len(parts)):
                    key = '/'.join(parts[:depth]) or '.'
                    row = dirs[key]
                    row[0] += 1
                    row[1] += st.st_size
                ext = p.suffix.lower() or '(no extension)'
                extensions[ext][0] += 1
                extensions[ext][1] += st.st_size
                heapq.heappush(largest, (st.st_size, rel))
                if len(largest) > 100:
                    heapq.heappop(largest)
            except OSError as exc:
                errors.append([rel, str(exc)])
with (OUT / 'directories.tsv').open('x', encoding='utf-8', newline='') as f:
    f.write('path\tfiles\tlogical_bytes\n')
    for path, row in sorted(dirs.items(), key=lambda kv: kv[1][1], reverse=True):
        f.write(path + '\t' + '\t'.join(map(str, row)) + '\n')
summary = dict(started=started, finished=datetime.datetime.now().astimezone().isoformat(), root=str(ROOT),
               total_files=dirs['.'][0], logical_bytes=dirs['.'][1],
               extensions=dict(sorted(extensions.items(), key=lambda kv: kv[1][1], reverse=True)),
               largest_files=[dict(path=p, logical_bytes=s) for s,p in sorted(largest, reverse=True)],
               volumes={v: dict(zip(('total','used','free'), shutil.disk_usage(v))) for v in ('C:/','D:/') if Path(v).exists()},
               errors=errors, skipped=skipped,
               limitations='Logical-path metadata snapshot, not a frozen filesystem or allocated-space census. No content hashing or modifications to measured files. Audit measurement output excluded. Follow with summarize_inventory.py for physical identity checks and compact retained tables.')
with (OUT / 'summary.json').open('x', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)
print(json.dumps({k: summary[k] for k in ('started','finished','total_files','logical_bytes','volumes','errors','skipped')}, indent=2))
print('TOP DIRECTORIES')
for p,row in sorted(dirs.items(), key=lambda kv: kv[1][1], reverse=True)[:55]:
    print(f'{row[1]/1e9:.3f} GB\t{row[0]} files\t{p}')
