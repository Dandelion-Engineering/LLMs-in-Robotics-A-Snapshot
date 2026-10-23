"""Preserve terminal-host lifecycle limitations and report additional actual traces."""
import argparse
from pathlib import Path
import json
from assess_bootstrap import parsed_objects, read_json, sha
from assess_smoke import jsonl, simple_cat_paths


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('assessment','evidence','host-evidence','queue-receipt','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    receipt=read_json(args.queue_receipt)
    job=receipt.get('job',receipt)
    if job.get('state')!='succeeded' or job.get('exit_status')!=0:
        raise ValueError('Successful official receipt required before evidence reads')
    primary=read_json(args.assessment)
    if primary['queue_job_id']!=job['id']:
        raise ValueError('Queue/assessment mismatch')
    changed=[name for name,digest in primary['evidence_sha256'].items() if sha(Path(name).read_bytes())!=digest]
    if changed:
        raise ValueError('Evidence changed since primary assessment: '+str(changed))
    root=args.evidence/'pilot'
    events=jsonl(root/'client/events.jsonl')
    completed=[e['params']['item'] for e in events if e.get('method')=='item/completed'
               and e.get('params',{}).get('item',{}).get('type')=='commandExecution']
    hashes=read_json(root/'runtime-input-hashes.json')
    empty=[]
    for item in completed:
        if (item.get('exitCode')==0 and item.get('aggregatedOutput') is None
            and simple_cat_paths(item)=={'Continuity.md'} and hashes.get('Continuity.md')==sha(b'')):
            deltas=[e for e in events if 'outputDelta' in e.get('method','')
                    and e.get('params',{}).get('itemId')==item['id']]
            empty.append({'item_id':item['id'],'exit_code':0,'aggregated_output_representation':None,
                          'output_delta_events':len(deltas),'initial_input_sha256':hashes['Continuity.md'],
                          'interpretation':'Successful exact cat of the known initially empty file, with null aggregate and no output-delta records. This is command/read evidence; the null representation is not a recorded byte string for direct SHA comparison.'})
    initial=read_json(root/'canary-stdout.json')
    canaries=[]
    for item in completed:
        if item.get('exitCode')!=0 or '/canary.py' not in item.get('command',''):
            continue
        for obj in parsed_objects(item.get('aggregatedOutput') or ''):
            if (obj.get('qualified') is True and len(obj.get('checks',{}))==45
                and set(obj['checks'])==set(initial['checks']) and all(v is True for v in obj['checks'].values())):
                canaries.append({'item_id':item['id'],'qualified':True,'checks_passed':45,
                                 'complete_tool_output_sha256':sha(item['aggregatedOutput'].encode()),
                                 'retained_in':'client/events.jsonl','separate_named_agent_note_required':False})
    broker=jsonl(root/'broker-events.jsonl')
    handbacks=[e for e in broker if e.get('method')=='POST' and e.get('path')=='/handback'
               and e.get('status')==200 and e.get('response',{}).get('owner')=='conventional'
               and e.get('response',{}).get('command',{}).get('status')=='completed']
    denied=[e for e in broker if handbacks and e.get('wall_unix_s',0)>handbacks[-1]['wall_unix_s']
            and e.get('status')==403 and e.get('response',{}).get('error',{}).get('code')=='unauthorized']
    history=jsonl(args.host_evidence/'public-history.jsonl')
    stops=[e for e in history if e.get('type')=='episode_stopped']
    stage=read_json(root/'stage-result.json')
    sequence=read_json(args.evidence/'sequence-result.json')
    result={
        'schema':'robot-codex-pilot-terminal-lifecycle-supplement-1',
        'run_id':primary['run_id'],'queue_job_id':job['id'],
        'primary_assessment_sha256':sha(args.assessment.read_bytes()),'primary_evidence_hashes_still_match':True,
        'unchanged_unfulfilled_strict_checks':[key for key,value in primary['checks'].items() if not value],
        'independent_task_outcome':primary['recovery_and_task_outcome']['independent_task_outcome'],
        'protected_handback_epoch_transition':primary['recovery_and_task_outcome']['accepted_handback_corresponds_to_owner_transfer'],
        'actual_post_handback_authority_denials':[{'method':e['method'],'path':e['path'],'status':e['status'],
             'wall_unix_s':e['wall_unix_s'],'error':e['response']['error']} for e in denied],
        'host_terminal_events':[{'event_id':e['event_id'],'reason':e['payload']['reason'],'wall_unix_s':e['wall_unix_s'],'authority_epoch':e['authority_epoch']} for e in stops],
        'host_exit_code':sequence.get('host_exit_code'),
        'late_launcher_errors':{k:stage[k] for k in ('retirement_error','old_token_check_error') if k in stage},
        'all_actual_namespaces_retired':primary['checks']['all_namespace_retirements_observed'],
        'raw_bytes_retained_across_cleanup':primary['checks']['actual_file_bytes_durable_across_cleanup'],
        'actual_model_canaries_in_retained_tool_trace':canaries,
        'initial_empty_continuity_read_trace':empty,
        'interpretation':'Protected handback revoked robot authority and an actual later continuity mutation received HTTP403 unauthorized. The host naturally ended at task_success before launcher cleanup, so late operator retirement and old-token probe saw connection refusal. Physical namespace retirement and raw retention were observed. These corroborate completed recovery and authority revocation but do not replace the missing explicit lifecycle retirement receipt or late403 probe. The strict primary checks remain false; successful-host-shutdown bookkeeping needs a separately revised and qualified path before a broader readiness claim.',
        'model_calls_in_supplement':0,
        'supplement_code_sha256':sha(Path(__file__).read_bytes()),
    }
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'task_outcome':result['independent_task_outcome'],'actual_model_canaries':len(canaries),
                      'post_handback_403':len(denied),'strict_checks_preserved_false':result['unchanged_unfulfilled_strict_checks']}))


if __name__=='__main__':main()
