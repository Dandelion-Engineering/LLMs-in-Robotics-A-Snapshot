"""Read-only r4 dependency and bounded diagnostic-window extraction.

The full header scan belongs on the shared queue. No pixel bodies are read.
Existing files are never written. All outputs use exclusive creation.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = ROOT / 'Long-Horizon Adaptive Robotics Expirement'
ATTEMPTS = EXP / 'Evidence/releases/batch01-eval-r4/attempts'
SITE = EXP / 'Engineering Investigation 007/site-r4-003'
EXPLORER = EXP / 'Task and Architecture Explorer'
DERIVED = EXP / 'Evidence/derived/evaluation-r4-administrative005-001'
HEADER = re.compile(rb'^\{"schema_version":"[^"]+","run_id":"([^"]+)","event_id":(\d+),"event_type":"([^"]+)","source":"[^"]+","sim_time_s":([^,]+),"sim_tick":([^,]+),"wall_elapsed_s":([^,]+),')
PATH = re.compile(rb'"(rgb|depth)":"(frames/[^"\\]+\.(?:png|npz))"')
STAMP = re.compile(rb'"capture_sim_time_s":([^,}]+)')
EXPLICIT = re.compile(r'(batch01-eval-r4-[A-Za-z0-9-]+)/evidence/frames/([0-9]+(?:-depth)?\.(?:png|npz))')

def digest(data): return hashlib.sha256(data).hexdigest()
def rel(path): return Path(path).resolve().relative_to(ROOT).as_posix()
def write_json(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(obj, out, indent=2, sort_keys=True); out.write('\n')
def write_gzip(path, rows):
    with path.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as out:
            for row in rows:
                out.write((json.dumps(row, sort_keys=True, separators=(',', ':'))+'\n').encode())

class Extractor:
    def __init__(self):
        self.required = {}
        self.sources = {}
        self.windows = []
        self.scan = []
        self.inventory = []
        self.rebuild = {}
    def read(self, path):
        raw = path.read_bytes()
        self.sources[rel(path)] = {'bytes':len(raw), 'sha256':digest(raw)}
        return json.loads(raw)
    def add(self, path, reason, dependency, identity=None, expected=None):
        path = path.resolve()
        if not path.is_relative_to(ATTEMPTS):
            return
        name = rel(path)
        row = self.required.setdefault(name, {'path':name, 'reasons':[], 'dependencies':[], 'source_identities':[]})
        for key, value in [('reasons',reason),('dependencies',dependency),('source_identities',identity)]:
            if value is not None and value not in row[key]: row[key].append(value)
        if expected:
            current = row.setdefault('expected_sha256', expected)
            if current != expected: raise ValueError('Contradictory frame hash '+name)
        if not path.is_file(): raise FileNotFoundError(name)
    def trace_manifest(self, directory, ref, reason, dependency):
        path = directory / unquote(ref['href'])
        m = self.read(path)
        bound = self.sources[rel(path)]
        if bound != {'bytes':ref['bytes'], 'sha256':ref['sha256']}: raise ValueError('Trace manifest binding')
        count = 0
        for e in m['event_headers']:
            for kind, a in e.get('artifact_refs',{}).items():
                if kind not in ('rgb','depth') or a.get('state') != 'available': continue
                p = (directory/unquote(a['href'])).resolve()
                self.add(p,reason,dependency,{'event_id':e['event_id'],'sim_time_s':e['sim_time_s'],'artifact_type':kind,'source':rel(path)},a.get('sha256'))
                if p.stat().st_size != a['bytes']: raise ValueError('Artifact size mismatch '+str(p))
                count += 1
        return count
    def viewer_dependencies(self):
        package=self.read(SITE/'package-manifest.json')
        self.rebuild['fixed_selected_run_ids']=[t['run_id'] for t in package['trace_checks']]
        for t in package['trace_checks']:
            n=self.trace_manifest(SITE,t['package']['manifest'],'current_viewer_dependency','Investigation007/site-r4-003:'+t['run_id'])
            self.inventory.append({'consumer':'Investigation007','run_id':t['run_id'],'references':n})
        validation=EXP/'Evidence/derived/investigation007-package-validation-004/first-declared-trace'
        descriptor=self.read(validation/'descriptor.json')
        n=self.trace_manifest(validation,descriptor['package']['manifest'],'source_bound_validation_dependency','Investigation007 validation004 first fixed trace')
        self.inventory.append({'consumer':'source_bound_package_validation004','references':n})
        index=self.read(EXPLORER/'data/index.json')
        for ref in index['episodes']:
            ep_path=(EXPLORER/unquote(ref['href'])).resolve(); ep=self.read(ep_path)
            if self.sources[rel(ep_path)] != {'bytes':ref['bytes'],'sha256':ref['sha256']}: raise ValueError('Explorer binding')
            n=0
            for e in ep['events']:
                for kind,a in e.get('artifact_refs',{}).items():
                    self.add(EXPLORER/unquote(a['href']),'current_viewer_dependency','Task and Architecture Explorer:'+ep['id'],{'event_id':e['event_id'],'sim_time_s':e['sim_time_s'],'artifact_type':kind,'source':rel(ep_path)},a.get('sha256'));n+=1
            self.inventory.append({'consumer':'Explorer','run_id':ep['id'],'references':n})
        # Search actual tracked content, including historical literal pointers.
        tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
        found=[]; scanned=0
        for name in tracked:
            if not name or not name.endswith(('.json','.jsonl','.md','.py','.js','.html','.txt','.css')): continue
            p=ROOT/name
            if not p.is_file(): continue
            raw=p.read_bytes();scanned+=len(raw)
            if b'batch01-eval-r4' not in raw or b'frames' not in raw: continue
            text=unquote(raw.decode('utf-8',errors='replace')).replace('\\\\','/').replace('\\','/')
            refs=sorted(set(EXPLICIT.findall(text)))
            if refs:
                self.sources[name]={'bytes':len(raw),'sha256':digest(raw)}
                for rid,frame in refs:
                    p=ATTEMPTS/rid/'evidence/frames'/frame
                    self.add(p,'tracked_literal_image_reference',name,{'reference_kind':'literal path in tracked source'})
                found.append({'source':name,'exact_r4_frame_references':len(refs)})
        self.rebuild['tracked_reference_scan']={'tracked_paths':len(tracked)-1,'bytes_read':scanned,'hits':found}
        for name in ['Engineering Investigation 005/evidence_adapter.py','Engineering Investigation 005/selected_trace.py','Engineering Investigation 007/validate_package.py','Task and Architecture Explorer/validate_report.py','Runtime 004/diagnostics.py','Engineering Investigation 005/continuity.py','Runtime 004/protocol.py','Batch 01/Release Analysis 005/analyze_results.py']:
            p=EXP/name;raw=p.read_bytes();self.sources[rel(p)]={'bytes':len(raw),'sha256':digest(raw)}
        self.rebuild.update({'selected_reader_requires_all_10Hz_images':False,'reason':'evidence_adapter.read_run applies 2Hz/parent-linked/final selection before artifact_ref reads any pixel body; selected_trace source hashes cover manifest/events/motion/result/terminal only. Existing packages authenticate exact selected image identities.','numerical_consumers':'Aggregate analysis consumes compact result/manifests. diagnostics consumes event and full precision motion streams. continuity consumes event/state/restart and provenance/calibration records. None reads r4 PNG/NPZ pixel bodies.','calibration_rule':'Retain every explicit r4 image reference, all nonnumeric/unknown frame names, and any orphan camera artifact. Qualification artifacts outside r4 are untouched. No calibrated geometry or external qualification is inferred from visual windows.'})
    def window(self,rid,category,anchor,before,after,identity,why):
        start=max(0.0,anchor-before);end=anchor+after
        row={'window_id':f'W{len(self.windows)+1:05d}','run_id':rid,'category':category,'selection':'outcome_selected_diagnostic','start_capture_sim_time_s':start,'end_capture_sim_time_s':end,'anchor':identity,'reason':why,'selection_rate':'All original saved RGB and depth captures inside this bounded window; no interpolation'}
        self.windows.append(row);return row
    def scan_run(self,attempt,selected,contact_top):
        rid=attempt.name;root=attempt/'evidence';p=root/'events.jsonl'
        if not p.is_file(): return
        result=self.read(root/'result.json') if (root/'result.json').is_file() else None
        before=p.stat();sha=hashlib.sha256(); observations=[];anchors=defaultdict(list);counts=Counter();last=None;init=None;parents=set();all_obs=[]
        with p.open('rb',buffering=4*1024*1024) as stream:
            for line in stream:
                sha.update(line)
                if not line.endswith(b'\n'): raise ValueError('Incomplete event record '+rid)
                m=HEADER.match(line)
                if not m: raise ValueError('Header shape changed '+rid)
                rr,eid,kind,sim,tick,wall=m.groups()
                if rr.decode()!=rid:raise ValueError('Run mismatch')
                event={'event_id':int(eid),'event_type':kind.decode(),'sim_time_s':float(sim),'sim_tick':int(tick),'wall_elapsed_s':float(wall)}
                last=event;counts[event['event_type']]+=1
                if kind==b'episode_clock_started':init=event
                if kind==b'observation':
                    # Original packet appears before trailing RGB/depth metadata.
                    tail=line[max(line.rfind(b'"rgb":"'),0):]
                    paths={k.decode():v.decode() for k,v in PATH.findall(tail)}
                    stamp=STAMP.search(tail)
                    if set(paths)!= {'rgb','depth'} or stamp is None: raise ValueError('Observation artifact mapping changed '+rid)
                    marker=b'"artifacts":'
                    artifacts=json.JSONDecoder().raw_decode(tail[tail.index(marker)+len(marker):].decode())[0]
                    obs={**event,'capture_sim_time_s':float(stamp.group(1)),'paths':paths,'artifact_hashes':{k:v['sha256'] for k,v in artifacts.items()}}
                    observations.append(obs)
                    if rid in selected:all_obs.append(event)
                    continue
                if rid in selected:
                    pm=re.search(rb'"parent_ids":(\[[^\]]*\])',line[:800])
                    if pm:parents.update(json.loads(pm.group(1)))
                if kind in (b'completion_claim_check',b'restart_begin',b'restart_ready',b'restart_absence',b'model_error',b'terminal_error',b'final_world',b'scenario_exposure',b'physical_service_event',b'resource_watchdog_exceeded',b'stale_model_output_discarded',b'model_output_invalidated',b'candidate_usage_tail_missing'):
                    full=json.loads(line);payload=full['payload']
                    expected=digest(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
                    if expected!=full['payload_sha256']:raise ValueError('Anchor payload hash mismatch')
                    anchor={**event,'payload_sha256':expected}
                    if kind==b'completion_claim_check' and not payload.get('success'):
                        anchors['incorrect_completion_claim'].append({**anchor,'reasons':payload.get('reasons',[])})
                    elif kind==b'restart_begin':anchors['runtime_restart'].append(anchor)
                    elif kind==b'scenario_exposure':anchors['scenario_intervention'].append(anchor)
                    elif kind==b'physical_service_event':
                        subtype=str(payload.get('type',''));status=str(payload.get('status',payload.get('outcome','')))
                        # Failed physical feedback and explicit safety/contact/ambiguity labels only.
                        label=(subtype+' '+status+' '+str(payload.get('reason',''))).lower()
                        if any(x in label for x in ('fail','collision','unsafe','abort','ambiguous','lost','slip','drop','contact_limit')):
                            anchors['physical_or_ambiguous_event'].append({**anchor,'physical_type':subtype,'status':status,'reason':payload.get('reason')})
                    elif kind in (b'model_error',b'terminal_error',b'resource_watchdog_exceeded',b'stale_model_output_discarded',b'model_output_invalidated',b'candidate_usage_tail_missing'):anchors['explicit_runtime_anomaly'].append(anchor)
                    elif kind==b'final_world':anchors['physical_end'].append(anchor)
        after=p.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Event source changed')
        self.sources[rel(p)]={'bytes':before.st_size,'sha256':sha.hexdigest()}
        if not observations:raise ValueError('No observation mappings '+rid)
        endpoint=(anchors['physical_end'] or [last])[-1]
        window_start=len(self.windows)
        if result is None:
            self.window(rid,'administrative_partial',observations[-1]['capture_sim_time_s'],20,0,last,'Final recorded capture context only; physical ending and outcome remain unknown')
            self.window(rid,'administrative_partial_start',observations[0]['capture_sim_time_s'],0,5,observations[0],'Startup of interrupted partial record')
        elif result.get('validity')!='valid' or result.get('infrastructure_invalid'):
            self.window(rid,'infrastructure_invalid',endpoint['sim_time_s'],20,2,endpoint,str(result.get('validity_reason')))
        elif result.get('outcome')!='success':
            self.window(rid,'valid_task_failure',endpoint['sim_time_s'],20,2,endpoint,str(result.get('termination_reason')))
        for category in ['incorrect_completion_claim','physical_or_ambiguous_event','explicit_runtime_anomaly']:
            rows=anchors[category]
            # First/last per observed reason or event type; repeated 1861-claim history remains numerical.
            by_reason=defaultdict(list)
            for row in rows:by_reason[json.dumps(row.get('reasons', [row.get('physical_type'),row.get('status'),row.get('reason'),row['event_type']]),sort_keys=True)].append(row)
            for key, group in by_reason.items():
                chosen={row['event_id']:row for row in [group[0],group[-1]]}
                for row in chosen.values():self.window(rid,category,row['sim_time_s'],5,5,row,'First/last event of this recorded reason class; bounded outcome-selected context')
        for row in anchors['runtime_restart']:
            self.window(rid,'runtime_restart',row['sim_time_s'],5,15,row,'Each actual restart: pre-cut physical context and bounded post-cut action ambiguity')
        for row in {r['event_id']:r for r in anchors['scenario_intervention'][:1]+anchors['scenario_intervention'][-1:]}.values():
            self.window(rid,'scenario_intervention',row['sim_time_s'],5,10,row,'First/last protected scenario intervention; no admissibility or recovery inference')
        if rid in contact_top:
            mp=root/'motion.jsonl';peak=(-1,None);mh=hashlib.sha256()
            with mp.open('rb') as stream:
                for line in stream:
                    mh.update(line);sample=json.loads(line)
                    if sample.get('contact_peak_N',-1)>peak[0]:peak=(sample['contact_peak_N'],sample['sim_time_s'])
            self.sources[rel(mp)]={'bytes':mp.stat().st_size,'sha256':mh.hexdigest()}
            self.window(rid,'high_recorded_contact',peak[1],5,5,{'motion_sim_time_s':peak[1],'contact_peak_N':peak[0]},'Ten highest all-run recorded contact peaks; contact is not automatically unintended collision')
        if rid in self.discordant:
            start=(init or observations[0])['sim_time_s'];end=endpoint['sim_time_s']
            for phase,fraction in [('early',.25),('middle',.5),('late',.75)]:
                self.window(rid,'discordant_pair_'+phase,start+(end-start)*fraction,5,5,{'fraction_of_recorded_episode':fraction},'Same rule for both sides of the two baseline/A3 discordant pairs')
            self.window(rid,'discordant_pair_endpoint',end,30,2,endpoint,'Endpoint context for both sides of the two baseline/A3 discordant pairs')
        local=self.windows[window_start:]
        for window in local:window['selected_observations']=0;window['first_available_capture_sim_time_s']=None;window['last_available_capture_sim_time_s']=None
        seen_paths=set()
        for obs in observations:
            seen_paths.update(obs['paths'].values())
            matches=[w for w in local if w['start_capture_sim_time_s']-1e-9<=obs['capture_sim_time_s']<=w['end_capture_sim_time_s']+1e-9]
            for w in matches:
                w['selected_observations']+=1
                if w['first_available_capture_sim_time_s'] is None:w['first_available_capture_sim_time_s']=obs['capture_sim_time_s']
                w['last_available_capture_sim_time_s']=obs['capture_sim_time_s']
                for kind,value in obs['paths'].items():
                    self.add(root/value,'diagnostic_window:'+w['category'],w['window_id'],{k:v for k,v in obs.items() if k not in ('paths','artifact_hashes')},obs['artifact_hashes'][kind])
        # Calibration/unmapped files cannot become eligible merely by absence from events.
        orphans=[]
        for p2 in (root/'frames').iterdir():
            if p2.is_file() and p2.suffix.lower() in ('.png','.npz') and p2.relative_to(root).as_posix() not in seen_paths:
                self.add(p2,'unmapped_or_calibration_artifact','conservative_uncategorized_r4_frame',{'source':'No observation mapping; preserved without inferring eligibility'});orphans.append(p2.name)
        if rid in selected:
            last_obs=-float('inf');keep=[]
            for o in all_obs:
                if o['event_id'] not in parents and o['sim_time_s']-last_obs < .5-1e-9:continue
                last_obs=o['sim_time_s'];keep.append(o['event_id'])
            if all_obs[-1]['event_id'] not in keep:keep.append(all_obs[-1]['event_id'])
            for o in observations:
                if o['event_id'] in keep:
                    for k,v in o['paths'].items():self.add(root/v,'fixed_selection_rebuild_dependency','Investigation005 original 2Hz plus parent-linked/final sampling',{'event_id':o['event_id'],'sim_time_s':o['sim_time_s'],'capture_sim_time_s':o['capture_sim_time_s'],'artifact_type':k},o['artifact_hashes'][k])
            self.rebuild.setdefault('recomputed_selected_observations',{})[rid]=len(keep)
        self.scan.append({'run_id':rid,'events':sum(counts.values()),'event_counts':dict(counts),'observations':len(observations),'event_bytes_read':before.st_size,'windows':len(local),'orphan_frames_retained':orphans,'anchor_counts':{k:len(v) for k,v in anchors.items()},'false_done_assertions_result':result.get('false_done_assertions') if result else None,'actual_false_claim_anchors':len(anchors['incorrect_completion_claim']),'status':'complete'})
        print(json.dumps({'scanned':rid,'observations':len(observations),'windows':len(local),'required_paths_so_far':len(self.required)}),flush=True)
    def run(self,out):
        out.mkdir(exist_ok=False,parents=True)
        implementation=Path(__file__).read_bytes()
        self.sources[rel(Path(__file__))]={'bytes':len(implementation),'sha256':digest(implementation)}
        self.viewer_dependencies()
        index=self.read(DERIVED/'index.json');valid={r['run_id']:r for r in index['runs'] if r['primary_disposition']=='eligible'}
        pairs=[]
        for rid,r in valid.items():
            if not rid.endswith('-baseline-persistent'):continue
            other=rid.replace('-baseline-persistent','-A3-persistent')
            if other in valid and (r['selected_result'].get('outcome')=='success') != (valid[other]['selected_result'].get('outcome')=='success'):pairs.append([rid,other])
        if len(pairs)!=2:raise ValueError('Expected two discordant eligible pairs')
        self.discordant={r for pair in pairs for r in pair}
        results=[]
        for p in sorted(ATTEMPTS.glob('*/evidence/result.json')):
            r=self.read(p);results.append((float(r.get('contact_peak_N',0)),r['run_id']))
        top={rid for peak,rid in sorted(results,reverse=True)[:10]}
        self.rebuild['top_recorded_contact_runs']=[{'run_id':rid,'contact_peak_N':peak} for peak,rid in sorted(results,reverse=True)[:10]]
        self.rebuild['discordant_pairs']=pairs
        selected=set(self.rebuild['fixed_selected_run_ids'])
        for attempt in sorted(ATTEMPTS.iterdir()):
            if attempt.is_dir():self.scan_run(attempt,selected,top)
        if Path(__file__).read_bytes()!=implementation:raise ValueError('Extractor implementation changed during scan')
        rows=[self.required[k] for k in sorted(self.required)]
        write_gzip(out/'retained-inputs.jsonl.gz',rows)
        write_json(out/'windows.json',{'format':'r4-diagnostic-windows-1','windows':self.windows,'selection_warning':'Outcome-selected diagnostic images are not a representative performance sample. Current fixed selection was predeclared; these additional windows were selected after outcomes. Completeness means every original saved observation in each declared interval, not nominal 10Hz availability.','counts':dict(Counter(w['category'] for w in self.windows))})
        write_json(out/'scan.json',{'format':'r4-event-header-scan-1','runs':self.scan,'total_event_bytes_read':sum(r['event_bytes_read'] for r in self.scan)})
        write_json(out/'decisions.json',{'format':'r4-image-dependencies-1','created_at':datetime.now(timezone.utc).isoformat(),'required_paths':len(rows),'consumer_inventory':self.inventory,'rebuild':self.rebuild,'sources':self.sources})
        print(json.dumps({'status':'completed','required_paths':len(rows),'windows':len(self.windows),'output':str(out)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    Extractor().run(args.output.resolve())
