/* Pure presentation validation. This does not start a simulation or an episode.
 * Run: node "Long-Horizon Adaptive Robotics Expirement/Task and Architecture Explorer/test_scene.js"
 */
'use strict';
const assert=require('node:assert/strict');
require('./scene.js');
const Scene=globalThis.ExplorerScene;
// First original motion sample, sim_time_s=.502, A3 persistent / C01 / rep1.
// The source logs q and MuJoCo's cached TCP; moving samples may differ by one
// integration step. At this settled first sample the discrepancy is <1 micron.
const q=[.8000000066180085,-.49704393279951053,.00012381654432927036,-2.206418204354829,-.00031195756769236655,1.6988753169378308,.7853998517066695];
const recordedTCP=[.2782303996895633,.2864621242381523,.4674546520719501];
const actualTCP=Scene.forwardKinematics(q).tcp;
const error=Math.hypot(...actualTCP.map((v,i)=>v-recordedTCP[i]));
assert.ok(error<1e-6,'FK must match the original settled TCP sample within one micron.');
for(const missing of [null,[],[0,0,0],Array(7).fill(NaN)])assert.equal(Scene.forwardKinematics(missing),null,'Missing/invalid joints must never create an invented posture.');
// Exercise every view and a narrow screen without a browser or graphics driver.
let operations=0;
const finiteArgs=(name,args)=>{operations++;for(const n of args)if(typeof n==='number')assert.ok(Number.isFinite(n),name+' received a non-finite canvas coordinate.');};
for(const width of [375,640]) {
  const context=new Proxy({measureText:s=>({width:s.length*6}),createLinearGradient:(...a)=>{finiteArgs('linear gradient',a);return {addColorStop(){}};},createRadialGradient:(...a)=>{finiteArgs('radial gradient',a);return {addColorStop(){}};}},{get:(target,key)=>target[key]??((...args)=>finiteArgs(key,args)),set:(target,key,value)=>(target[key]=value,true)});
  const canvas={style:{},getContext:()=>context,hasAttribute:()=>false,setAttribute(){},addEventListener(){},removeEventListener(){},getBoundingClientRect:()=>({width,height:400})};
  const scene=new Scene(canvas);
  for(const view of ['perspective','overhead','front','side']) {
    scene.setView(view);
    assert.equal(scene.view,view);
    scene.draw({q:[...q,.04,.04],tcp:recordedTCP,objects:[{id:'A1',position:[.32,-.373,.021],family:'A'},{id:'insert_B',position:[.18,-.34,.009]}]});
    for(const p of [[-.13,-.46,0],[.83,.46,0],[0,0,.94]]) {
      const projected=scene.project(p);
      assert.ok(projected.x>=0&&projected.x<=width&&projected.y>=0&&projected.y<=400,'Workspace reference point must fit '+view+' at '+width+'px.');
    }
    scene.draw({q:null,objects:[]});
  }
  assert.throws(()=>scene.setView('missing'),RangeError);
  scene.destroy();
}
console.log(JSON.stringify({status:'passed',recordedSampleErrorM:error,views:4,widths:[375,640],canvasOperations:operations}));
