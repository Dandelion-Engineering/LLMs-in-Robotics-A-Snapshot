"""Register the first immutable proposed designs through the map's safe API."""
from datetime import datetime,timezone
import hashlib
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'Architecture Map'
spec=importlib.util.spec_from_file_location('architecture_map',ROOT/'map.py')
am=importlib.util.module_from_spec(spec);spec.loader.exec_module(am)

DESIGNS=[
('A1','Durable Task Dispatcher','Chooses each next typed task using current observations and retrieved consequential context.','LLM selects task motions; shared numerical executor supplies physical movement.','Journal, task projection and unresolved-request reconciliation.','Explicit task-level reconsideration after interruptions.','Boundary inference may cause pauses or poor sequencing.','https://say-can.github.io/','SayCan','arxiv:2204.01691'),
('A2','Guarded Procedure Composer','Generates bounded reactive procedures whose guards and steps execute between model calls.','LLM supplies procedure structure; deterministic DSL interpreter and shared motion executor act.','Versioned program, step checkpoint and unresolved-effect journal.','Local feedback handling can continue without a model call at every step.','Bad guards or stale procedures can repeatedly pursue the wrong behavior.','https://code-as-policies.github.io/','Code as Policies','arxiv:2209.07753'),
('A3','Grounded Objective Composer','Composes geometric objectives for a conventional durable scheduler and numerical motion planner.','Scheduler selects job; LLM defines transport geometry; numerical controller executes bounded trajectories.','Durable job transactions plus versioned sensed geometry and objective applicability.','Language may improve movement choices while fixed rules preserve job flow.','An unnecessary or poor geometric objective can add latency and reduce reliability.','https://voxposer.github.io/','VoxPoser','arxiv:2307.05973')]

def main():
    for short,title,summary,loop,continuity,strength,risk,url,source,paper in DESIGNS:
        aid='B01-'+short;rid=aid+'-r1';path=ROOT/'designs'/f'{rid}.md'
        now=datetime.now(timezone.utc).isoformat()
        common={'schema_version':'architecture-map-1.0','recorded_at':now,'author':'Codex session 4','tags':['batch-01','main-candidate','continuity',short], 'details':{}}
        architecture={**common,'id':aid,'title':title,'summary':summary,'details':{'batch_id':'B01','role':'main_candidate','literature_ids':[paper]}}
        revision={**common,'id':rid,'architecture_id':aid,'parent_revision_id':None,'status':'proposed','title':title+' — initial design','summary':summary,'mechanism':loop+' '+continuity+' Model proposals cannot certify physical completion. Restart reobserves current state and order; unresolved actions remain uncertain until sensor evidence supports reconciliation.','attachments':[{'label':'Complete mechanism design','uri':'designs/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'state':'available','access':'operator','locator':None}],'details':{'batch_id':'B01','role':'main_candidate','llm_role':summary,'control_loop':loop,'continuity':continuity,'expected_strength':strength,'failure_risk':risk,'implementation_status':'Proposed design snapshot. Runtime implementation and calibration proceed separately; no candidate performance attached.','sources':[{'label':source,'url':url},{'label':'Qwen3-4B official weights','url':'https://huggingface.co/Qwen/Qwen3-4B-GGUF'}],'literature_ids':[paper],'model_target':'Qwen3-4B-GGUF Q4_K_M; thinking disabled; exact runtime evidence separate','online_changes':'Own decisions/procedure/objective only; no evaluator/sensor/body changes','measurement_status':'No experimental outcome in this proposed revision'}}
        for kind,record in [('architecture',architecture),('revision',revision)]:
            data,raw,errors=am.read_store(ROOT)
            if errors:raise ValueError(errors)
            existing=next((r for r in data[kind] if r['id']==record['id']),None)
            if existing:
                if kind=='revision' and existing['attachments']!=record['attachments']:raise ValueError('Registered design attachment changed')
                continue
            am.append_record(ROOT,kind,record,am.store_digest(raw))
            print('Registered',record['id'])
    am.main(['build']);am.main(['validate','--output','validation.json'])

if __name__=='__main__':main()
