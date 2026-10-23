"""Observable handoff/index exposure and artifact activity, without causal claims."""
import hashlib
import json
from pathlib import Path
import stat
from audit_inventory import verify_inventory


def analyze_memory(journal, root, episode, artifacts, sessions):
    root, episode = Path(root), Path(episode)
    inventory_audit = verify_inventory(root)
    known_paths = sorted({c['path'] for c in artifacts['changes']
                          if c['path'].startswith(('/programs/','/notes/'))})
    summary = []
    for session in sessions:
        sid = session['session_id']
        boundary = artifacts['model_boundaries'][sid]
        start = boundary['inventory']
        def content(node):
            if not node or 'sha256' not in node:return None
            return (root/'objects'/node['sha256']).read_bytes().decode('utf-8',errors='replace')
        continuity = content(start.get('/.continuity/Continuity.md'))
        index = content(start.get('/ArtifactInventory.json'))
        reads = [r for r in artifacts['reads'] if r['session_id']==sid and r['model_runtime_read'] and r['bytes']>0]
        exposures = []
        for r in reads:
            if r['path'] not in ('/.continuity/Continuity.md','/ArtifactInventory.json'):continue
            raw=(root/'objects'/r['content_sha256']).read_bytes()[r['offset']:r['offset']+r['bytes']]
            assert hashlib.sha256(raw).hexdigest()==r['returned_sha256']
            text=raw.decode('utf-8',errors='replace')
            exposures.append({'sequence':r['sequence'],'path':r['path'],'offset':r['offset'],'bytes':len(raw),
                              'content_sha256':r['content_sha256'],'returned_sha256':r['returned_sha256'],
                              'returned_text':text,'artifact_paths_present_in_returned_bytes':[p for p in known_paths if p[1:] in text]})
        changes=[c for c in artifacts['changes'] if c['session_id']==sid and c['model_runtime_write'] and not c['apparatus_path']]
        request_path=episode/sid/'executor-2-requests.jsonl'
        commands=[]
        for line,raw in enumerate(request_path.read_text(encoding='utf-8').splitlines(),1):
            record=json.loads(raw)
            if record.get('method')!='process/start':continue
            params=record.get('params') or {}
            # Retain only public requested program/arguments, not environment
            # configuration, auth or executor transport envelopes.
            command={k:params[k] for k in ('command','args','argv','program','executable','processId','cwd') if k in params}
            encoded=json.dumps(command)
            commands.append({'source':sid+'/executor-2-requests.jsonl:'+str(line),'request':command,
                             'artifact_path_mentions':[p for p in known_paths if p[1:] in encoded]})
        summary.append({'session_id':sid,'occurrence':session['occurrence'],
            'continuity_visible_at_start':continuity,'inventory_visible_at_start':json.loads(index),
            'continuity_model_read':any(r['path']=='/.continuity/Continuity.md' for r in reads),
            'inventory_model_read':any(r['path']=='/ArtifactInventory.json' for r in reads),
            'historical_surface_exposures':exposures,
            'durable_artifact_reads':[r for r in reads if r['path'].startswith(('/programs/','/notes/')) and not r['apparatus_path']],
            'model_content_changes':changes,'public_process_requests':commands,
            'semantic_assessment_boundary':'Path mentions are observable exposure, not proof of semantic use. A process request is an execution request; completion and useful behavior require tool/physical receipts. Interpret purpose, limitations, adaptation and usefulness from the original public content, separately from these mechanical fields.'})
    return {'structural_inventory_audit':inventory_audit,'sessions':summary,
            'evidence_levels':['existence','discoverability/indexing','read','execution','semantic reuse/adaptation','useful transfer','causal contribution'],
            'causal_contribution':'unknown; no memory-withholding comparison was authorized'}
