"""Independent source/time/frame and actual decoded-video readback. Queue it."""
from pathlib import Path
import bisect,gzip,hashlib,json,re,subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
D=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_bytes().splitlines() if x]
def main():
    m=load(D/'source-timecode-manifest.json');v=m['video'];assert sha(v['path'])==v['sha256']
    out=D/'.local'/Path(v['path']).parent.name;out.mkdir(parents=True,exist_ok=True)
    checked=0
    for p,r in m['input_identities'].items():
        assert Path(p).stat().st_size==r['bytes'] and sha(p)==r['sha256'],p
        checked+=1
    for join in m['invocation_clock_joins']:
        original=next(r for r in rows(join['source']) if r['sequence']==join['capture_sequence'])
        assert original['record_sha256']==join['capture_record_sha256'] and original['message']['params']['argv']==join['argv']
        events=rows(Path(join['source']).parents[3]/'events.jsonl')
        a,b=[next(r for r in events if r['sequence']==n) for n in join['event_sequences']]
        assert [a['sha256'],b['sha256']]==join['event_sha256']
        assert a['wall_ns']<=round(original['wall_unix_s']*1e9)<=b['wall_ns']
        assert join['display_not_before']==b['sim_time']
    with gzip.open(D/'frame-sources.jsonl.gz','rt',encoding='utf-8') as f:frames=[json.loads(s) for s in f]
    assert len(frames)==v['frames']==3360 and v['duration_s']==140 and v['fps']==24
    cache={};max_age=0
    for n,r in enumerate(frames):
        assert r['output_frame']==n and r['output_time']==n/24
        shot=m['shots'][r['shot']];assert shot['start']<=n/24<shot['end']
        if shot['kind']=='replay':
            s=r['evidence'];p=s['source']
            if p not in cache:
                with np.load(p) as a:cache[p]=a['t'].copy()
            a=cache[p];assert float(a[s['sample']])==s['sim_time']
            assert max(0,bisect.bisect_right(a,s['requested_sim_time'])-1)==s['sample']
            assert s['sim_time']<=s['requested_sim_time']+1e-9
            # The historical recorder is approximately 50 Hz, not an exact 20 ms clock.
            # Require the actual retained predecessor, with no interpolation/extrapolation.
            if s['sample']+1<len(a):assert s['requested_sim_time']<float(a[s['sample']+1])
            max_age=max(max_age,s['age_s'])
        elif shot['kind']=='image':
            im=r['evidence']['image'];assert im['sequence']==shot['source']
    # Independently check every file panel's first actual recorded sample against its original upper clock bound.
    prep=D.parent;links=load(prep/'reuse-links.json')
    panels={'program':(0,'write'),'read1':(0,'full_file_read'),'defaults':(1,'write'),'read9':(1,'full_file_read'),
      'route':(3,'write'),'summary2':(2,'write'),'read2':(2,'full_file_read'),'readroute':(3,'full_file_read'),
      'mapsummary':(5,'write'),'readmapsummary':(5,'full_file_read'),'readmap':(6,'full_file_read'),'savemap':(6,'write')}
    bindings=[]
    for shot in m['shots']:
        name=shot.get('panel')
        if name not in panels:continue
        i,operation=panels[name];l=links[i];receipt=l[operation]
        first=frames[shot['output_frames'][0]]['evidence']['sim_time'];high=receipt['clock_bound']['sim_time'][1]
        assert first>=high,(name,first,high)
        original=next(r for r in rows(receipt['journal']) if r['sequence']==receipt['sequence'])
        assert original['record_sha256']==receipt['record_sha256']
        assert sha(l['checkpoint_file'])==sha(prep/l['export'])==l['sha256']
        bindings.append({'shot':shot['id'],'output_time':[shot['start'],shot['end']],'panel':name,
            'path':l['path'],'sha256':l['sha256'],'checkpoint_source':l['checkpoint_file'],
            'record_source':receipt['journal'],'record_sequence':receipt['sequence'],'record_sha256':receipt['record_sha256'],
            'original_sim_bracket':receipt['clock_bound']['sim_time'],'first_displayed_sample':first})
    (D/'cue-evidence-bindings.json').write_text(json.dumps(bindings,indent=2)+'\n',encoding='utf-8')
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    cmd=[ff,'-hide_banner','-i',v['path'],'-map','0:v:0','-vf','scale=320:180','-an','-f','framemd5','-']
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert p.returncode==0,p.stderr.decode(errors='replace')[-2000:]
    info=p.stderr.decode(errors='replace');(out/'decode.log').write_text(info,encoding='utf-8')
    (out/'decoded-frames.md5').write_bytes(p.stdout)
    decoded=[x for x in p.stdout.decode().splitlines() if x and not x.startswith('#')]
    assert len(decoded)==3360,len(decoded)
    assert 'Audio:' not in info and 'Video: h264' in info and '1920x1080' in info and '00:02:20.00' in info
    # Decode actual MP4 samples around every cut plus the middle of every shot, at phone landscape size.
    indexes=sorted({max(0,min(3359,int(t*24))) for s in m['shots'] for t in [s['start'],(s['start']+s['end'])/2,s['end']-1/24]})
    selected=out/'decoded';selected.mkdir(exist_ok=True)
    expression='+'.join('eq(n\\,'+str(n)+')' for n in indexes)
    cmd=[ff,'-hide_banner','-loglevel','error','-i',v['path'],'-vf',f'select={expression},scale=640:360','-fps_mode','vfr','-q:v','2',str(selected/'frame-%03d.jpg')]
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert p.returncode==0,p.stderr.decode()
    files=sorted(selected.glob('frame-*.jpg'));assert len(files)==len(indexes)
    qa=D/('qa-decoded-'+Path(v['path']).parent.name);qa.mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',23)
    for start in range(0,len(files),8):
        sheet=Image.new('RGB',(1280,4*394),(12,22,31));draw=ImageDraw.Draw(sheet)
        for j,p in enumerate(files[start:start+8]):
            x=(j%2)*640;y=(j//2)*394;sheet.paste(Image.open(p),(x,y+34))
            n=indexes[start+j];draw.text((x+10,y+3),f'MP4 decoded frame {n} • {n/24:.3f} video s',font=font,fill='white')
        sheet.save(qa/f'contact-{start//8:02}.jpg',quality=92)
    # Preserve useful single phone-size decoded frames for direct legibility checks.
    for target in [26,37,62,99,115,130,137]:
        k=min(range(len(indexes)),key=lambda j:abs(indexes[j]/24-target))
        Image.open(files[k]).save(qa/f'phone-{target:03}.jpg',quality=95)
    result={'passed':True,'video':v,'input_identity_checks':checked,'all_decoded_frames':len(decoded),
       'audio_streams':0,'codec':'H.264 / yuv420p','resolution':[1920,1080],'duration_s':140,
       'source_frames_authenticated':len(frames),'maximum_selected_sample_age_s':max_age,
       'file_panel_time_guards':len(bindings),'invocation_clock_joins':len(m['invocation_clock_joins']),
       'decoded_qa_frames':len(files),'qa_raster':[640,360],
       'actual_playback_review':'Separate browser/visual review still required; decoding and source validation alone do not establish watchability.'}
    (D/'video-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
