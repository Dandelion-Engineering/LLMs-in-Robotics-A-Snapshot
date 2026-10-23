"""Final read-only preservation, provenance and export checks; no model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request

HOME=Path(__file__).resolve().parent
sys.path.insert(0,str(HOME.parent))
from common import REPO,save,sha
import preservation


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def identity(path,expected):
    path=Path(path)
    assert path.stat().st_size==expected['bytes'] and sha(path)==expected['sha256'],str(path)


def run(manifest_path,audit,replay,output):
    manifest_path=Path(manifest_path).resolve();audit=Path(audit).resolve()
    replay=Path(replay).resolve();output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    manifest=read(manifest_path);episode=Path(manifest['output'])
    snapshot=read(manifest_path.parent/'snapshot.json')
    checks={};measurements={}
    for group in ('source','inherited'):
        for name,value in snapshot[group].items():identity(REPO/name,value)
        measurements[group+'_files']=len(snapshot[group])
    checks['all_frozen_campaign_and_inherited_source_bytes']=True
    inputs=read(audit/'assessment/input-identities.json')
    for name,value in inputs.items():identity(episode/name,value)
    measurements['original_episode_files']=len(inputs)
    checks['all_original_actual_evidence_bytes']=True
    preserved=read(HOME/'preservation-baseline-identity.json')
    assert sha(HOME.parent/'preservation-baseline.json')==preserved['baseline_sha256']
    preservation.verify(HOME.parent/'preservation-baseline.json',output/'historical-preservation.json')
    checks['all_historical_files_membership_and_map_prefixes']=True
    build=read(replay/'build.json');verification=read(replay/'verification.json')
    assert verification['passed'] and verification['source_manifest_sha256']==sha(manifest_path)
    assert verification['build_sha256']==sha(replay/'build.json')
    for name,value in build['sources'].items():identity(REPO/name,value)
    for name,value in build['outputs'].items():identity(replay/name,value)
    measurements['replay_output_files']=len(build['outputs'])
    checks['replay_source_and_every_output_identity']=True
    analysis=read(HOME/'evidence/observable-analysis.json')
    verified=read(HOME/'evidence/analysis-verification.json')
    assert verified['passed'] and verified['analysis_sha256']==sha(HOME/'evidence/observable-analysis.json')
    assert analysis['manifest_sha256']==sha(manifest_path)
    from audit_inventory import verify_inventory
    assert verify_inventory(audit/'assessment/raw/journal')==analysis['memory']['structural_inventory_audit']
    checks['corrected_analysis_identity_and_positive_read_attribution']=True
    public_files=read(HOME/'evidence/public-file-identities.json')
    for name,value in public_files.items():
        identity(HOME/'evidence'/name,value)
        node=analysis['artifacts']['final_inventory'][value['workspace_path']]
        assert node['sha256']==value['sha256'] and node['size']==value['bytes']
        assert value['journal_final_state_sha256']==analysis['artifacts']['final_state_sha256']
    checks['public_handoff_helper_and_notes_equal_closed_journal']=True
    measurements['exact_public_file_exports']=len(public_files)
    qa=read(HOME/'qa/browser-qa.json')
    assert qa['passed'] and qa['replay']==str(replay)
    for name,value in qa['screenshots'].items():identity(HOME/'qa'/name,value)
    checks['actual_browser_qa_and_screenshot_bytes']=True
    http_proofs={}
    for name in ('verification.json','inputs.json','build.json'):
        with urllib.request.urlopen('http://127.0.0.1:8765/'+name,timeout=10) as response:
            raw=response.read();status=response.status
        assert status==200 and hashlib.sha256(raw).hexdigest()==sha(replay/name)
        http_proofs[name]=dict(status=status,bytes=len(raw),sha256=sha(replay/name))
    save(output/'http-source-bytes.json',http_proofs)
    checks['loopback_source_links_exact_bytes']=True
    # The namespace-local facade value is fixed; host capabilities are revoked
    # and removed at clean retirement, so their old exact values are unavailable.
    # Do not misreport this as an exhaustive scan of unavailable host secrets.
    journal=audit/'assessment/raw/journal';tokens=set();endpoint_objects=set()
    for line in (journal/'mutations.jsonl').open(encoding='utf-8'):
        record=json.loads(line);state=record.get('state')
        if not state or '/live/endpoint.json' not in state['paths']:continue
        node=state['nodes'][str(state['paths']['/live/endpoint.json'])]
        if 'sha256' in node:
            endpoint_objects.add(node['sha256'])
            endpoint=read(journal/'objects'/node['sha256'])
            if endpoint.get('capability'):tokens.add(endpoint['capability'].encode())
    assert tokens and endpoint_objects
    packed=(replay/'objects.js').read_text(encoding='utf-8')
    for object_id in endpoint_objects:
        assert '"'+object_id+'":' not in packed,'Withheld endpoint object exported'
    export_paths=[p for p in replay.rglob('*') if p.is_file()]
    export_paths += [p for p in (HOME/'evidence').rglob('*') if p.is_file()]
    for path in export_paths:
        raw=path.read_bytes()
        assert not any(token in raw for token in tokens),'Capability content reached export: '+str(path)
    checks['retained_endpoint_objects_and_facade_value_absent_from_derived_exports']=True
    measurements.update(export_files_scanned=len(export_paths),
        retained_endpoint_objects_checked=len(endpoint_objects),
        token_scan_boundary='Only retained namespace-local facade values can be scanned exactly. Retired host capability values are unavailable; no exhaustive exact-value claim is made for them.',
        free_C_GiB=shutil.disk_usage('C:/').free/1024**3,
        free_D_GiB=shutil.disk_usage('D:/').free/1024**3)
    result=dict(passed=True,model_calls=0,checks=checks,measurements=measurements,
        manifest_sha256=sha(manifest_path),source_sha256=sha(__file__),
        replay_verification_sha256=sha(replay/'verification.json'),
        browser_qa_sha256=sha(HOME/'qa/browser-qa.json'),
        boundary='Read-only final provenance and preservation audit. Behavior, UI and scientific claims retain their separately stated boundaries.')
    save(output/'receipt.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('audit');p.add_argument('replay');p.add_argument('output')
    a=p.parse_args();run(a.manifest,a.audit,a.replay,a.output)
