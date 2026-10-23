"""Register the prepared comparison without launching or assessing either condition."""
import argparse
from pathlib import Path
from common import HERE,read,sha,save
from register import ARCH,base,ref,append

def recorded(*refs):return dict(state='recorded',refs=list(refs),reason=None)

def run(root):
    root=Path(root);prepared=read(root/'prepared.json');certificate=read(HERE/'commissioning.json')
    if prepared['official_launched'] or prepared['official_assignments_consumed']!=0 or not certificate['passed']:raise ValueError('Only clean commissioned starts may register')
    out=root/'registration';out.mkdir(exist_ok=False)
    revision='APARTMENT-v1-frozen'
    common={**base(revision),'tags':['apartment','frozen','paired-comparison','unlaunched']}
    append('revision',{**common,'architecture_id':ARCH,'parent_revision_id':'APARTMENT-dev028-revision','status':'frozen',
        'title':'Apartment v1 baseline and Maps controlled comparison',
        'summary':'One prepared hidden 21-assignment schedule; ordinary v0.2 versus its actual Maps Edition. Neither official condition has launched.',
        'mechanism':'Continuous MuJoCo apartment, RGB-D/lidar perception, physical household tasks and bounded throwing practice; time-only battery, physical charging, persistent isolated filesystem, original-state replay and deferred validated hibernation.',
        'attachments':[],'details':{'commissioning':ref('Commissioning certificate',HERE/'commissioning.json'),'prepared':ref('Clean two-condition preparation',root/'prepared.json')}},out)
    for condition in ('baseline','maps'):
        identifier='APARTMENT-v1-'+condition
        b={**base(identifier),'tags':['apartment','evaluation','prepared','unlaunched']}
        schedule=ref('Matched hidden assignment and variation manifest',root/'hidden-schedule.json','evaluator_only')
        cert=ref('Runtime model environment and calibrated parameters',HERE/'commissioning.json')
        append('run',{**b,'revision_id':revision,'stage':'evaluation','condition_id':condition,
            'protocol_id':'APARTMENT-v1','scenario_id':'apartment-procedural-1','paired_block_id':'APARTMENT-pair-001','replicate':1,
            'started_at':None,'rerun_of_run_id':None,'condition_details':dict(official_launched=False,assignments_consumed=0,condition=condition,order='baseline before Maps',battery=certificate['config']),
            'seeds':recorded(schedule),'frozen_refs':dict(code=recorded(ref('Frozen repository byte manifest',root/'frozen_repository/source-manifest.json')),
                environment=recorded(cert),models=recorded(cert),protocol=recorded(ref('Frozen comparison choices',root/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/COMPARISON.md')),
                scenario=recorded(schedule),initial_filesystem=recorded(ref('Pristine initial file inventory',root/condition/'initial-filesystem.json'))),
            'evidence':[ref('Preparation receipt',root/'prepared.json')]},out)
    append('note',{**base('APARTMENT-v1-commissioned-unlaunched'),'tags':['apartment','commissioning','not-performance'],
        'target_ids':[revision,'APARTMENT-v1-baseline','APARTMENT-v1-maps'],'claim_type':'observation',
        'body':'Apparatus commissioning passed the separately retained physical, native-session, continuation, sensor-boundary, frozen-bundle and browser/replay checks. All engineering attempts and failures remain outside both official starts. Both evaluation manifests are prepared and unlaunched; no terminal result or official performance claim exists. See commissioning audit for exact source correspondence and engineering-only task-boundary repairs.',
        'supersedes_note_id':None,'evidence':[ref('Independent commissioning readback',HERE/'commissioning-audit.json'),ref('Preparation receipt',root/'prepared.json')]},out)
    print('Registered frozen revision and two unlaunched evaluation manifests; no result was created.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();run(a.root)
