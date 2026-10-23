/* Recorded-state schematic, with no simulation or external dependencies.
 * Frames: Runtime 004/vendor/panda/panda.xml (normalized MuJoCo wxyz quaternions).
 * XML SHA256: 96ad67da03710f17f798c9478fd9e9efdf24a3bf8359f05e456dd9fb158ea273.
 * Workcell: Runtime 004/cell.py: ZONES, zone_half, fixture walls, rack, TCP site.
 * The shapes approximate the Panda meshes. Positions use exact frame transforms.
 * Object positions are supplied by the caller; no poses or motion are invented.
 */
(() => {
  'use strict';
  const add=(a,b)=>a.map((v,i)=>v+b[i]);
  const sub=(a,b)=>a.map((v,i)=>v-b[i]);
  const mul=(a,s)=>a.map(v=>v*s);
  const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const norm=a=>Math.hypot(...a);
  const unit=a=>mul(a,1/(norm(a)||1));
  const identity=()=>[1,0,0,0,1,0,0,0,1];
  const mv=(r,p)=>[dot(r.slice(0,3),p),dot(r.slice(3,6),p),dot(r.slice(6,9),p)];
  function mm(a,b) { const r=Array(9).fill(0); for(let i=0;i<3;i++)for(let j=0;j<3;j++)for(let k=0;k<3;k++)r[3*i+j]+=a[3*i+k]*b[3*k+j]; return r; }
  function quaternion(q) {
    const [w,x,y,z]=unit(q);
    return [1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)];
  }
  const rz=q=>[Math.cos(q),-Math.sin(q),0,Math.sin(q),Math.cos(q),0,0,0,1];
  const framePoint=(f,p)=>add(f.p,mv(f.r,p));
  const finitePosition=p=>Array.isArray(p)&&p.length>=3&&p.slice(0,3).every(Number.isFinite);
  const FRAMES=[
    [[0,0,.333],[1,0,0,0]], [[0,0,0],[1,-1,0,0]],
    [[0,-.316,0],[1,1,0,0]], [[.0825,0,0],[1,1,0,0]],
    [[-.0825,.384,0],[1,-1,0,0]], [[0,0,0],[1,1,0,0]],
    [[.088,0,0],[1,1,0,0]]
  ];
  function forwardKinematics(q) {
    if(!Array.isArray(q)||q.length<7||!q.slice(0,7).every(Number.isFinite))return null;
    let f={p:[0,0,0],r:identity()}; const joints=[];
    FRAMES.forEach(([p,quat],i)=>{f={p:framePoint(f,p),r:mm(mm(f.r,quaternion(quat)),rz(q[i]))};joints.push(f);});
    const hand={p:framePoint(f,[0,0,.107]),r:mm(f.r,quaternion([.9238795,0,0,-.3826834]))};
    return {joints,hand,tcp:framePoint(hand,[0,0,.1034])};
  }
  const ZONES=[
    {id:'fixture',label:'Machine',short:'Machine',p:[.57,0],color:'#ae7a36'},
    {id:'inspection',label:'Inspection',short:'Inspect',p:[.34,.20],color:'#347b83'},
    {id:'parking1',label:'Buffer 1',short:'B1',p:[.34,.04],color:'#738896'},
    {id:'parking2',label:'Buffer 2',short:'B2',p:[.46,.12],color:'#738896'},
    {id:'tray1',label:'Tray 1',short:'Tray 1',p:[.40,.33],color:'#657eac'},
    {id:'tray2',label:'Tray 2',short:'Tray 2',p:[.61,.33],color:'#657eac'},
    {id:'tray3',label:'Tray 3',short:'Tray 3',p:[.65,-.29],color:'#657eac'},
    {id:'quarantine',label:'Quarantine',short:'Quar.',p:[.20,.29],color:'#a56566'},
    {id:'insert_home_A',label:'Insert A home',short:'Insert A',p:[.18,-.25],color:'#8a7c9b'},
    {id:'insert_home_B',label:'Insert B home',short:'Insert B',p:[.18,-.34],color:'#8a7c9b'}
  ];
  const CAMERA={perspective:{az:-.95,el:.66,perspective:true},overhead:{az:-Math.PI/2,el:Math.PI/2,perspective:false},front:{az:-Math.PI/2,el:.09,perspective:false},side:{az:0,el:.09,perspective:false}};
  function shade(hex,n=1) {const h=hex.replace('#',''); const rgb=[0,2,4].map(i=>Math.max(0,Math.min(255,Math.round(parseInt(h.slice(i,i+2),16)*n))));return `rgb(${rgb.join(',')})`;}

  class ExplorerScene {
    constructor(canvas) {
      if(!canvas||typeof canvas.getContext!=='function')throw new TypeError('ExplorerScene needs a canvas.');
      this.canvas=canvas;this.ctx=canvas.getContext('2d');this.view='perspective';this.camera={...CAMERA.perspective};this.state={};this.zoom=1;
      canvas.style.touchAction='pan-y';canvas.style.cursor='grab';
      if(!canvas.hasAttribute('aria-label'))canvas.setAttribute('aria-label','Recorded robot state reconstructed as a 3D schematic. Drag to orbit.');
      canvas.setAttribute('role','img');
      this.handlers={};
      this.listen('pointerdown',e=>{if(e.button!==0)return;this.drag={x:e.clientX,y:e.clientY,az:this.camera.az,el:this.camera.el};canvas.setPointerCapture?.(e.pointerId);canvas.style.cursor='grabbing';});
      this.listen('pointermove',e=>{if(!this.drag)return;this.camera={az:this.drag.az-(e.clientX-this.drag.x)*.007,el:Math.max(.07,Math.min(Math.PI/2,this.drag.el+(e.clientY-this.drag.y)*.006)),perspective:true};this.view='orbit';this.draw(this.state);});
      const end=()=>{this.drag=null;canvas.style.cursor='grab';};this.listen('pointerup',end);this.listen('pointercancel',end);this.listen('lostpointercapture',end);
      if(typeof ResizeObserver!=='undefined'){this.resizeObserver=new ResizeObserver(()=>this.draw(this.state));this.resizeObserver.observe(canvas);}
      this.draw({});
    }
    listen(name,handler) {this.handlers[name]=handler;this.canvas.addEventListener(name,handler);}
    destroy() {this.resizeObserver?.disconnect();Object.entries(this.handlers).forEach(([name,handler])=>this.canvas.removeEventListener(name,handler));}
    setView(name) {if(!CAMERA[name])throw new RangeError('Unknown scene view: '+name);this.view=name;this.camera={...CAMERA[name]};this.zoom=1;this.draw(this.state);}
    setupProjection(w,h) {
      const {az,el,perspective}=this.camera,target=[.32,0,.22],distance=2.6;
      const eye=add(target,mul([Math.cos(el)*Math.cos(az),Math.cos(el)*Math.sin(az),Math.sin(el)],distance));
      const forward=unit(sub(target,eye));
      const right=el>1.56?[1,0,0]:unit(cross(forward,[0,0,1]));
      const up=unit(cross(right,forward));
      const raw=p=>{const d=sub(p,eye),depth=dot(d,forward),s=perspective?distance/depth:1;return {x:dot(d,right)*s,y:-dot(d,up)*s,depth,s};};
      const bounds=[[-.13,-.46,-.025],[-.13,.46,-.025],[.83,-.46,-.025],[.83,.46,-.025],[0,0,.94],[.4,0,.8]];
      const points=bounds.map(raw),xs=points.map(p=>p.x),ys=points.map(p=>p.y);
      const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
      this.scale=Math.min((w-42)/(maxX-minX),(h-72)/(maxY-minY))*this.zoom;
      const cx=w/2-(minX+maxX)/2*this.scale,cy=(h+6)/2-(minY+maxY)/2*this.scale;
      this.project=p=>{const v=raw(p);return {x:cx+v.x*this.scale,y:cy+v.y*this.scale,depth:v.depth,scale:v.s*this.scale};};
      this.eye=eye;this.forward=forward;this.w=w;this.h=h;
    }
    polygon(points,fill,stroke='rgba(20,38,43,.14)',width=.65) {
      const ps=points.map(this.project);this.primitives.push({depth:ps.reduce((s,p)=>s+p.depth,0)/ps.length,paint:()=>{const c=this.ctx;c.beginPath();ps.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));c.closePath();c.fillStyle=fill;c.fill();if(stroke){c.strokeStyle=stroke;c.lineWidth=width;c.stroke();}}});
    }
    box(p,half,color,r=identity(),alpha=1) {
      const pts=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]].map(v=>add(p,mv(r,v.map((n,i)=>n*half[i]))));
      const faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]],light=unit([-.4,-.6,1.6]);
      faces.forEach(indices=>{const normal=unit(cross(sub(pts[indices[1]],pts[indices[0]]),sub(pts[indices[2]],pts[indices[0]])));if(dot(normal,sub(this.eye,p))<=0)return;const fill=shade(color,.68+.32*Math.max(0,dot(normal,light)));this.polygon(indices.map(i=>pts[i]),alpha===1?fill:fill.replace('rgb(','rgba(').replace(')',`,${alpha})`));});
    }
    line(a,b,color,width=1,dash=[]) {
      const p=this.project(a),q=this.project(b);this.primitives.push({depth:(p.depth+q.depth)/2,paint:()=>{const c=this.ctx;c.beginPath();c.moveTo(p.x,p.y);c.lineTo(q.x,q.y);c.strokeStyle=color;c.lineWidth=width;c.setLineDash(dash);c.stroke();c.setLineDash([]);}});
    }
    cylinder(a,b,r,color) {
      if(norm(sub(b,a))<.0001)return;
      const axis=unit(sub(b,a)),u=unit(cross(axis,Math.abs(axis[2])>.9?[1,0,0]:[0,0,1])),v=cross(axis,u);
      const rings=[a,b].map(p=>Array.from({length:12},(_,i)=>add(p,add(mul(u,r*Math.cos(i*Math.PI/6)),mul(v,r*Math.sin(i*Math.PI/6))))));
      for(let i=0;i<12;i++){const j=(i+1)%12,normal=add(mul(u,Math.cos((i+.5)*Math.PI/6)),mul(v,Math.sin((i+.5)*Math.PI/6)));if(dot(normal,sub(this.eye,a))>0)this.polygon([rings[0][i],rings[0][j],rings[1][j],rings[1][i]],shade(color,.65+.35*Math.max(0,dot(normal,unit([-.4,-.6,1.6])))),null);}
      this.polygon(rings[dot(axis,sub(this.eye,a))>0?1:0],shade(color,.86),'rgba(22,44,50,.18)');
    }
    sphere(p,r,color) {
      const v=this.project(p),radius=Math.max(2,r*v.scale);this.primitives.push({depth:v.depth,paint:()=>{const c=this.ctx,g=c.createRadialGradient(v.x-radius*.35,v.y-radius*.4,radius*.1,v.x,v.y,radius);g.addColorStop(0,shade(color,1.17));g.addColorStop(.6,color);g.addColorStop(1,shade(color,.6));c.beginPath();c.arc(v.x,v.y,radius,0,2*Math.PI);c.fillStyle=g;c.fill();c.strokeStyle='rgba(15,37,44,.24)';c.lineWidth=.7;c.stroke();}});
    }
    workspace() {
      this.box([.35,0,-.024],[.48,.46,.023],'#dce6e5');
      for(let x=-.1;x<=.8;x+=.1)this.line([x,-.46,0],[x,.46,0],'rgba(90,121,123,.11)',.6);
      for(let y=-.4;y<=.4;y+=.1)this.line([-.13,y,0],[.83,y,0],'rgba(90,121,123,.11)',.6);
      ZONES.forEach(z=>{const half=z.id.startsWith('tray')?[.092,.065,.001]:[.053,.053,.001];this.box([...z.p,.001],half,z.color,identity(),.4);const [x,y]=z.p;const corners=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([a,b])=>[x+a*half[0],y+b*half[1],.003]);corners.forEach((p,i)=>this.line(p,corners[(i+1)%4],z.color,.85));});
      // Public fixture walls: 12 mm high, 40 mm jaw-access slots.
      [[.049,0,.004,.053],[-.049,0,.004,.053],...[-.0365,.0365].flatMap(dx=>[-.049,.049].map(dy=>[dx,dy,.0165,.004]))].forEach(([dx,dy,sx,sy])=>this.box([.57+dx,dy,.006],[sx,sy,.006],'#a38d6e'));
      // Raw rack is an explanatory outline around the source's initial part grid.
      const raw=[[.285,-.419,.004],[.529,-.419,.004],[.529,-.045,.004],[.285,-.045,.004]];raw.forEach((p,i)=>this.line(p,raw[(i+1)%4],'#77918b',1,[3,3]));
      this.cylinder([0,0,.001],[0,0,.048],.079,'#798c91');
      this.cylinder([0,0,.048],[0,0,.072],.066,'#e0e7e9');
    }
    robot(kin,q) {
      const joints=kin.joints;
      const links=[[[0,0,.07],joints[0].p,.044], [joints[1].p,joints[2].p,.040],[joints[2].p,joints[3].p,.038],[joints[3].p,joints[4].p,.039],[joints[5].p,joints[6].p,.034],[joints[6].p,kin.hand.p,.032]];
      links.forEach(([a,b,r])=>{const middle=mul(add(a,b),.5);this.cylinder(a,middle,r,'#e8eef0');this.cylinder(middle,b,r*.92,'#e8eef0');});
      joints.forEach((f,i)=>{const axis=mv(f.r,[0,0,1]),radius=i<4?.047:.038;this.cylinder(add(f.p,mul(axis,-.018)),add(f.p,mul(axis,.018)),radius,i===5?'#548f98':'#5b6f78');this.sphere(f.p,radius*.84,'#d2dfe3');});
      this.box(framePoint(kin.hand,[0,0,.023]),[.031,.048,.027],'#bbcbd0',kin.hand.r);
      // Recorded finger joints, when supplied; otherwise schematic 28 mm travel per finger.
      const openings=[Number.isFinite(q[7])?q[7]:.028,Number.isFinite(q[8])?q[8]:.028];
      [-1,1].forEach((sign,i)=>{this.box(framePoint(kin.hand,[0,sign*(openings[i]+.008),.078]),[.008,.007,.023],'#526974',kin.hand.r);this.box(framePoint(kin.hand,[0,sign*(openings[i]+.006),.101]),[.008,.006,.007],'#a7bbc1',kin.hand.r);});
    }
    objects(objects) {
      objects.filter(o=>finitePosition(o.position||o.pos)).forEach(o=>{
        const p=(o.position||o.pos).slice(0,3),id=String(o.id||o.name||''),insert=id.startsWith('insert'),family=o.family||(insert?id.slice(-1):id[0]);
        const r=Array.isArray(o.quaternion)&&o.quaternion.length===4?quaternion(o.quaternion):identity();
        const half=insert?[.025,.025,.008]:[.021,.021,.018],color=family==='A'?'#df9557':family==='B'?'#618ac1':'#8986a7';
        this.box(p,half,'#aab6b8',r);this.box(add(p,mv(r,[0,0,half[2]+.001])),[.014,.014,.001],color,r);
        this.objectLabels.push({p:add(p,[0,0,half[2]+.018]),text:id,color});
      });
    }
    labels() {
      const c=this.ctx,small=this.w<470,rects=[],placed=[];
      const specs=ZONES.map(z=>({p:[...z.p,.005],text:small?z.short:z.label,color:z.color}));
      specs.push({p:[.41,-.44,.005],text:'Raw rack',color:'#587c73'});
      // Place labels around projected zones; leader lines retain the exact anchor.
      specs.forEach(label=>{
        const p=this.project(label.p);c.font=`600 ${small?9:10}px system-ui, sans-serif`;
        const width=c.measureText(label.text).width+10,height=16;
        const candidates=[[0,0],[0,18],[0,-18],[0,36],[0,-36],[width*.58,18],[-width*.58,18],[width*.6,-18],[-width*.6,-18]];
        let best=null,bestCost=Infinity;
        candidates.forEach(([dx,dy])=>{const x=Math.max(4,Math.min(this.w-width-4,p.x+dx-width/2)),y=Math.max(35,Math.min(this.h-41,p.y+dy-height/2));const rect={x,y,w:width,h:height},overlap=rects.reduce((s,b)=>s+(x<b.x+b.w+2&&x+width+2>b.x&&y<b.y+b.h+2&&y+height+2>b.y?1:0),0);const cost=overlap*10000+Math.abs(dx)+Math.abs(dy);if(cost<bestCost){best={...rect,p,label};bestCost=cost;}});
        rects.push(best);placed.push(best);
      });
      placed.forEach(({x,y,w,h,p,label})=>{c.beginPath();c.moveTo(p.x,p.y);c.lineTo(x+w/2,y+h/2);c.strokeStyle=label.color+'88';c.lineWidth=.65;c.stroke();c.fillStyle='rgba(249,252,252,.91)';c.fillRect(x,y,w,h);c.strokeStyle=label.color+'66';c.strokeRect(x+.5,y+.5,w-1,h-1);c.font=`600 ${small?9:10}px system-ui, sans-serif`;c.fillStyle='#354e54';c.textAlign='center';c.textBaseline='middle';c.fillText(label.text,x+w/2,y+h/2+.5);});
      // IDs identify source objects, independently from the explanatory zone labels.
      this.objectLabels.forEach(({p,text,color})=>{if(!text)return;const v=this.project(p);c.font=`700 ${small?9:10}px system-ui, sans-serif`;const tw=c.measureText(text).width;c.fillStyle='rgba(253,254,254,.88)';c.fillRect(v.x-tw/2-3,v.y-7,tw+6,14);c.fillStyle=shade(color,.62);c.fillText(text,v.x,v.y);});
    }
    overlay(kin,state) {
      const c=this.ctx,w=this.w,h=this.h;
      c.textAlign='left';c.textBaseline='alphabetic';c.fillStyle='#35545b';c.font='600 10px system-ui, sans-serif';c.fillText('RECORDED-STATE SCHEMATIC',14,21);
      c.textAlign='right';c.fillStyle='#6c8488';c.font='10px system-ui, sans-serif';c.fillText(this.view==='orbit'?'Drag to orbit':this.view[0].toUpperCase()+this.view.slice(1)+' · drag to orbit',w-14,21);
      const origin=[29,h-27],axisLength=17,reference=[.35,0,.2],a=this.project(reference);
      [['x',[.1,0,0],'#ae7451'],['y',[0,.1,0],'#528a74'],['z',[0,0,.1],'#587aa3']].forEach(([label,delta,color])=>{const p=this.project(add(reference,delta)),d=[p.x-a.x,p.y-a.y],length=Math.hypot(...d);if(length<.01)return;const b=[origin[0]+d[0]/length*axisLength,origin[1]+d[1]/length*axisLength];c.beginPath();c.moveTo(...origin);c.lineTo(...b);c.strokeStyle=color;c.lineWidth=1.5;c.stroke();c.fillStyle=color;c.font='9px system-ui';c.textAlign='center';c.fillText(label,b[0]+d[0]/length*6,b[1]+d[1]/length*6+3);});
      c.textAlign='right';c.fillStyle='#617b80';c.font='10px system-ui, sans-serif';
      const q=state.q||state.qpos,hasFingers=q&&Number.isFinite(q[7])&&Number.isFinite(q[8]);
      c.fillText(kin?(hasFingers?'Joint poses from record · shapes simplified':'Joint poses recorded · gripper schematic'):'No recorded joint state selected',w-14,h-15);
      if((state.objects||[]).some(o=>finitePosition(o.position||o.pos)&&!Array.isArray(o.quaternion)))c.fillText('Object orientation schematic',w-14,h-29);
      if(finitePosition(state.tcp)) {const p=this.project(state.tcp);c.beginPath();c.arc(p.x,p.y,5,0,Math.PI*2);c.fillStyle='#e4b24e';c.fill();c.strokeStyle='#6b4a14';c.lineWidth=1;c.stroke();c.beginPath();c.moveTo(p.x-8,p.y);c.lineTo(p.x+8,p.y);c.moveTo(p.x,p.y-8);c.lineTo(p.x,p.y+8);c.stroke();}
    }
    draw(state={}) {
      this.state=state||{};const rect=this.canvas.getBoundingClientRect();
      const w=Math.max(100,rect.width||this.canvas.clientWidth||640),h=Math.max(180,rect.height||this.canvas.clientHeight||400),dpr=Math.min(globalThis.devicePixelRatio||1,3);
      const pw=Math.round(w*dpr),ph=Math.round(h*dpr);if(this.canvas.width!==pw)this.canvas.width=pw;if(this.canvas.height!==ph)this.canvas.height=ph;
      const c=this.ctx;c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);
      const gradient=c.createLinearGradient(0,0,0,h);gradient.addColorStop(0,'#f4f8f7');gradient.addColorStop(1,'#eaf1f0');c.fillStyle=gradient;c.fillRect(0,0,w,h);
      this.setupProjection(w,h);this.primitives=[];this.objectLabels=[];this.workspace();
      const q=this.state.q||this.state.qpos,kin=forwardKinematics(q);if(kin)this.robot(kin,q);
      this.objects(Array.isArray(this.state.objects)?this.state.objects:[]);
      this.primitives.sort((a,b)=>b.depth-a.depth).forEach(item=>item.paint());this.labels();this.overlay(kin,this.state);
      return kin;
    }
  }
  ExplorerScene.forwardKinematics=forwardKinematics;
  ExplorerScene.zones=ZONES.map(z=>({id:z.id,position:[...z.p,0]}));
  ExplorerScene.provenance={frames:'Runtime 004/vendor/panda/panda.xml',xmlSha256:'96ad67da03710f17f798c9478fd9e9efdf24a3bf8359f05e456dd9fb158ea273',workspace:'Runtime 004/cell.py',tcpLocalOffset:[0,0,.1034],geometry:'Simplified shaded geometry; not a camera image or a new physics simulation. Table is a bounded illustration of the source plane. Raw rack outline is an explanatory guide.',objectOrientation:'Identity unless recorded wxyz quaternion is supplied.',fingerOpening:'Uses q[7:9] when recorded; otherwise schematic 28 mm travel per finger.'};
  globalThis.ExplorerScene=ExplorerScene;
})();
