"""Caption-led presentation of original sampled states. Never runs task dynamics.

Use the shared compute queue. All source access is read-only. Each output version
uses a new directory; historical outputs and the approved script are untouched.
"""
from pathlib import Path
import argparse,bisect,collections,gzip,hashlib,importlib.util,json,math,subprocess,sys,textwrap,time
import numpy as np
import mujoco
from PIL import Image,ImageDraw,ImageFont,ImageOps
import imageio_ffmpeg

HERE=Path(__file__).resolve().parent
PREP=HERE.parent
REPO=PREP.parents[1]
APP=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
ROOTS={'baseline':Path('D:/Dandelion Engineering/LLMs in Robotics/Dandelion-Apartment-Experiment/official/apartment-v4/baseline'),
       'maps':Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Local Experiment Data/apartment-v4-maps/recovery-session63/recovered-run')}
W,H,FPS,DURATION=1920,1080,24,140
IDENTITIES={}
def digest(b):return hashlib.sha256(b).hexdigest()
def take(p):
    p=Path(p);b=p.read_bytes();identity={'bytes':len(b),'sha256':digest(b)}
    assert IDENTITIES.setdefault(str(p),identity)==identity,p
    return b
def load(p):return json.loads(take(p))
def rows(p):return [json.loads(x) for x in take(p).splitlines() if x]
def write(p,value):Path(p).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

CAPTIONS=[
 (0,3,'A new session. Not a blank slate.'),
 (3,8,'An AI agent worked in a simulated apartment, with files that persisted between sessions.'),
 (8,13,'Could it carry unfinished work, notes, and programs forward?'),
 (13,17,'Here are three documented examples.'),
 (17,24,'It tried a throw, got feedback, and kept experimenting.'),
 (24,32,'Then it saved a throwing program.'),
 (32,41,'A later session read the same file, reused it, and tuned its parameters.'),
 (41,49,'Session 9 read that revised version and ran it again.'),
 (49,56,'Two toys put away. Two still to go.'),
 (56,64,'The session saved its route and its unfinished work.'),
 (64,71,'The next session read those files and continued.'),
 (71,77,'It finished the remaining toys.'),
 (77,85,'The cup slipped. The task was not finished.'),
 (85,94,'It recovered the cup, staged it, and saved what remained.'),
 (94,97,'An infrastructure failure interrupted the run.'),
 (97,103,'Randy directed a restore to checkpoint 5. The failed original session-6 tail was excluded.'),
 (103,112,'The restarted session read the saved files and resumed the task.'),
 (112,119,'The recorded task check passed after placement.'),
 (119,127,'Saved files persisted. Later sessions read them. Programs were reused.'),
 (127,134,'The arm uses simulated joints but omits physical connecting structures. These results belong to that simplified model.'),
 (134,140,'Evidence of continuity, not proof that memory caused better performance.\nExplore the decisions, code, and evidence in the project record.')]
STORIES=[(17,49,'1 • A program survives the session'),(49,77,'2 • Pick up the remaining work'),(77,119,'3 • Recover, save, resume')]

def shots():
    # Every state frame selects an earlier actual sample; no interpolated world state.
    def s(a,b,kind,condition=None,session=None,source=None,**kw):
        return dict(start=a,end=b,kind=kind,condition=condition,session=session,source=source,**kw)
    return [
      s(0,3,'replay','baseline',1,[24.364,24.364],camera='wide',note='Held sample • opening'),
      s(3,8,'replay','baseline',1,[130,135],camera='throw'),
      s(8,13,'diagram',note='Session 1 → Saved files → Later session'),
      s(13,17,'replay','baseline',1,[856.024,856.024],camera='robot',panel='intro',note='Preview • Simplified simulated robot • not real-hardware validation'),
      s(17,20.5,'replay','baseline',1,[154,160.5],camera='throw',panel='miss',note='First trial'),
      s(20.5,24,'replay','baseline',1,[232,238.5],camera='throw',panel='hit',note='Time jump • later trial'),
      s(24,28,'replay','baseline',1,[415,419],camera='robot',panel='program',note='Time jump • verified program write'),
      s(28,32,'replay','baseline',1,[446.5,451],camera='throw',panel='run1',motion_fraction=.55,note='Time jump • saved program in use'),
      s(32,35,'replay','baseline',6,[3638.88,3638.88],camera='robot',panel='read1',note='Later: Session 6 • held sample'),
      s(35,39,'replay','baseline',6,[4104,4108.5],camera='throw',panel='run6',motion_fraction=.55,note='Time jump • explicit parameter trial'),
      s(39,41,'replay','baseline',6,[4188,4188],camera='robot',panel='defaults',note='Time jump • defaults edited after trials'),
      s(41,44,'replay','baseline',9,[6124.68,6124.68],camera='robot',panel='read9',note='Later: Session 9 • held sample'),
      s(44,49,'replay','baseline',9,[6296,6300],camera='throw',panel='run9',motion_fraction=.6,note='Time jump • revised program in use'),
      s(49,56,'image','baseline',2,34,note='Session 2 • held original frame'),
      s(56,60,'replay','baseline',2,[1475.24,1475.24],camera='robot',panel='route',note='Time jump • saved route • held sample'),
      s(60,64,'replay','baseline',2,[1565.36,1565.36],camera='robot',panel='summary2',note='Time jump • saved unfinished work'),
      s(64,67,'replay','baseline',3,[1694.82,1694.82],camera='robot',panel='read2',note='New session: 3 • held sample'),
      s(67,71,'replay','baseline',3,[1703.04,1707.04],camera='robot',panel='readroute',note='Route read, then fresh state'),
      s(71,73,'replay','baseline',3,[1871,1875],camera='chest',note='Time jump • red placement'),
      s(73,75.5,'replay','baseline',3,[1954.5,1959.5],camera='chest',panel='toysuccess',note='Time jump • yellow placement'),
      s(75.5,77,'image','baseline',3,66,note='Held original frame • after placement'),
      s(77,81,'replay','maps',5,[3170,3177],camera='cup',note='Session 5 • loss of contact'),
      s(81,85,'image','maps',5,146,note='Time jump • held original floor view'),
      s(85,89,'replay','maps',5,[3205,3218],camera='cup',note='Time jump • pickup and recovery'),
      s(89,91,'image','maps',5,150,note='Time jump • held cabinet-top view'),
      s(91,92.5,'replay','maps',5,[3422.14,3422.14],camera='robot',panel='savemap',note='Time jump • saved kitchen map'),
      s(92.5,94,'replay','maps',5,[3422.14,3422.14],camera='robot',panel='mapsummary',note='Saved unfinished work • held sample'),
      s(94,97,'pause',note='Intentional pause • no continuous-motion claim'),
      s(97,103,'authority',note='87-minute wall-time interruption'),
      s(103,106,'replay','maps',6,[3463.38,3463.38],camera='robot',panel='readmapsummary',note='Accepted continuation: Session 6 • held sample'),
      s(106,108,'replay','maps',6,[3483.84,3483.84],camera='robot',panel='readmap',note='Room map read • held sample'),
      s(108,110,'image','maps',6,165,note='Time jump • drawer B opened'),
      s(110,112,'image','maps',6,170,note='Time jump • cup held above drawer'),
      s(112,119,'image','maps',6,171,panel='cupsuccess',note='After release • held original frame'),
      s(119,127,'chain',note='Editorial summary of the three documented stories'),
      s(127,134,'replay','baseline',1,[524.288,524.288],camera='arm',panel='limitation',note='Time jump • representative original state'),
      s(134,140,'end',note='Editorial closing card')]

class Evidence:
    def __init__(self):
        self.script=take(PREP/'VIDEO-SCRIPT.md').decode('utf-8')
        for _,_,c in CAPTIONS:
            for line in c.splitlines():
                if 'failed original session-6 tail' in line:continue
                assert line in self.script,line
        # The approved script identifies this exact historical evidence commit.
        for name in ['HIGHLIGHTS.md','DIAGNOSIS.md','reuse-links.json','selected-exports.json','selected-images.json','selected-program-executions.json']:
            original=subprocess.check_output(['git','show','752266bae3a57ced83a7ce783c8fa1e7a460ae80:Post-Experiment Preparation/2026-10-23/'+name],cwd=REPO)
            assert take(PREP/name)==original,name
        self.links=load(PREP/'reuse-links.json');self.images=load(PREP/'selected-images.json');self.requests=load(PREP/'selected-program-executions.json')
        self.events={c:rows(r/'events.jsonl') for c,r in ROOTS.items()}
        self.index={c:load(r/'replay/index.json') for c,r in ROOTS.items()}
        self.cache={};self.used_chunks={};self.image_cache={}
        for c,r in ROOTS.items():
            run=load(r/'run.json')
            for n in ['scene.py','world.py','recording.py','viewer.html']:
                assert digest(take(APP/n))==run['source_identity']['apartment/'+n],n
        baseline=load(APP/'operations/session-57/endpoint.json')['official_queue']
        maps_=load(APP/'operations/session-74/scientific-terminal.json')
        assert all(q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0 for q in [baseline,maps_])
        self.endpoint_queues=[baseline['id'],maps_['id']]
        self.invocations=[]
        for session,request_id in [(1,142),(6,163),(9,107)]:
            selected=next(x for x in self.requests if x['condition']=='baseline' and x['session']==session and x['id']==request_id)
            p=ROOTS['baseline']/f'sessions/session-{session:05}/native/executor-1-capture.jsonl'
            capture=rows(p)
            found=next(x for x in capture if x['kind']=='request' and x['message'].get('id')==request_id and x['message'].get('method')=='process/start')
            assert found['message']['params']['argv']==selected['argv']
            wall=round(found['wall_unix_s']*1e9)
            events=self.events['baseline'];intervals=[]
            for a,b in zip(events,events[1:]):
                if a['clock_epoch']==b['clock_epoch'] and a['wall_ns']<=wall<=b['wall_ns']:
                    intervals.append((a,b))
            assert len(intervals)==1,(session,request_id,len(intervals))
            a,b=intervals[0]
            self.invocations.append(dict(session=session,request_id=request_id,source=str(p),capture_sequence=found['sequence'],
                capture_record_sha256=found['record_sha256'],wall_unix_s=found['wall_unix_s'],argv=selected['argv'],
                sim_bracket=[a['sim_time'],b['sim_time']],event_sequences=[a['sequence'],b['sequence']],
                event_sha256=[a['sha256'],b['sha256']],display_not_before=b['sim_time']))
        self.file_text={}
        for i in [0,1,2,3,5,6]:
            l=self.links[i];b=take(PREP/l['export']);assert digest(b)==l['sha256'];self.file_text[i]=b.decode('utf-8')
        self.logs={}
        for name in ['baseline-session-001-trial-5.jsonl','baseline-session-006-trial-6.jsonl','baseline-session-009-trial-1.jsonl']:
            p=PREP/'evidence'/name;self.logs[name]=rows(p)
        self.authority_path=REPO/'chats/Codex-Human/Apartment v4 Maps Launch and Monitoring/Apartment v4 Maps Launch and Monitoring - Active.md'
        self.authority=take(self.authority_path).decode('utf-8')
        assert 'recover the existing apartment-v4 Maps experiment' in self.authority
        cp=ROOTS['maps']/'checkpoints/session-00005';self.checkpoint=load(cp/'manifest.json');self.checkpoint_sha=digest(take(cp/'manifest.json'))
        take(APP/'operations/session-63/continuation-route.json')
        take(APP/'operations/session-74/timing-provenance.json')
    def sample(self,condition,t):
        index=self.index[condition];j=max(0,bisect.bisect_right([x['first'] for x in index],t)-1);row=index[j]
        assert row['first']<=t<=index[-1]['last'],(condition,t)
        key=(condition,row['file'])
        if key not in self.cache:
            p=ROOTS[condition]/'replay'/row['file'];assert digest(take(p))==row['sha256']
            with np.load(p) as a:self.cache[key]={n:a[n].copy() for n in a.files}
            self.used_chunks[str(p)]=dict(row)
            if len(self.cache)>8:self.cache.pop(next(iter(self.cache)))
        a=self.cache[key];k=max(0,int(np.searchsorted(a['t'],t,side='right'))-1)
        assert a['t'][k]<=t+1e-9
        return a['qpos'][k],a['qvel'][k],{'source':str(ROOTS[condition]/'replay'/row['file']),'sha256':row['sha256'],
          'sample':k,'sim_time':float(a['t'][k]),'requested_sim_time':t,'age_s':max(0,t-float(a['t'][k])),
          'wall_ns':int(a['wall_ns'][k]),'clock_epoch':row['clock_epoch']}
    def image(self,condition,n):
        key=(condition,n)
        if key not in self.image_cache:
            r=next(x for x in self.images if x['condition']==condition and x['sequence']==n)
            p=ROOTS[condition]/'sensors'/f'frame-{n:07}.png';assert digest(take(p))==r['sha256']
            event=next(x for x in self.events[condition] if x['sequence']==r['event'])
            assert event['payload']['image_sha256']==r['sha256']
            assert event['payload']['packet']['sim_time']==round(r['sim_time'],3)
            self.image_cache[key]=(Image.open(p).convert('RGB'),r)
        return self.image_cache[key]

def font(size,bold=False,mono=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('consola.ttf' if mono else 'seguisb.ttf' if bold else 'segoeui.ttf'),size)
BG=(12,22,31);FG=(241,245,243);MUTED=(164,190,196);ACCENT=(99,228,181);GOLD=(250,205,127)
FONT_CACHE={}
def f(size,bold=False,mono=False):
    key=(size,bold,mono)
    if key not in FONT_CACHE:FONT_CACHE[key]=font(*key)
    return FONT_CACHE[key]
def wrapped(text,size,width,bold=False,mono=False):
    ft=f(size,bold,mono);lines=[]
    for para in text.split('\n'):
        line=''
        for word in para.split():
            test=(line+' '+word).strip()
            if ft.getlength(test)>width and line:lines.append(line);line=word
            else:line=test
        lines.append(line)
    return lines
LAYOUT=[]
def text(draw,xy,content,size=44,color=FG,width=1780,bold=False,mono=False,spacing=1.2,tag='support'):
    lines=wrapped(content,size,width,bold,mono);x,y=xy
    for line in lines:
        assert f(size,bold,mono).getlength(line)<=width+1,(tag,line)
        draw.text((x,y),line,font=f(size,bold,mono),fill=color,
                  stroke_width=3 if tag=='source-clock' else 0,stroke_fill=BG)
        y+=size*spacing
    LAYOUT.append(dict(tag=tag,x=x,y=xy[1],width=width,height=y-xy[1],font_px=size,text=content))
    assert y<=1068,(tag,y,content)
    return y
def card(im,x,y,w,h):ImageDraw.Draw(im).rounded_rectangle((x,y,x+w,y+h),radius=22,fill=(23,39,50),outline=(52,75,84),width=2)

class Painter:
    def __init__(self,e):
        self.e=e;spec=importlib.util.spec_from_file_location('frozen_scene',APP/'scene.py');scene=importlib.util.module_from_spec(spec);spec.loader.exec_module(scene)
        self.model=mujoco.MjModel.from_xml_string(scene.xml());self.data=mujoco.MjData(self.model)
        self.renders={False:mujoco.Renderer(self.model,height=360,width=960),True:mujoco.Renderer(self.model,height=576,width=960)}
        self.option=mujoco.MjvOption();self.option.geomgroup[1]=0
    def scene(self,shot,video_t):
        a,b=shot['source'];u=min(1.,(video_t-shot['start'])/((shot['end']-shot['start'])*shot.get('motion_fraction',1.)));t=a+(b-a)*u
        q,v,receipt=self.e.sample(shot['condition'],t);self.data.qpos[:]=q;self.data.qvel[:]=v;self.data.time=receipt['sim_time'];mujoco.mj_forward(self.model,self.data)
        base=self.data.body('base').xpos;cam=mujoco.MjvCamera();cam.type=mujoco.mjtCamera.mjCAMERA_FREE
        mode=shot.get('camera','robot');yaw=float(q[self.model.joint('base_yaw').qposadr[0]])
        if mode=='wide':cam.lookat[:]=[6,5,.3];cam.distance=14;cam.azimuth=90;cam.elevation=-58
        elif mode=='throw':cam.lookat[:]=[3.8,1.55,.7];cam.distance=4.4;cam.azimuth=70;cam.elevation=-27
        elif mode=='chest':cam.lookat[:]=[4.55,7.7,.6];cam.distance=3.9;cam.azimuth=45;cam.elevation=-32
        elif mode=='cup':cam.lookat[:]=[8.3,2.9,.75];cam.distance=3.8;cam.azimuth=110;cam.elevation=-28
        elif mode=='arm':cam.lookat[:]=base+[.25,0,.65];cam.distance=2.7;cam.azimuth=math.degrees(yaw)+115;cam.elevation=-15
        else:cam.lookat[:]=base+[.2,0,.65];cam.distance=3.1;cam.azimuth=math.degrees(yaw)+105;cam.elevation=-22
        renderer=self.renders[bool(shot.get('panel'))];renderer.update_scene(self.data,camera=cam,scene_option=self.option)
        return Image.fromarray(renderer.render().copy()),receipt
    def panel(self,im,name,sim_time):
        x,y=1244,190;card(im,x-24,y-10,628,624);d=ImageDraw.Draw(im)
        def line(s,c=FG,size=44,bold=False):
            nonlocal y;y=text(d,(x,y),s,size,c,575,bold,spacing=1.17)+15
        if name in ['program','intro']:
            line('Saved file excerpt',ACCENT,42,True);line('throw_orange.py',FG,44,True)
            body=self.e.file_text[0]
            excerpt='\n'.join(body.splitlines()[body.splitlines().index('    start = s["sim_time"]'):][:3])
            line(excerpt,FG,40);line('SHA-256\n09a25635…',MUTED,38)
            line('Write verified by\n414.896 sim s',GOLD,38)
        elif name in ['read1','read9','defaults']:
            revised=name in ['read9','defaults'];idx=1 if revised else 0;l=self.e.links[idx]
            line('Same saved program' if not revised else 'Revised saved program',ACCENT,42,True);line('throw_orange.py',FG,44,True)
            line('SHA-256\n'+l['sha256'][:12]+'…',MUTED,38)
            if name=='defaults':
                # Contiguous literal fragments from the original revised source, not invented code.
                body=self.e.file_text[1]
                assert 'default=.28' in body and 'default=.137' in body
                line('Exact source fragments',GOLD,38);line('default=.28\ndefault=.137',FG,46)
                line('After explicit trials.\nNo new default run\nin session 6.',MUTED,36)
            else:
                r=l['full_file_read'];line('Full-file read\n'+f"{r['clock_bound']['sim_time'][0]:.3f}–\n{r['clock_bound']['sim_time'][1]:.3f} sim s",GOLD,40)
        elif name in ['run1','run6','run9','miss','hit']:
            line('Recorded feedback',ACCENT,42,True)
            if name in ['miss','hit']:
                landed=158.940 if name=='miss' else 236.168
                line('First miss' if name=='miss' else 'Later trial',FG,48,True)
                if sim_time>=landed:line('inside_bin: '+('false' if name=='miss' else 'true'),GOLD,46);line(f'Landing: {landed:.3f} s',MUTED,38)
                else:line('Waiting for landing',MUTED,40)
            else:
                which={'run1':0,'run6':1,'run9':2}[name];inv=self.e.invocations[which]
                if sim_time>=inv['display_not_before']:
                    line('Original command excerpt',MUTED,36)
                    line('throw_orange.py'+('\n--accelerate .28\n--release .137' if name=='run6' else ''),FG,42)
                log=self.e.logs[['baseline-session-001-trial-5.jsonl','baseline-session-006-trial-6.jsonl','baseline-session-009-trial-1.jsonl'][which]]
                available=log[-1]['status']['sim_time']
                if sim_time>=available:
                    fb=log[2]['feedback'];line('inside_bin: true',GOLD,44)
                    line('Forward / left (m)\n'+f"{fb['displacement_m']['forward']:+.3f} / {fb['displacement_m']['left']:+.3f}",MUTED,38)
        elif name in ['route','summary2','read2','readroute','mapsummary','readmapsummary','readmap','savemap']:
            mapping={'route':3,'readroute':3,'summary2':2,'read2':2,'mapsummary':5,'readmapsummary':5,'readmap':6,'savemap':6};l=self.e.links[mapping[name]]
            isread=name.startswith('read');line('Original full-file read' if isread else 'Saved file excerpt',ACCENT,40,True)
            if name in ['route','readroute']:
                line('bedroom-route.md',FG,42,True)
                quote='Bedroom lies approximately along initial-frame +y, through the opening beyond the living-room table and TV cabinet.'
                assert quote in self.e.file_text[3];line(quote,FG,40)
            elif name in ['readmap','savemap']:
                line('Kitchen.md',FG,46,True);line('SHA-256\n'+l['sha256'][:12]+'…',MUTED,38)
            else:
                line('Continuity summary',FG,44,True)
                body=self.e.file_text[mapping[name]];p=next(z for z in body.split('\n') if z.startswith('**'))
                if name in ['mapsummary','readmapsummary']:
                    snippet="It was recovered from the floor with a confirmed lift and successfully released onto the top of drawer B's cabinet"
                    assert snippet in body.replace('**','');snippet+='…'
                else:snippet=p.replace('**','').split('. ')[0]+'.'
                line(snippet[:210]+('…' if len(snippet)>210 else ''),FG,40)
            receipt=l['full_file_read'] if isread else l['write'];bounds=receipt['clock_bound']['sim_time']
            line(('Read' if isread else 'Saved')+f' by {bounds[1]:.3f} s',GOLD,38)
        elif name=='toysuccess':
            line('Recorded task check',ACCENT,42,True)
            if sim_time>=1956.584:line('task_success: true',GOLD,46);line('Latch: 1956.584 s',MUTED,38)
            else:line('Placement in progress',MUTED,40)
        elif name=='cupsuccess':
            line('Recorded task check',ACCENT,42,True);line('task_success: true',GOLD,46)
            line('Latch: 3648.276 s\nRelease done:\n3648.392 s',MUTED,38)
            line('Cup occluded in the\nfinal camera view',GOLD,40,True)
        elif name=='limitation':
            line('Original geometry',ACCENT,44,True);line('No connecting rails\nor links in the gaps.',FG,44)
            line('Joints constrain the\narm bodies. Missing\nstructures supply\nno contacts.',MUTED,40)
    def frame(self,shot,t):
        LAYOUT.clear();im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im);receipt={}
        chapter=next((label for a,b,label in STORIES if a<=t<b),'Three sessions later')
        text(d,(58,28),chapter,54,FG,1810,True,tag='chapter')
        kind=shot['kind'];panel=shot.get('panel');box=(48,176,1170 if panel else 1872,816)
        if kind=='replay':
            pic,receipt=self.scene(shot,t);fitted=ImageOps.contain(pic,(box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
            im.paste(fitted,(box[0]+(box[2]-box[0]-fitted.width)//2,box[1]));d=ImageDraw.Draw(im)
            rate=(shot['source'][1]-shot['source'][0])/((shot['end']-shot['start'])*shot.get('motion_fraction',1.))
            if t>=shot['start']+(shot['end']-shot['start'])*shot.get('motion_fraction',1.):rate=0
            label='Recorded-state replay'
            suffix='Held sample' if rate==0 else f'{rate:.2f}× recorded time'
            text(d,(58,100),label+'  •  '+suffix,42,ACCENT,1810,tag='evidence-label')
            text(d,(65,768),f"{shot['condition'].title()} • Session {shot['session']} • sim {receipt['sim_time']:.3f} s",38,FG,1750,tag='source-clock')
            if panel:self.panel(im,panel,receipt['sim_time'])
        elif kind=='image':
            pic,r=self.e.image(shot['condition'],shot['source']);receipt={'image':r}
            fitted=ImageOps.contain(pic,(box[2]-box[0],580),Image.Resampling.NEAREST);im.paste(fitted,(box[0]+(box[2]-box[0]-fitted.width)//2,180));d=ImageDraw.Draw(im)
            text(d,(58,100),'Robot camera • recorded frame',42,ACCENT,1810,tag='evidence-label')
            text(d,(65,768),f"{shot['condition'].title()} • Session {shot['session']} • image {shot['source']} • sim {r['sim_time']:.3f} s • held image",38,FG,1810,tag='source-clock')
            if panel:self.panel(im,panel,r['sim_time'])
        else:
            text(d,(58,100),'Editorial graphic',42,ACCENT,1810,tag='evidence-label')
            if kind in ['diagram','chain']:
                labels=['Session 1','Saved files','Later session'] if kind=='diagram' else ['File write','Checkpoint','Later read / run']
                for i,label in enumerate(labels):
                    x=85+i*620;card(im,x,310,510,230);d=ImageDraw.Draw(im);text(d,(x+35,380),label,52,FG,450,True,tag='diagram-label')
                    if i<2:text(d,(x+535,380),'→',64,ACCENT,90,True,tag='diagram-arrow')
                if kind=='diagram':text(d,(100,615),'Simplified simulated robot • not real-hardware validation',46,MUTED,1740,tag='limitation')
                else:text(d,(100,615),'Throwing program  •  Toy cleanup  •  Cup recovery',46,MUTED,1740,tag='story-summary')
            elif kind in ['pause','authority']:
                card(im,90,210,1740,530);d=ImageDraw.Draw(im)
                text(d,(145,250),'Intentional pause' if kind=='pause' else 'Randy • October 10, 11:32 PDT',58,FG,1620,True,tag='authority-heading')
                if kind=='pause':
                    text(d,(145,370),'The original session-6 closeout failed.\nThis is an interruption, not continuous footage.',50,MUTED,1580,tag='pause-context')
                else:
                    text(d,(145,355),'Original direction excerpt:',42,ACCENT,1580,tag='quote-label')
                    text(d,(145,420),'“recover the existing apartment-v4 Maps experiment”',52,FG,1580,tag='human-quote')
                    text(d,(145,555),'Checkpoint 5 • verified clean boundary\nManifest SHA-256 '+self.e.checkpoint_sha[:16]+'…',42,MUTED,1580,tag='checkpoint')
                    text(d,(145,678),'87-minute wall-time interruption',42,GOLD,1580,tag='clock-gap')
            else:
                text(d,(130,300),'A new session.\nNot a blank slate.',88,FG,1630,True,tag='end-title')
        # A persistent cut/jump label distinguishes held material and nonlinear editorial time.
        text(ImageDraw.Draw(im),(62,818),shot.get('note',''),34,MUTED,1790,tag='cut-label')
        c=next(c for a,b,c in CAPTIONS if a<=t<b)
        d=ImageDraw.Draw(im);d.rectangle((0,867,W,H),fill=(6,13,20));lines=wrapped(c,64,1780,True)
        if len(lines)>2:
            size=54;lines=wrapped(c,size,1780,True)
        else:size=64
        assert len(lines)<=3,(c,lines)
        text(d,(64,883),c,size,FG,1780,True,spacing=1.12,tag='approved-caption')
        return im,receipt,list(LAYOUT)
    def close(self):
        for r in self.renders.values():r.close()

def build(out):
    assert not out.exists(),'Use a fresh output version; never overwrite earlier video outputs.'
    out.mkdir(parents=True);e=Evidence();take(__file__);painter=Painter(e);plan=shots();ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    take(ffmpeg)
    mp4=out/f'three-sessions-later-session76-{out.name}.mp4'
    log=(out/'encoder.log').open('wb')
    command=[ffmpeg,'-hide_banner','-loglevel','warning','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0',
      '-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart','-metadata','title=Three sessions later: what the files carried forward',str(mp4)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
    layouts={};mapping=[];frames=FPS*DURATION;started=time.monotonic()
    try:
        for n in range(frames):
            t=n/FPS;si=next(i for i,s in enumerate(plan) if s['start']<=t<s['end']);shot=plan[si]
            im,receipt,layout=painter.frame(shot,t);proc.stdin.write(im.tobytes())
            layouts.setdefault(str(si),layout)
            mapping.append({'output_frame':n,'output_time':t,'shot':si,'evidence':receipt})
            if n%240==0:print(f'frame {n}/{frames}; {time.monotonic()-started:.1f}s',flush=True)
            # Small representative QA stills from the actual encoder input, later checked against decoded MP4 frames.
            if n==round((shot['start']+shot['end'])/2*FPS):
                qa=HERE/('qa-'+out.name);qa.mkdir(exist_ok=True);im.save(qa/f'input-shot-{si:02}.jpg',quality=92)
        proc.stdin.close();rc=proc.wait();assert rc==0,rc
    finally:
        painter.close();log.close()
    with gzip.open(HERE/'frame-sources.jsonl.gz','wt',encoding='utf-8') as f:
        for r in mapping:f.write(json.dumps(r,separators=(',',':'))+'\n')
    cue_sources=[]
    for i,s in enumerate(plan):
        cue=dict(id=i,**s)
        cue['output_frames']=[round(s['start']*FPS),round(s['end']*FPS)-1]
        cue['evidence_type']={'replay':'native render of original qpos/qvel; no task dynamics','image':'original sensor pixels, held',
                              'diagram':'editorial graphic','chain':'editorial graphic','pause':'editorial interruption card',
                              'authority':'original human quote plus editorial checkpoint card','end':'editorial title'}[s['kind']]
        if s['kind']=='replay':cue['camera_display']={'apartment_wall_group_1_hidden':True,'robot_geometry_unchanged':True}
        if s.get('panel'):
            cue['supporting_records']={'reuse_links':str(PREP/'reuse-links.json'),'program_requests':str(PREP/'selected-program-executions.json'),
                                       'invocation_clock_joins':e.invocations}
        cue_sources.append(cue)
    manifest=dict(schema='historical-video-source-timecode-1',production_date='2026-10-23',source_script=str(PREP/'VIDEO-SCRIPT.md'),
        source_script_sha256=digest(take(PREP/'VIDEO-SCRIPT.md')),historical_evidence_commit='752266bae3a57ced83a7ce783c8fa1e7a460ae80',
        video={'path':str(mp4),'sha256':digest(mp4.read_bytes()),'bytes':mp4.stat().st_size,'duration_s':DURATION,'fps':FPS,'frames':frames,'width':W,'height':H,'codec':'H.264','audio_streams':0},
        captions=[dict(start=a,end=b,text=c) for a,b,c in CAPTIONS],shots=cue_sources,invocation_clock_joins=e.invocations,
        original_scientific_queues=e.endpoint_queues,used_replay_chunks=e.used_chunks,
        input_identities=IDENTITIES,layout=layouts,encoder_argv=command,
        corrections=[{'original':'Randy directed a restore to checkpoint 5. The abandoned continuation was excluded.',
                      'rendered':CAPTIONS[15][2],'reason':'The abandoned material was the failed original session-6 tail; the accepted checkpoint-5 continuation was retained.'}],
        limitations=['Native rendering is a new observer reconstruction, not original continuous camera footage.',
          'Walls are hidden for visibility; historical robot geometry and physics sources are unchanged.',
          'Camera frames are sparse originals and held without invented motion.',
          'The cup remains occluded in the final original camera frame.',
          'World state also persists; these examples do not prove a causal memory benefit.',
          'The original failed Maps session 6 is excluded; the 87-minute interruption is explicit.'])
    write(HERE/'source-timecode-manifest.json',manifest)
    transcript=[];srt=[]
    def stamp(t):
        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    for i,(a,b,c) in enumerate(CAPTIONS,1):
        transcript.append(f'{a:06.2f}–{b:06.2f}\n{c}\n');srt.append(f'{i}\n{stamp(a)} --> {stamp(b)}\n{c}\n')
    (HERE/'captions.txt').write_text('\n'.join(transcript)+'\n',encoding='utf-8')
    (HERE/'captions.srt').write_text('\n'.join(srt)+'\n',encoding='utf-8')
    write(HERE/'render-result.json',dict(passed=True,video=manifest['video'],elapsed_s=time.monotonic()-started,manifest_sha256=digest((HERE/'source-timecode-manifest.json').read_bytes())))
    print('Completed',mp4,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();build(args.output.resolve())
