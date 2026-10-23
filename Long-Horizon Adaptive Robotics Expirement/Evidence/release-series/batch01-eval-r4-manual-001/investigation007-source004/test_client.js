'use strict';
// Standard Node built-ins only. Root runs these through the shared compute queue.
const test=require('node:test');
const assert=require('node:assert/strict');
const {webcrypto,createHash}=require('node:crypto');
const {readFile}=require('node:fs/promises');
const path=require('node:path');
const api=require('./lazy_data.js');
const BASE='http://127.0.0.1:8778/site/index.html';
const utf8=value=>new TextEncoder().encode(value);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
function source(bytes,ext='json'){const hash=sha(bytes);return {href:'data/'+hash+'.'+ext,sha256:hash,bytes:bytes.length};}
function jsonArtifact(value){const bytes=utf8(JSON.stringify(value));return {bytes,ref:source(bytes)};}
function fixtureReader(artifacts,transform=null){const requests=[];const reader=new api.Reader({base:BASE,cryptoImpl:webcrypto,fetchImpl:async(url,options)=>{requests.push({url,options});const value=artifacts.get(new URL(url).pathname.split('/').pop());if(!value)return new Response('',{status:404});let response=new Response(value,{status:200,headers:{'content-length':String(value.length)}});return transform?transform(response,value,options):response;}});return {reader,requests};}
function store(...artifacts){return new Map(artifacts.map(artifact=>[artifact.ref.href.split('/').pop(),artifact.bytes]));}
function valueArtifact(node){return jsonArtifact({format:'robot-trace-value-1.0',node});}
function summaryMetadata(runId,fields={}){return {run_id:runId,...fields,metadata_projection:{format:'robot-trace-metadata-summary-1.0',scope:'Bounded display fields; exact metadata is separately referenced.',full_metadata_included:false,deferred_fields:[]}};}
test('exact-length streaming read verifies SHA-256 before JSON use',async()=>{const artifact=jsonArtifact({ok:true});const {reader,requests}=fixtureReader(store(artifact));assert.deepEqual(await reader.json(artifact.ref,api.LIMITS.node),{ok:true});assert.equal(requests.length,1);assert.equal(requests[0].options.redirect,'error');assert.equal(requests[0].options.credentials,'same-origin');});
test('package addresses cannot traverse, change origin or embed schemes',()=>{for(const href of ['../x.json','/data/x.json','https://other/a','//other/a','data\\x','data/%2e%2e/x.json','data/%2Fetc.json','data/a.json?x=1','data/a.json#part','javascript:alert(1)','data/%0a.json'])assert.throws(()=>api.relativeURL(href,BASE),api.PackageError);assert.throws(()=>api.relativeURL('data/'+'a'.repeat(64)+'.json','file:///C:/site/index.html'),api.PackageError);assert.equal(api.relativeURL('../source%20files/frame.png',BASE,true),'http://127.0.0.1:8778/source%20files/frame.png');});
test('wrong declared length, truncation, excess bytes, bad SHA and filename fail closed',async()=>{const artifact=jsonArtifact({ok:true});const valid=store(artifact);let reader=fixtureReader(valid).reader;await assert.rejects(reader.json({...artifact.ref,bytes:artifact.ref.bytes+1},api.LIMITS.node),/length/);reader=fixtureReader(valid,(_response,bytes)=>new Response(bytes.slice(0,-1))).reader;await assert.rejects(reader.json(artifact.ref,api.LIMITS.node),/truncated/);reader=fixtureReader(valid,(_response,bytes)=>new Response(new Uint8Array([...bytes,0]))).reader;await assert.rejects(reader.json(artifact.ref,api.LIMITS.node),/exceeds/);const tampered=new Uint8Array(artifact.bytes);tampered[0]^=1;reader=fixtureReader(new Map([[artifact.ref.href.split('/').pop(),tampered]])).reader;await assert.rejects(reader.json(artifact.ref,api.LIMITS.node),/SHA-256/);await assert.rejects(reader.json({...artifact.ref,sha256:'b'.repeat(64)},api.LIMITS.node),/filename/);});
test('reference limits reject before fetching; malformed JSON and UTF-8 fail',async()=>{const {reader,requests}=fixtureReader(new Map());await assert.rejects(reader.json({href:'data/'+'a'.repeat(64)+'.json',sha256:'a'.repeat(64),bytes:api.LIMITS.node+1},api.LIMITS.node),/limit/);assert.equal(requests.length,0);const malformed={bytes:utf8('{bad')};malformed.ref=source(malformed.bytes);await assert.rejects(fixtureReader(store(malformed)).reader.json(malformed.ref,api.LIMITS.node),/JSON/);const invalid={bytes:new Uint8Array([0xc0,0xaf])};invalid.ref=source(invalid.bytes,'utf8');await assert.rejects(fixtureReader(store(invalid)).reader.text(invalid.ref),/UTF-8/);});
test('unexpected redirects and missing artifacts fail',async()=>{const artifact=jsonArtifact({ok:true});const {reader}=fixtureReader(store(artifact),response=>({ok:true,status:200,url:'http://127.0.0.1:8778/elsewhere',headers:response.headers,body:response.body}));await assert.rejects(reader.json(artifact.ref,api.LIMITS.node),/address changed/);await assert.rejects(fixtureReader(new Map()).reader.json(artifact.ref,api.LIMITS.node),/404/);});
test('epoch aborts stale loads and rejects stale completion after a new selection',async()=>{const epoch=new api.Epoch(),first=epoch.begin();assert.equal(epoch.current(first),true);const second=epoch.begin();assert.equal(first.signal.aborted,true);assert.equal(epoch.current(first),false);assert.throws(()=>epoch.check(first),{name:'AbortError'});assert.equal(epoch.current(second),true);epoch.cancel();assert.equal(second.signal.aborted,true);assert.equal(epoch.current(second),false);});
test('aborted reads never publish verified bytes',async()=>{const artifact=jsonArtifact({ok:true}),controller=new AbortController();controller.abort();const {reader,requests}=fixtureReader(store(artifact));await assert.rejects(reader.json(artifact.ref,api.LIMITS.node,controller.signal),{name:'AbortError'});assert.equal(requests.length,0);});
test('invalid codec tags, duplicate keys, invalid numbers and oversized inline strings fail',()=>{for(const value of [['x',[]],['v',{}],['v',Infinity],['o',[[['v','x'],['v',1]],[['v','x'],['v',2]]]],['o',[[['v',1],['v','bad']]]],['r',{href:'x',bytes:0,sha256:'no'}],['v','x'.repeat(16385)]])assert.throws(()=>api.validateNode(value),api.PackageError);});
test('array/object fragments reconstruct small data losslessly without prototype mutation',async()=>{
 const a=valueArtifact(['a',[['v',1],['v',2]]]);
 const b=valueArtifact(['a',[['v',3]]]);
 const root=valueArtifact(['o',[
  [['v','__proto__'],['v','ordinary evidence']],
  [['v','items'],['A',[['r',a.ref],['r',b.ref]]]]
 ]]);
 const {reader}=fixtureReader(store(root,a,b));
 const result=await api.materialize(await reader.value(root.ref),reader);
 assert.equal(Object.getPrototypeOf(result),null);
 assert.equal(result.__proto__,'ordinary evidence');
 assert.deepEqual(result.items,[1,2,3]);
});
test('object-fragment duplicate names and array fragment type mismatches fail',async()=>{const {reader}=fixtureReader(new Map());await assert.rejects(api.materialize(['O',[['o',[[['v','same'],['v',1]]]],['o',[[['v','same'],['v',2]]]]]],reader),/Duplicate/);await assert.rejects(api.materialize(['A',[['o',[]]]],reader),/wrong type/);});
test('path lookup resolves only preceding fragments needed for the selected field',async()=>{const hugeUnused={href:'data/'+'a'.repeat(64)+'.json',sha256:'a'.repeat(64),bytes:100};const first=valueArtifact(['a',[['o',[[['v','type'],['v','context_read']],[['v','content'],['v','exact bytes']]]]]]);const root=valueArtifact(['o',[[['v','events'],['A',[['r',first.ref],['r',hugeUnused]]]]]]);const {reader,requests}=fixtureReader(store(root,first));const result=await api.atPath(['r',root.ref],['events',0,'content'],reader);assert.deepEqual(result,['v','exact bytes']);assert.equal(requests.length,2);await assert.rejects(api.atPath(['o',[]],['missing'],reader),/absent/);});
test('large strings remain chunk-addressable and cannot be accidentally materialized',async()=>{const one={bytes:utf8('λ'.repeat(16000))};one.ref=source(one.bytes,'utf8');const two={bytes:utf8('🦾'.repeat(16000))};two.ref=source(two.bytes,'utf8');const {reader}=fixtureReader(store(one,two));const encoded=['S',[['s',[one.ref]],['s',[two.ref]],['s',[one.ref]],['s',[two.ref]]]];api.validateNode(encoded);assert.equal((await reader.text(one.ref)).length,16000);await assert.rejects(api.materialize(encoded,reader),/chunk by chunk/);});
test('manifest v2 requires exact run identity, bounded summary, metadata reference and ordered payload-free events',()=>{
 const ref={href:'data/'+'a'.repeat(64)+'.json',sha256:'a'.repeat(64),bytes:10};
 const event={event_id:1,event_type:'candidate_reply',parent_ids:[],payload_ref:ref,cues:{has_packet:false,candidate_events:[]}};
 const doc={format:'robot-trace-manifest-2.0',ordinal:0,run_id:'r',metadata:summaryMetadata('r'),metadata_ref:ref,motion_ref:ref,event_headers:[event]};
 assert.doesNotThrow(()=>api.validateManifest(doc,'r'));
 assert.throws(()=>api.validateManifest(doc,'other'),/identity/);
 assert.throws(()=>api.validateManifest({...doc,event_headers:[event,event]},'r'),/unordered/);
 assert.throws(()=>api.validateManifest({...doc,event_headers:[{...event,payload:{}}]},'r'),/eager/);
 assert.throws(()=>api.validateManifest({...doc,format:'robot-trace-manifest-1.0'},'r'),/identity/);
 assert.throws(()=>api.validateManifest({...doc,metadata_ref:null},'r'),/reference/);
 assert.throws(()=>api.validateManifest({...doc,metadata:{run_id:'r'}},'r'),/summary declaration/);
 assert.throws(()=>api.validateManifest({...doc,metadata:summaryMetadata('r',{too_big:'x'.repeat(api.LIMITS.descriptor)})},'r'),/summary exceeds/);
});
test('slot binding preserves summary values, types, array order and exact full metadata reference',()=>{
 const ref={href:'data/'+'a'.repeat(64)+'.json',sha256:'a'.repeat(64),bytes:10};
 const metadata=summaryMetadata('r',{manifest:{architecture:'A',counts:[1,2]},result:null});
 const descriptor={...metadata,package:{manifest:{},metadata_ref:ref}};
 const manifest={ordinal:3,run_id:'r',metadata:{metadata_projection:metadata.metadata_projection,result:null,manifest:{counts:[1,2],architecture:'A'},run_id:'r'},metadata_ref:ref};
 assert.doesNotThrow(()=>api.validateSlot(manifest,descriptor,3));
 assert.throws(()=>api.validateSlot(manifest,descriptor,2),/selected slot/);
 assert.throws(()=>api.validateSlot({...manifest,metadata:{...manifest.metadata,result:{outcome:'success'}}},descriptor,3),/selected slot/);
 assert.throws(()=>api.validateSlot({...manifest,metadata:{...manifest.metadata,manifest:{architecture:'A',counts:[2,1]}}},descriptor,3),/selected slot/);
 assert.throws(()=>api.validateSlot({...manifest,metadata:{...manifest.metadata,manifest:{architecture:'A',counts:['1',2]}}},descriptor,3),/selected slot/);
 assert.throws(()=>api.validateSlot({...manifest,metadata_ref:{...ref,bytes:11}},descriptor,3),/selected slot/);
 assert.throws(()=>api.validateSlot(manifest,{...descriptor,package:{manifest:{}}},3),/reference/);
});
test('Python-produced v2 fixture keeps large metadata exact and lazy alongside event codec',{skip:!process.env.INVESTIGATION007_FIXTURE_DIR},async()=>{
 const directory=process.env.INVESTIGATION007_FIXTURE_DIR;
 const descriptor=JSON.parse(await readFile(path.join(directory,'fixture-descriptor.json'),'utf8'));
 const requests=[];
 const reader=new api.Reader({base:BASE,cryptoImpl:webcrypto,fetchImpl:async(url)=>{
  const name=new URL(url).pathname.replace('/site/','');
  assert.match(name,/^data\/[a-f0-9]{64}\.(json|utf8)$/);
  requests.push(name);
  const bytes=await readFile(path.join(directory,name));
  return new Response(bytes,{headers:{'content-length':String(bytes.length)}});
 }});
 const manifest=await reader.manifest(descriptor.package.manifest,'synthetic-contract-check');
 api.validateSlot(manifest,descriptor,0);
 assert.equal(requests.length,1,'Opening the manifest must not fetch or decode full metadata.');
 assert.equal(descriptor.metadata_projection.full_metadata_included,false);
 assert.equal(descriptor.sampling.event_gap_count,8000);
 assert.equal(Object.hasOwn(descriptor.sampling,'event_gaps'),false);
 assert.ok(utf8(JSON.stringify(descriptor)).length<=api.LIMITS.descriptor);
 const gapNode=await api.atPath(['r',manifest.metadata_ref],['sampling','event_gaps',7999],reader);
 const gap=await api.materialize(gapNode,reader);
 assert.equal(gap.from_event,7999);
 assert.equal(gap.to_event,8000);
 assert.equal(gap.gap_s,0.501);
 assert.equal(gap.explanation,'synthetic metadata size regression');
 const sourceManifest=await api.materialize(await api.atPath(['r',manifest.metadata_ref],['manifest'],reader),reader);
 assert.equal(sourceManifest.architecture,'fixture');
 assert.equal(manifest.event_headers.length,1);
 assert.equal(manifest.event_headers[0].cues.candidate_events[0].type,'model_context_supplied');
 const motion=await api.materialize(await reader.value(manifest.motion_ref),reader);
 assert.equal(motion[0].sim_time_s,0);
 assert.deepEqual(motion[0].tcp,[0,0,0]);
 const root=await reader.value(manifest.event_headers[0].payload_ref);
 const reserved=await api.materialize(await api.atPath(root,['reserved'],reader),reader);
 assert.equal(reserved.format,'robot-trace-value-1.0');
 assert.deepEqual(reserved.node,['r','ordinary-data']);
 const content=await api.atPath(root,['events',0,'content'],reader);
 assert.equal(await api.materialize(content,reader),'lambda λ 🦾 '.repeat(3000));
});
