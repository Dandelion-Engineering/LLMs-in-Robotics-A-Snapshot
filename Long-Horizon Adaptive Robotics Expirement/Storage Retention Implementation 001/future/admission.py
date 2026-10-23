"""Measured campaign projection, finite lifetime ceiling, and fail-closed release gate."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sqlite3
import shutil
from datetime import datetime,timezone
from pathlib import Path

GB = 1_000_000_000
EXPECTED_EVIDENCE_ROOT=Path(__file__).resolve().parents[2]
CAPACITY_SCOPE='whole-experiment-logical-bytes-v1'


def nonnegative_int(value,label):
    if type(value) is not int or value<0: raise ValueError(label+' must be a nonnegative integer')
    return value


def positive_number(value,label):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError(label+' must be a finite positive number')
    return value


def is_reparse(path):
    return bool(getattr(Path(path).lstat(),'st_file_attributes',0)&0x400) or Path(path).is_symlink()


def project_images(*, measured_pair_bytes, task_seconds=156600, runs=264,
                   representative_runs=12, representative_seconds_each=600,
                   representative_hz=2, sparse_period_s=30, campaign_trigger_windows=128,
                   trigger_pre_post_s=5, trigger_hz=10):
    """Conservative frame count: overlap is NOT discounted. All pairs cost measured max."""
    if measured_pair_bytes<=0: raise ValueError('Measured encoded pair size required')
    counts={'representative':math.ceil(representative_runs*representative_seconds_each*representative_hz),
            'sparse':math.ceil(task_seconds/sparse_period_s)+runs,
            'triggered':math.ceil(campaign_trigger_windows*(trigger_pre_post_s*trigger_hz+1))}
    categories={key:{'pairs':count,'bytes':count*measured_pair_bytes} for key,count in counts.items()}
    return {'measured_max_pair_bytes':measured_pair_bytes,'categories':categories,
            'projected_encoded_bytes':sum(v['bytes'] for v in categories.values()),
            'metadata_allowance_bytes':math.ceil(task_seconds*10)*200,
            'budget_bytes':6*GB,'policy':{'representative_runs':representative_runs,
            'representative_seconds_each':representative_seconds_each,'representative_hz':representative_hz,
            'sparse_period_s':sparse_period_s,'campaign_trigger_windows':campaign_trigger_windows,
            'trigger_pre_post_s':trigger_pre_post_s,'trigger_hz':trigger_hz}}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capacity_from_retention(source_path,receipt_path):
    """Derive exact whole-EXP total from the root workflow's successful census."""
    source_path,receipt_path=map(Path,(source_path,receipt_path))
    source=json.loads(source_path.read_text(encoding='utf-8')); receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if source.get('schema')!='retention-census-1' or Path(source['root']).resolve()!=EXPECTED_EVIDENCE_ROOT.parent:
        raise ValueError('Wrong retention census schema/root')
    if source.get('errors') or source.get('skipped'): raise ValueError('Incomplete retention census')
    if receipt.get('state')!='succeeded' or type(receipt.get('exit_status')) is not int or receipt['exit_status']!=0:
        raise ValueError('Official successful census queue receipt required')
    argv=receipt.get('argv',[])
    if 'census' not in argv or '--name' not in argv or argv[argv.index('--name')+1]!=source_path.parent.name:
        raise ValueError('Queue receipt does not identify this census')
    prefix=EXPECTED_EVIDENCE_ROOT.name+'/'
    areas={key:value for key,value in source['counts'].items() if key.startswith(prefix)}
    if prefix+'Evidence' not in areas: raise ValueError('Missing Evidence area in complete census')
    for count,size in areas.values(): nonnegative_int(count,'census count'); nonnegative_int(size,'census size')
    return {'schema_version':'storage-capacity-census-1','observed_at':source['finished'],
        'evidence_root':str(EXPECTED_EVIDENCE_ROOT),'scope_policy':CAPACITY_SCOPE,
        'evidence_bytes':sum(v[1] for v in areas.values()),'files':sum(v[0] for v in areas.values()),
        'source_census':{'path':str(source_path.resolve()),'sha256':sha(source_path)},
        'source_queue_receipt':{'path':str(receipt_path.resolve()),'sha256':sha(receipt_path)},
        'scope':'Conservative logical whole EXP including code, models and repeated hardlink path accounting'}


def verified_capacity(spec):
    """Fresh volume capacity + authenticated, recent evidence census. Never guess."""
    binding=spec['evidence_census']; path=Path(binding['path'])
    if sha(path)!=binding['sha256']: raise ValueError('Evidence census hash changed')
    census=json.loads(path.read_text(encoding='utf-8'))
    if census.get('schema_version')!='storage-capacity-census-1': raise ValueError('Unsupported capacity census')
    root=Path(census['evidence_root'])
    if not root.is_dir() or root.resolve()!=EXPECTED_EVIDENCE_ROOT or is_reparse(root):
        raise ValueError('Census must cover the canonical experiment evidence root')
    if census.get('scope_policy')!=CAPACITY_SCOPE: raise ValueError('Capacity census scope is incomplete or unrecognized')
    if 'source_census' in census or 'source_queue_receipt' in census:
        for key in ('source_census','source_queue_receipt'):
            if sha(census[key]['path'])!=census[key]['sha256']: raise ValueError('Capacity source provenance changed')
        derived=capacity_from_retention(census['source_census']['path'],census['source_queue_receipt']['path'])
        if any(census.get(key)!=derived[key] for key in ('evidence_bytes','files','observed_at','evidence_root','scope_policy')):
            raise ValueError('Derived capacity differs from exact source census')
    observed=datetime.fromisoformat(census['observed_at'])
    age=(datetime.now(timezone.utc)-observed).total_seconds()
    if not 0<=age<=3600: raise ValueError('Evidence census is stale or from the future; repeat queued census')
    output=Path(spec['output_directory']).resolve()
    if not output.is_dir() or not output.is_relative_to(EXPECTED_EVIDENCE_ROOT):
        raise ValueError('Output directory must exist within counted experiment scope')
    value=nonnegative_int(census['evidence_bytes'],'evidence bytes')
    return {'evidence_bytes':value,'free_bytes':shutil.disk_usage(output).free,
        'observed_at':datetime.now(timezone.utc).isoformat(),'output_directory':str(output),
        'evidence_census':binding,'census_age_s':age}


def write_capacity_census(evidence_root,output):
    """Run through the shared queue for large evidence trees; source metadata only."""
    import os
    supplied=Path(evidence_root)
    if not supplied.is_dir() or is_reparse(supplied): raise ValueError('Existing ordinary evidence directory required')
    root=supplied.resolve(); total=0; count=0
    if root!=EXPECTED_EVIDENCE_ROOT: raise ValueError('Census must cover canonical experiment evidence root')
    def refuse(error): raise error
    for directory,dirs,files in os.walk(root,onerror=refuse,followlinks=False):
        if any(is_reparse(Path(directory)/name) for name in dirs): raise ValueError('Census refuses reparse subtree')
        for name in files:
            path=Path(directory)/name
            if is_reparse(path): raise ValueError('Census refuses reparse file')
            total+=path.stat().st_size; count+=1
    report={'schema_version':'storage-capacity-census-1','observed_at':datetime.now(timezone.utc).isoformat(),
            'evidence_root':str(root),'evidence_bytes':total,'files':count,
            'scope_policy':CAPACITY_SCOPE,
            'scope':'Logical-byte metadata census; require no concurrent evidence writer during admission'}
    Path(output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); return report


def verify_qualification_receipt(report,receipt):
    if (report.get('schema_version')!='future-recorder-qualification-1' or
        report.get('tests',{}).get('passed') is not True or
        type(report.get('tests',{}).get('run')) is not int or report['tests']['run']<1):
        raise ValueError('Successful complete qualification schema/tests required')
    if (receipt.get('state')!='succeeded' or type(receipt.get('exit_status')) is not int or
        receipt['exit_status']!=0 or not isinstance(receipt.get('id'),str) or not receipt['id']):
        raise ValueError('Successful identified queue receipt required')
    cwd=Path(receipt.get('cwd','')).resolve()
    if cwd!=EXPECTED_EVIDENCE_ROOT.parent: raise ValueError('Qualification queue cwd mismatch')
    argv=receipt.get('argv',[]); expected=Path(__file__).resolve().parent/'qualify.py'
    scripts=[(i,Path(value)) for i,value in enumerate(argv) if isinstance(value,str) and value.endswith('.py')]
    if len(scripts)!=1: raise ValueError('Qualification command must identify exactly one script')
    index,script=scripts[0]
    if not script.is_absolute(): script=cwd/script
    if script.resolve()!=expected: raise ValueError('Queue receipt does not execute the current qualifier')
    if argv[index+1:]!=['--generation',report.get('generation')]:
        raise ValueError('Qualification generation/arguments mismatch')
    if report.get('queue_job_id',receipt['id'])!=receipt['id']: raise ValueError('Qualification job identity mismatch')
    times=[datetime.fromisoformat(value) for value in
           (receipt['started_at'],report['created_at'],receipt['ended_at'])]
    if any(value.tzinfo is None for value in times) or not times[0]<=times[1]<=times[2]:
        raise ValueError('Qualification report was not completed within queue execution')


def bind_qualification(report_path, receipt_path, seal_path):
    report_path,receipt_path,seal_path=map(Path,(report_path,receipt_path,seal_path))
    report=json.loads(report_path.read_text(encoding='utf-8')); receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    verify_qualification_receipt(report,receipt)
    for name,expected in report['implementation_hashes'].items():
        if sha(report_path.parent/name)!=expected: raise ValueError('Implementation changed after qualification: '+name)
    for name,expected in report.get('source_hashes',{}).items():
        if sha(EXPECTED_EVIDENCE_ROOT/name)!=expected: raise ValueError('Frozen component source changed: '+name)
    image_binding=report.get('image_input_binding')
    if image_binding and sha(EXPECTED_EVIDENCE_ROOT/image_binding['path'])!=image_binding['sha256']:
        raise ValueError('Frozen retained image inputs changed')
    seal={'schema_version':'qualification-binding-1','report_sha256':sha(report_path),
          'queue_receipt_sha256':sha(receipt_path),'queue_job_id':receipt['id'],
          'implementation_hashes':report['implementation_hashes'],'source_hashes':report.get('source_hashes',{}),
          'image_input_binding':image_binding}
    seal_path.write_text(json.dumps(seal,indent=2)+'\n',encoding='utf-8'); return seal


def load_bound_qualification(report_path,receipt_path,seal_path):
    report_path,receipt_path,seal_path=map(Path,(report_path,receipt_path,seal_path))
    seal=json.loads(seal_path.read_text(encoding='utf-8')); report=json.loads(report_path.read_text(encoding='utf-8'))
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if sha(report_path)!=seal['report_sha256'] or sha(receipt_path)!=seal['queue_receipt_sha256']:
        raise ValueError('Qualification or queue receipt changed')
    verify_qualification_receipt(report,receipt)
    if seal.get('queue_job_id')!=receipt['id']: raise ValueError('Qualification seal job identity mismatch')
    for name,expected in seal['implementation_hashes'].items():
        if sha(report_path.parent/name)!=expected: raise ValueError('Stale qualification source binding: '+name)
    for name,expected in seal.get('source_hashes',{}).items():
        if sha(EXPECTED_EVIDENCE_ROOT/name)!=expected: raise ValueError('Stale frozen component source binding: '+name)
    image_binding=seal.get('image_input_binding')
    if image_binding and sha(EXPECTED_EVIDENCE_ROOT/image_binding['path'])!=image_binding['sha256']:
        raise ValueError('Stale retained image input binding')
    return report


class CampaignReservations:
    """Durable cap ledger. Reserve complete per-run maxima before any run starts.

    An existing reservation is immutable. Reuse of a run ID fails. No automatic
    release/deletion of historical reservations can manufacture spare capacity.
    """
    def __init__(self,path,*,core_bytes,image_bytes=6*GB,trigger_windows=128):
        for key,value in [('core',core_bytes),('image',image_bytes),('windows',trigger_windows)]: nonnegative_int(value,key)
        self.db=sqlite3.connect(path)
        self.db.executescript('CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY,value INTEGER);'
          'CREATE TABLE IF NOT EXISTS reservations(run_id TEXT PRIMARY KEY,core INTEGER,image INTEGER,windows INTEGER);')
        expected={'core':core_bytes,'image':image_bytes,'windows':trigger_windows}
        existing=dict(self.db.execute('SELECT key,value FROM limits'))
        if existing and existing!=expected: self.db.close(); raise ValueError('Campaign limits are immutable')
        if not existing: self.db.executemany('INSERT INTO limits VALUES(?,?)',expected.items()); self.db.commit()
        self.limits=expected
    def allocate(self,run_id,*,core_bytes,image_bytes,trigger_windows):
        values=(core_bytes,image_bytes,trigger_windows)
        if any(type(v) is not int or v<0 for v in values): raise ValueError('Invalid campaign allocation')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            used=self.db.execute('SELECT COALESCE(SUM(core),0),COALESCE(SUM(image),0),COALESCE(SUM(windows),0) FROM reservations').fetchone()
            if any(used[i]+values[i]>self.limits[key] for i,key in enumerate(('core','image','windows'))):
                raise ValueError('Campaign reservation exceeds declared cap')
            self.db.execute('INSERT INTO reservations VALUES(?,?,?,?)',(run_id,*values)); self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return {'run_id':run_id,'core_quota_bytes':core_bytes,'image_quota_bytes':image_bytes,
                'maximum_trigger_windows':trigger_windows}
    def close(self): self.db.close()


def project(pilots, *, task_seconds=156600, runs=264, image_budget_bytes=6*GB,
            compact_bytes=GB, derived_bytes=4*GB, development_bytes=2*GB,
            uncertainty_fraction=.25, temporary_bytes=2*GB, image_projection=None):
    if not pilots: raise ValueError('Measured pilots required')
    positive_number(task_seconds,'task seconds'); nonnegative_int(runs,'runs')
    for key,value in [('images',image_budget_bytes),('compact',compact_bytes),('derived',derived_bytes),
                      ('development',development_bytes),('temporary',temporary_bytes)]: nonnegative_int(value,key)
    if type(uncertainty_fraction) not in (int,float) or not math.isfinite(uncertainty_fraction) or uncertainty_fraction<0:
        raise ValueError('Invalid uncertainty fraction')
    for p in pilots:
        positive_number(p['task_seconds'],'pilot task seconds'); positive_number(p['database_core_bytes'],'pilot bytes')
    rate = max(p['database_core_bytes']/p['task_seconds'] for p in pilots)
    core = math.ceil(rate*task_seconds) + runs*262144
    image_bytes = image_budget_bytes if image_projection is None else max(image_budget_bytes,
        image_projection['projected_encoded_bytes']+image_projection['metadata_allowance_bytes'])
    permanent = core + image_bytes + compact_bytes + derived_bytes + development_bytes
    peak = math.ceil(permanent*(1+uncertainty_fraction)) + temporary_bytes
    return {'schema_version':'storage-projection-1', 'task_seconds':task_seconds, 'runs':runs,
        'measured_max_core_bytes_per_task_second':rate, 'projected_core_bytes':core,
        'image_allowance_bytes':image_bytes, 'image_projection':image_projection, 'compact_allowance_bytes':compact_bytes,
        'derived_allowance_bytes':derived_bytes, 'development_allowance_bytes':development_bytes,
        'permanent_bytes':permanent, 'uncertainty_fraction':uncertainty_fraction,
        'temporary_bytes':temporary_bytes, 'peak_bytes_with_headroom':peak,
        'target_30GB_met':permanent <= 30*GB, 'ceiling_40GB_met':peak <= 40*GB,
        'basis':'maximum measured pilot core rate; fixed bounded image/package budgets; not a completed full campaign'}


def admit(projection, *, evidence_bytes, free_bytes, qualification, outstanding_reserved_bytes=0):
    for key,value in [('evidence bytes',evidence_bytes),('free bytes',free_bytes),('reserved bytes',outstanding_reserved_bytes),
                      ('projected permanent',projection['permanent_bytes']),('projected peak',projection['peak_bytes_with_headroom'])]:
        nonnegative_int(value,key)
    if projection['peak_bytes_with_headroom']<projection['permanent_bytes']: raise ValueError('Peak below permanent footprint')
    reasons = []
    peak = projection['peak_bytes_with_headroom']
    if peak > 40*GB: reasons.append('40 GB campaign admission ceiling exceeded')
    if evidence_bytes + outstanding_reserved_bytes + projection['permanent_bytes'] > 150*GB:
        reasons.append('150 GB project evidence ceiling exceeded')
    if free_bytes - outstanding_reserved_bytes - peak < 100*GB:
        reasons.append('100 GB free reserve would not survive campaign peak')
    for key in ('semantic_exact', 'diagnostics_equivalent', 'continuity_equivalent',
                'image_policy_qualified', 'runtime_timing_qualified', 'frozen_release_bound'):
        if qualification.get(key) is not True: reasons.append('Missing qualification: ' + key)
    return {'admitted':not reasons, 'reasons':reasons, 'projection':projection,
            'evidence_bytes_before':evidence_bytes, 'free_bytes_before':free_bytes,
            'outstanding_reserved_bytes':outstanding_reserved_bytes,
            'action':'proceed only under separate experiment authorization' if not reasons else 'reject large batch'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('input',type=Path); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--qualification',type=Path,required=True); parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--seal',type=Path,required=True)
    args = parser.parse_args(); spec = json.loads(args.input.read_text(encoding='utf-8'))
    qualified=load_bound_qualification(args.qualification,args.receipt,args.seal)
    capacity=verified_capacity(spec)
    report = admit(qualified['projection'], evidence_bytes=capacity['evidence_bytes'], free_bytes=capacity['free_bytes'],
                   qualification=qualified['qualification'], outstanding_reserved_bytes=spec.get('outstanding_reserved_bytes',0))
    report['capacity_observation']=capacity
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if report['admitted'] else 2)
