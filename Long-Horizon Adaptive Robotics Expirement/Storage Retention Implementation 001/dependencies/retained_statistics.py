"""Compact exact statistics from a successfully partitioned final retention manifest."""
import argparse
from collections import defaultdict
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def source(path):return {'path':str(Path(path).resolve()),'bytes':Path(path).stat().st_size,'sha256':sha(path)}
def count():return {'files':0,'logical_bytes':0,'rgb':{'files':0,'logical_bytes':0},'depth':{'files':0,'logical_bytes':0}}
def add(c,row):
    c['files']+=1;c['logical_bytes']+=row['logical_bytes']
    kind=row['artifact_type'];c[kind]['files']+=1;c[kind]['logical_bytes']+=row['logical_bytes']

def main():
    p=argparse.ArgumentParser();p.add_argument('--partition',type=Path,required=True);p.add_argument('--required',type=Path,required=True)
    p.add_argument('--partition-job-id',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    queue=ROOT.parent/'tools/compute_queue/compute_queue.py'
    receipt=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(queue),'status',a.partition_job_id]))
    if receipt['state']!='succeeded' or receipt['exit_status']!=0:raise ValueError('Partition has not officially succeeded')
    if 'partition' not in receipt['argv'] or Path(receipt['cwd']).resolve()!=ROOT:raise ValueError('Receipt is not a project partition job')
    argv=receipt['argv'];name=argv[argv.index('--name')+1];required_arg=Path(argv[argv.index('--required')+1])
    if not required_arg.is_absolute():required_arg=ROOT/required_arg
    if a.partition.name!=name+'-partition.json' or required_arg.resolve()!=a.required.resolve():raise ValueError('Official job parameters differ from supplied partition inputs')
    partition=json.loads(a.partition.read_text());expected=partition['manifests']['retained'];manifest=ROOT/expected['path']
    if sha(a.required)!=partition['required_input_sha256']:raise ValueError('Partition input differs from extraction dependency manifest')
    if sha(manifest)!=expected['sha256']:raise ValueError('Final retained manifest digest mismatch')
    total=count();groups=defaultdict(count);reasons=defaultdict(count);overlaps=defaultdict(count);exclusive=defaultdict(count);captures=defaultdict(dict)
    consumer_reasons={'current_viewer_dependency','fixed_selection_rebuild_dependency','source_bound_validation_dependency','tracked_literal_image_reference'}
    with gzip.open(manifest,'rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);rs=set(row['reasons']);add(total,row)
            key=(row['run_id'],row['frame_id']);kind=row['artifact_type']
            if kind in captures[key]:raise ValueError('Duplicate run/frame/type identity')
            captures[key][kind]={'path':row['path'],'artifact_type':kind,'logical_bytes':row['logical_bytes']}
            viewer='current_viewer_dependency' in rs
            consumer=bool(rs & consumer_reasons)
            diagnostic=any(x.startswith('diagnostic_window:') for x in rs)
            orphan='unmapped_or_calibration_artifact' in rs
            flags={'current_viewer_union':viewer,'additional_beyond_current_viewer_union':not viewer,
                   'all_current_consumer_union':consumer,'additional_beyond_all_current_consumers':not consumer,
                   'fixed_selected_rebuild_union':'fixed_selection_rebuild_dependency' in rs,
                   'saved_source_bound_validation_union':'source_bound_validation_dependency' in rs,
                   'tracked_literal_reference_union':'tracked_literal_image_reference' in rs,
                   'diagnostic_window_union':diagnostic,'diagnostic_also_current_viewer':diagnostic and viewer,
                   'diagnostic_outside_current_viewer':diagnostic and not viewer,'unmapped_or_calibration_union':orphan}
            for group,include in flags.items():
                if include:add(groups[group],row)
            category=('current_viewer' if viewer else 'other_current_consumer' if consumer
                      else 'diagnostic_outside_consumers' if diagnostic else 'unmapped_other' if orphan else 'other')
            add(exclusive[category],row)
            for r in rs:add(reasons[r],row)
            for pair in combinations(sorted(rs),2):add(overlaps[pair],row)
    if total['files']!=expected['files'] or total['logical_bytes']!=expected['logical_bytes']:raise ValueError('Manifest totals disagree with partition')
    if sum(x['files'] for x in exclusive.values())!=total['files']:raise AssertionError('Exclusive count mismatch')
    if sum(x['logical_bytes'] for x in exclusive.values())!=total['logical_bytes']:raise AssertionError('Exclusive bytes mismatch')
    complete=sum(set(leaves)=={'rgb','depth'} for leaves in captures.values())
    unmatched=[{'run_id':rid,'frame_id':fid,'leaves':list(leaves.values())}
               for (rid,fid),leaves in sorted(captures.items()) if set(leaves)!={'rgb','depth'}]
    report={'format':'retained-manifest-statistics-1','status':'passed','partition':source(a.partition),'required_input':source(a.required),
            'retained_manifest':source(manifest),'partition_official_queue_receipt':receipt,'total':total,
            'capture_pairing':{'distinct_run_frame_ids':len(captures),'complete_rgb_depth_pairs':complete,
                'unmatched_frame_ids':len(unmatched),'unmatched_artifact_files':sum(len(r['leaves']) for r in unmatched),'unmatched':unmatched,
                'scope':'Pairing uses original run ID and numeric frame filename identity. File count is not paired capture count; unmapped preserved files need not have emitted observation events.'},
            'groups':dict(groups),'mutually_exclusive_partition':dict(exclusive),'per_reason_nonadditive':dict(sorted(reasons.items())),
            'pairwise_reason_overlaps_nonadditive':[{'reason_a':a,'reason_b':b,**v} for (a,b),v in sorted(overlaps.items())],
            'interpretation':'Group and reason counts overlap and must not be added. Only mutually_exclusive_partition sums to total. Current-viewer union is actual Investigation007 plus Explorer references, distinct from saved validation, exact selected rebuild and tracked literal dependencies. No camera bodies are read by this summary.'}
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'status':'passed','total':total,'capture_pairing':report['capture_pairing'],'groups':dict(groups),'mutually_exclusive_partition':dict(exclusive)},indent=2))
if __name__=='__main__':main()
