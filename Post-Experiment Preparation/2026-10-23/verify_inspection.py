"""Independent readback of selected original records and derived artifacts."""
from pathlib import Path
import bisect
import hashlib
import json
import os
import subprocess
import sys

D=Path(__file__).resolve().parent
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def rows(p):return [json.loads(x) for x in Path(p).read_bytes().splitlines() if x]

def main():
    count=0
    for manifest in ['inputs.json','geometry-inputs.json','selection-inputs.json']:
        for p,identity in load(D/manifest).items():
            assert Path(p).stat().st_size==identity['bytes'] and digest(p)==identity['sha256'],p
            count+=1
    for x in load(D/'selected-exports.json'):
        assert digest(D/x['export'])==digest(x['source'])==x['sha256']
    for link in load(D/'reuse-links.json'):
        for label in ['write','full_file_read']:
            r=link[label]; original=next(x for x in rows(r['journal']) if x['sequence']==r['sequence'])
            assert original['record_sha256']==r['record_sha256']
            if label=='full_file_read':
                assert original['offset']==0 and original['bytes']==link['bytes']
                assert original['returned_sha256']==original['content_sha256']==link['sha256']
            clocks=rows(Path(r['journal']).parent.parent/'clock-bridge.jsonl')
            times=[x['payload']['linux']['linux_monotonic_ns'] for x in clocks]
            i=bisect.bisect_left(times,original['monotonic_ns']);assert 0<i<len(clocks)
            expected=[clocks[i-1]['payload']['before']['sim_time'],clocks[i]['payload']['after']['sim_time']]
            assert expected==r['clock_bound']['sim_time']
        assert digest(link['checkpoint_file'])==digest(D/link['export'])==link['sha256']
    geometry=load(D/'geometry-inspection.json')
    import importlib.util
    import mujoco
    import numpy as np
    app=D.parents[1]/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
    spec=importlib.util.spec_from_file_location('readback_scene',app/'scene.py')
    scene=importlib.util.module_from_spec(spec);spec.loader.exec_module(scene)
    model=mujoco.MjModel.from_xml_string(scene.xml());data=mujoco.MjData(model)
    for x in geometry['examples']:
        with np.load(x['sample']['file']) as a:
            k=x['sample']['sample']
            assert a['t'][k]==x['sample']['t']
            assert np.array_equal(a['qpos'][k],x['qpos']) and np.array_equal(a['qvel'][k],x['qvel'])
        assert max(x['analytical_chain_residual_m'].values())<1e-10
        # The observer receives already transformed world geometry. Its vertex operation is R * local + position.
        frame=load(D/x['frame'])
        assert frame['sim_time']==x['sample']['t']
        assert frame['provenance']['sample']==k
        data.qpos[:]=x['qpos'];data.qvel[:]=x['qvel'];mujoco.mj_forward(model,data)
        for i,g in enumerate(frame['geoms']):
            assert np.array_equal(data.geom_xpos[i],g['position'])
            assert np.array_equal(data.geom_xmat[i],g['rotation'])
            assert np.array_equal(model.geom_size[i],g['size'])
            if g['type']==6:
                for corner in [(-1,-1,-1),(1,1,1),(1,-1,1),(-1,1,-1)]:
                    local=np.array(corner)*g['size'];r=g['rotation']
                    # Exact arithmetic order used by viewer.html vertices().
                    viewer=np.array([r[0]*local[0]+r[1]*local[1]+r[2]*local[2],
                                     r[3]*local[0]+r[4]*local[1]+r[5]*local[2],
                                     r[6]*local[0]+r[7]*local[1]+r[8]*local[2]])+g['position']
                    assert np.allclose(viewer,data.geom_xmat[i].reshape(3,3)@local+data.geom_xpos[i],atol=1e-12,rtol=0)
    roots={k:Path(v['root']) for k,v in load(D/'history-catalog.json').items()}
    video={}
    for label,root in roots.items():
        matches=[]
        for directory,_,files in os.walk(root):
            for name in files:
                if Path(name).suffix.lower() in ['.mp4','.mkv','.webm','.avi','.mov','.gif']:
                    matches.append(str(Path(directory)/name))
        video[label]={'searched_root':str(root),'recording_files':matches}
    result={'passed':True,'post_experiment_date':'2026-10-23','input_identity_checks':count,
            'byte_matched_cross_session_links':len(load(D/'reuse-links.json')),
            'original_image_exports':len(load(D/'selected-images.json')),
            'source_preservation':'All consumed original files rehashed unchanged; not a new full-root audit.',
            'video_inventory':video,'no_scientific_execution':True}
    (D/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
