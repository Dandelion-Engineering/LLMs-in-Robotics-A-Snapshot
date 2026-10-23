"""Queued read-only construction geometry diagnostic; no rule or qualification.

Compare fixed proposed 0/1/2/3/5/10 mm uniform padding, without choosing one. Export
every interval/geometry box and exact union-preserving duplicate/containment
pruning. A spatial hash accelerates containment queries; it does not quantize,
round, merge, expand, or replace geometry by bins or phase hulls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import assess_validation as assessment
from compatibility import digest, finite

PADDINGS_M=(0.,.001,.002,.003,.005,.010)


def box_key(box):return tuple(box['min']+box['max'])


def contained(a,b):
    return all(b['min'][i]<=a['min'][i] and a['max'][i]<=b['max'][i] for i in range(3))


def prune_boxes(records):
    """Remove only exact duplicates or boxes contained in one retained box."""
    unique={}
    for record in records:
        box=record['box'];assessment.require(assessment.valid_box(box),'Invalid corridor box')
        unique.setdefault(box_key(box),record)
    ordered=sorted(unique.values(),key=lambda r:-math.prod(b-a for a,b in zip(r['box']['min'],r['box']['max'])))
    kept=[];index={};large=[];comparisons=0
    for record in ordered:
        box=record['box'];center=tuple(math.floor((a+b)/2/.05) for a,b in zip(box['min'],box['max']))
        candidates=large+index.get(center,[])
        redundant=False
        for i in candidates:
            comparisons+=1
            if contained(box,kept[i]['box']):redundant=True;break
        if redundant:continue
        identity=len(kept);kept.append(record)
        ranges=[range(math.floor(a/.05),math.floor(b/.05)+1) for a,b in zip(box['min'],box['max'])]
        if math.prod(len(r) for r in ranges)>4096:large.append(identity)
        else:
            for bucket in itertools.product(*ranges):index.setdefault(bucket,[]).append(identity)
    return kept,{'input_box_count':len(records),'exact_unique_box_count':len(unique),
        'exact_duplicate_boxes_removed':len(records)-len(unique),'singly_contained_boxes_removed':len(unique)-len(kept),
        'retained_box_count':len(kept),'containment_comparisons':comparisons,
        'union_preserved_exactly':True,'global_optimal_cover_claimed':False,
        'index_bin_width_m':.05,'index_scope':'Candidate lookup only; original box coordinates are unchanged'}


def compare(records,objects,overlaps):
    reports=[]
    for padding in PADDINGS_M:
        strict=runtime=0;blockers=set();minimum=None;witness=None;first_overlap=None
        for record in records:
            original=record['box'];box={key:[v+(-padding if key=='min' else padding) for v in original[key]] for key in ('min','max')}
            for obj in objects:
                other=obj['bounds'];assessment.require(assessment.valid_box(other),'Invalid other-object bounds')
                depths=[min(box['max'][i],other['max'][i])-max(box['min'][i],other['min'][i]) for i in range(3)]
                separation=-min(depths)
                if minimum is None or separation<minimum:
                    minimum=separation;witness={'box_ref':record['source_ref'],'object_id':obj['id'],
                        'original_box':original,'expanded_box':box,'other_object_bounds':other,'axis_overlap_m':depths}
                if all(value>0 for value in depths):strict+=1
                if overlaps(box,other):
                    runtime+=1;blockers.add(obj['id']);first_overlap=first_overlap or {'box_ref':record['source_ref'],
                        'object_id':obj['id'],'axis_overlap_m':depths}
        reports.append({'proposed_uniform_padding_m':padding,'box_count':len(records),'other_object_count':len(objects),
            'pair_comparisons':len(records)*len(objects),'strict_interior_intersection_pairs':strict,
            'runtime_overlap_pairs':runtime,'runtime_blocker_ids':sorted(blockers),'first_runtime_overlap':first_overlap,
            'minimum_signed_axis_separation_m':minimum,'minimum_separation_witness':witness,
            'clearance_scope':'Minimum over AABB pairs of maximum signed axis gap; negative means interior overlap. Not native mesh distance.',
            'padding_selected':False})
    return reports


def export_intervals(source,row,output):
    identity=row['trial_id'];states=row['states'];start=states['cut']['sim_time_s'];end=states['after_placement']['sim_time_s']
    inventory,inventory_ref=source.evidence.json(identity+'/geometry-inventory.json')
    ids=[g['geom_id'] for g in inventory['geoms']]
    assessment.require(len(ids)==len(set(ids)) and {'robot','payload'}<={g['role'] for g in inventory['geoms']},'Incomplete geometry inventory')
    trace=identity+'/whole-geometry.jsonl';entry=source.evidence.entries[trace]
    refs={'path':trace,'sha256':entry['sha256'],'bytes':entry['bytes']}
    records=[];stats={'interval_count':0,'intervals_straddling_cut':0,'intervals_straddling_placement':0,
        'maximum_dense_sim_gap_s':0.,'maximum_dense_wall_gap_s':0.,'maximum_observed_sampling_deficit_m':0.,
        'first_sim_time_s':None,'last_sim_time_s':None,'tick_count_and_gap_checks_pass':True,'physics_timestep_s':None}
    path=output/(identity+'-interval-boxes.jsonl')
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        def visit(line,raw):
            value=json.loads(raw);dense=value['interval_dense_geometry'];first,last=dense['first_sim_wall_s'],dense['last_sim_wall_s']
            if last[0]<start or first[0]>end:return
            assessment.require(dense['geom_ids']==ids,'Dense/inventory IDs differ')
            dt=value['physics_timestep_s'];assessment.require(finite(dt) and dt>0,'Invalid native timestep')
            assessment.require(stats['physics_timestep_s'] is None or stats['physics_timestep_s']==dt,'Native timestep changed')
            stats['physics_timestep_s']=dt;stats['interval_count']+=1
            stats['intervals_straddling_cut']+=int(first[0]<start<=last[0])
            stats['intervals_straddling_placement']+=int(first[0]<=end<last[0])
            previous=stats['last_sim_time_s']
            stats['tick_count_and_gap_checks_pass'] &= (dense['maximum_sim_gap_s']<=dt+1e-9
                and abs((dense['distinct_sim_time_count']-1)*dt-(last[0]-first[0]))<=1e-9
                and (previous is None or first[0]<=previous+1e-9))
            stats['first_sim_time_s']=first[0] if stats['first_sim_time_s'] is None else stats['first_sim_time_s']
            stats['last_sim_time_s']=last[0]
            for clock in ('sim','wall'):stats['maximum_dense_'+clock+'_gap_s']=max(stats['maximum_dense_'+clock+'_gap_s'],dense['maximum_'+clock+'_gap_s'])
            deficit=dense.get('observed_coarse_endpoint_sampling_deficit_m')
            if deficit:stats['maximum_observed_sampling_deficit_m']=max(stats['maximum_observed_sampling_deficit_m'],
                *(v for key in ('lower_m','upper_m') for item in deficit[key] for v in item))
            bounds=dense['sampled_outer_box_union_m']
            assessment.require(len(bounds['min'])==len(bounds['max'])==len(ids),'Dense box count differs')
            exported=[]
            for i,geom_id in enumerate(ids):
                box={key:bounds[key][i] for key in ('min','max')}
                assessment.require(assessment.valid_box(box),'Invalid dense box')
                locator={**refs,'line':line,'line_sha256':hashlib.sha256(raw).hexdigest(),'geom_id':geom_id,
                         'trial_id':identity,'interval_sim_wall_s':[first,last]}
                record={'box':box,'source_ref':locator};records.append(record);exported.append(record)
            stream.write(json.dumps({'phase':value['phase'],'dense':dense,'boxes':exported},sort_keys=True,allow_nan=False)+'\n')
        source.evidence.stream(trace,visit)
    stats['cut_to_placement_covered']=stats['first_sim_time_s'] is not None and stats['first_sim_time_s']<=start and stats['last_sim_time_s']>=end
    stats.update(inventory_ref=inventory_ref,trace_ref=refs,inventory=inventory,
                 scope='Complete per-geometry interval boxes intersecting cut-through-placement; boundary intervals retained whole')
    return records,stats,{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}


def summarize_points(points):
    """Observed extrema only, not a cell, tolerance, or product-domain claim."""
    if not points:return {'point_count':0,'state':'unknown'}
    def ranges(values):return [[min(v[i] for v in values),max(v[i] for v in values)] for i in range(len(values[0]))]
    output={}
    for landmark in ('cut','before_recovery'):
        selected=[p for p in points if p['landmark']==landmark]
        if not selected:continue
        output[landmark]={'point_count':len(selected),
            'tcp_observed_ranges_m':ranges([p['robot']['tcp_position_world_m'] for p in selected]),
            'joint_observed_ranges_rad':ranges([p['robot']['joint_position_rad'] for p in selected]),
            'joint_velocity_observed_ranges_rad_s':ranges([p['robot']['joint_velocity_rad_s'] for p in selected]),
            'relative_position_observed_ranges_m':ranges([p['relative_pose']['position_m'] for p in selected]),
            'jaw_observed_range_m':[min(p['robot']['jaw_width_m'] for p in selected),max(p['robot']['jaw_width_m'] for p in selected)],
            'finger_force_observed_range_N':[min(p['contact'][key] for p in selected for key in ('left_normal_force_N','right_normal_force_N')),
                                           max(p['contact'][key] for p in selected for key in ('left_normal_force_N','right_normal_force_N'))]}
    return {'point_count':len(points),'landmarks':output,'scope':'Observed coupled in-domain points; no numerical cell or rounding epsilon created'}


def run(extraction,screen_receipt,extraction_receipt,destination,output):
    source=assessment.CompletedExtraction(extraction,screen_receipt,extraction_receipt)
    assessment.require(source.manifest['execution_phase']=='construction','Construction only; validation cannot be consumed')
    output=Path(output).resolve();assessment.require(not output.exists(),'Fresh diagnostic output required')
    for base in (source.base,source.evidence.root):
        assessment.require(base!=output and base not in output.parents and output not in base.parents,'Output must be separate from input')
    code,code_ref=source.source('Runtime/restart_state.py');functions=assessment.numeric_functions(code)
    output.mkdir(parents=True,exist_ok=False)
    rows=[];groups={};points={};scene_objects={}
    for identity,declaration in source.declared.items():
        report={'trial_id':identity,'declaration':declaration,'execution_status':source.entries[identity]['execution_status'],
                'selected_construction':identity in source.selected and declaration['destination']==destination}
        rows.append(report)
        if not report['selected_construction']:continue
        try:
            row=source.trial(identity);child=row.get('child_result') or {};details=child.get('details') or {}
            payload=details.get('picked_visible_part_id');group=str(payload)
            report.update(child_status=child.get('status'),child_error=child.get('error'),parent_attempt=row.get('parent_attempt'),
                physical_predicates_passed=details.get('physical_predicates_passed'),timing=child.get('timing'),
                all_objects_generator_domain_members=(row.get('compiled_properties') or {}).get('all_objects_generator_domain_members'),
                payload_id=payload,trial_ref=row['consumed_ref'],physical_success_is_qualification=False)
            cut=row['states']['cut']['payload'];objects=[o for o in cut['geometry']['objects'] if o['id']!=payload]
            scene_objects[identity]=objects
            records,stats,export_ref=export_intervals(source,row,output)
            kept,pruning=prune_boxes(records)
            report.update(geometry=stats,interval_export_ref=export_ref,pruning=pruning,
                padding_comparisons=compare(kept,objects,functions['overlaps']),diagnostic_state='measured_discrete_only')
            groups.setdefault(group,[]).extend(kept)
            if report['all_objects_generator_domain_members'] is True:
                for landmark in ('cut','before_recovery'):
                    state=row['states'][landmark];snapshot=state['payload']
                    obj=next(o for o in snapshot['geometry']['objects'] if o['id']==payload)
                    points.setdefault(group,[]).append({'trial_id':identity,'landmark':landmark,'source_ref':state['source_ref'],
                        'snapshot_sha256':snapshot['snapshot_sha256'],'physical_configuration_sha256':snapshot['physical_configuration_sha256'],
                        'physical_class_observation_sha256':digest(snapshot['physical_class_observation']),
                        'robot':snapshot['robot'],'payload':obj,'relative_pose':snapshot['object_poses'][payload]['relative_to_tcp'],
                        'contact':snapshot['contacts']['by_object'][payload],
                        'actual_host_timing_pass':(child.get('timing') or {}).get('actual_host_timing_pass')})
        except (ValueError,KeyError,TypeError,OSError) as error:
            report.update(diagnostic_state='unknown',reason=str(error))
    group_reports=[]
    for group,records in groups.items():
        kept,pruning=prune_boxes(records)
        path=output/(group+'-exact-pruned-box-union.json')
        assessment.reader.write(path,{'payload_location_group':group,'boxes':kept,'pruning':pruning,
            'scope':'Exact union of retained interval boxes across this payload ID only; no transfer/qualification decision'})
        comparison=[]
        for row in rows:
            if row.get('payload_id')==group and row['trial_id'] in scene_objects:
                comparison.append({'cut_trial_id':row['trial_id'],'padding_comparisons':compare(kept,scene_objects[row['trial_id']],functions['overlaps'])})
        group_reports.append({'payload_location_group':group,'pruning':pruning,
            'included_trial_ids':sorted({r['source_ref']['trial_id'] for r in kept}),
            'all_declared_group_routes_included':all(r.get('diagnostic_state')=='measured_discrete_only'
                for r in rows if r.get('payload_id')==group),
            'candidate_union_ref':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size},
            'all_member_cut_scene_comparisons':comparison,'in_domain_coupled_summary':summarize_points(points.get(group,[])),
            'in_domain_coupled_points':points.get(group,[])})
    source.evidence.stable()
    report={'schema_version':'construction-interval-corridor-diagnostic-1','completed_at':datetime.now(timezone.utc).isoformat(),
        'construction_extraction_ref':source.ref,'screen_receipt_ref':source.receipt_ref,
        'extraction_receipt_ref':source.extraction_receipt_ref,'overlap_formula_source_ref':code_ref,
        'destination':destination,'proposed_padding_comparison_m':PADDINGS_M,'trials':rows,'payload_location_groups':group_reports,
        'qualification_granted':False,'readiness_granted':False,'padding_selected':False,'numerical_cell_created':False,
        'continuous_clearance_bound_m':None,'source_holds':source.summary.get('sources_unchanged'),
        'limitations':['Bad host timing remains disqualifying; this diagnostic changes no original outcome.',
            'Only native discrete-state outer boxes and actual other movable cut-object bounds are compared.',
            'Fixed-world/self native contact and continuous geometry are not established by these comparisons.',
            'B2 remains separate from B10; no unseen location or Cartesian-product state domain is inferred.']}
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('construction-extraction','screen-receipt','extraction-receipt','output'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--destination',choices=('parking1','parking2'),required=True)
    args=parser.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Runtime'))
    from release_runner import queued_job
    queue=queued_job(expected_script=__file__)
    dependencies=[Path(__file__),Path(assessment.__file__),Path(assessment.reader.__file__),
                  Path(__file__).with_name('compatibility.py'),Path(__file__).with_name('bundle_construction.py')]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    report=run(args.construction_extraction,args.screen_receipt,args.extraction_receipt,args.destination,args.output)
    assessment.require(before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies},'Diagnostic source changed')
    report.update(queue=queue,diagnostic_source_sha256=before)
    assessment.reader.write(Path(args.output)/'diagnostic.json',report)
    print(json.dumps({'output':str(Path(args.output).resolve()),'qualification_granted':False}))


if __name__=='__main__':main()
