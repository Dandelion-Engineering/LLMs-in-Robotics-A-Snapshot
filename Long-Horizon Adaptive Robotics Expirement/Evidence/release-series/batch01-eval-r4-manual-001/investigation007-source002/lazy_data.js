/* Investigation 007: bounded, hash-verified presentation reads. No outcome derivation. */
(function (root) {
 'use strict';
 const LIMITS=Object.freeze({manifest:16*1024*1024,node:1024*1024,string:64*1024,image:16*1024*1024,motionBytes:32*1024*1024,motionNodes:1000000,depth:96,page:24});
 class PackageError extends Error { constructor(message){super(message);this.name='PackageError';} }
 function insist(ok,message){if(!ok)throw new PackageError(message);}
 function aborted(signal){if(signal?.aborted)throw new DOMException('Selection changed.','AbortError');}
 function validateRef(ref,limit){insist(ref&&typeof ref==='object'&&!Array.isArray(ref),'Invalid artifact reference.');insist(Number.isSafeInteger(ref.bytes)&&ref.bytes>0&&ref.bytes<=limit,'Artifact size is absent, invalid, or above the presentation limit.');insist(typeof ref.sha256==='string'&&/^[a-f0-9]{64}$/.test(ref.sha256),'Invalid artifact SHA-256.');return ref;}
 function relativeURL(href,base,source=false){
  insist(typeof href==='string'&&href.length>0&&!/[\u0000-\u0020\u007f\\?#]/.test(href)&&!/^[/]|^[a-z][a-z0-9+.-]*:/i.test(href),'Unsafe artifact address.');
  let decoded;try{decoded=decodeURIComponent(href);}catch{throw new PackageError('Malformed artifact address.');}
  insist(!(source?/[\u0000-\u001f\u007f\\?#]/:/[\u0000-\u0020\u007f\\?#]/).test(decoded)&&!/^[/]|^[a-z][a-z0-9+.-]*:/i.test(decoded),'Unsafe encoded artifact address.');
  if(!source)insist(/^data\/[a-f0-9]{64}\.(json|utf8)$/.test(href),'Unexpected packaged artifact address.');
  const origin=new URL(base),url=new URL(href,origin);insist(['http:','https:'].includes(origin.protocol)&&url.origin===origin.origin&&!url.username&&!url.password,'Artifact must use the same local web origin.');
  return url.href;
 }
 class Epoch {
  constructor(){this.number=0;this.controller=null;}
  begin(){this.cancel();this.controller=new AbortController();return {number:this.number,signal:this.controller.signal};}
  cancel(){this.controller?.abort();this.controller=null;this.number++;}
  current(ticket){return Boolean(ticket&&ticket.number===this.number&&!ticket.signal.aborted);}
  check(ticket){if(!this.current(ticket))throw new DOMException('Selection changed.','AbortError');}
 }
 class Reader {
  constructor({base,fetchImpl=root.fetch?.bind(root),cryptoImpl=root.crypto}={}){this.base=base||root.document?.baseURI;this.fetchImpl=fetchImpl;this.crypto=cryptoImpl;insist(this.base&&this.fetchImpl&&this.crypto?.subtle,'Verified package reading is unavailable in this browser.');}
  async bytes(ref,limit,signal,{source=false,budget=null}={}){
   validateRef(ref,limit);aborted(signal);const url=relativeURL(ref.href,this.base,source);
   if(!source)insist(ref.href.split('/').pop().split('.')[0]===ref.sha256,'Artifact filename does not match its content hash.');
   if(budget){budget.bytes+=ref.bytes;insist(budget.bytes<=budget.maxBytes,'Decoded record exceeds its bounded presentation budget.');}
   const response=await this.fetchImpl(url,{signal,redirect:'error',credentials:'same-origin'});aborted(signal);
   insist(response.ok,'Artifact request failed ('+response.status+').');
   if(response.url)insist(new URL(response.url).href===url,'Artifact response address changed.');
   const declared=response.headers?.get('content-length');if(declared!==null&&declared!==undefined)insist(/^\d+$/.test(declared)&&Number(declared)===ref.bytes,'Response length differs from the source-bound artifact size.');
   insist(response.body?.getReader,'Streaming artifact reads are unavailable.');const stream=response.body.getReader(),data=new Uint8Array(ref.bytes);let count=0;
   try{while(true){aborted(signal);const {value,done}=await stream.read();if(done)break;insist(value instanceof Uint8Array,'Invalid response byte stream.');insist(count+value.byteLength<=ref.bytes,'Artifact body exceeds its declared size.');data.set(value,count);count+=value.byteLength;}}
   catch(error){try{await stream.cancel();}catch{}throw error;}finally{stream.releaseLock();}
   aborted(signal);insist(count===ref.bytes,'Artifact is truncated.');const digest=Array.from(new Uint8Array(await this.crypto.subtle.digest('SHA-256',data)),x=>x.toString(16).padStart(2,'0')).join('');aborted(signal);insist(digest===ref.sha256,'Artifact SHA-256 mismatch.');return data;
  }
  async json(ref,limit,signal,budget=null){const bytes=await this.bytes(ref,limit,signal,{budget});let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);return JSON.parse(text);}catch(error){throw new PackageError('Artifact is not valid UTF-8 JSON: '+error.message);}}
  async value(ref,signal,budget=null){const doc=await this.json(ref,LIMITS.node,signal,budget);insist(doc?.format==='robot-trace-value-1.0','Unsupported trace value format.');validateNode(doc.node);return doc.node;}
  async text(ref,signal,budget=null){try{return new TextDecoder('utf-8',{fatal:true}).decode(await this.bytes(ref,LIMITS.string,signal,{budget}));}catch(error){if(error.name==='AbortError'||error instanceof PackageError)throw error;throw new PackageError('Invalid UTF-8 string chunk.');}}
  async manifest(ref,runId,signal){const doc=await this.json(ref,LIMITS.manifest,signal);validateManifest(doc,runId);return doc;}
 }
 function validateNode(value,depth=0){
  insist(depth<=LIMITS.depth&&Array.isArray(value)&&value.length===2&&typeof value[0]==='string','Malformed or excessively nested trace node.');const [tag,body]=value;
  if(tag==='v'){insist(body===null||typeof body==='boolean'||typeof body==='string'||(typeof body==='number'&&Number.isFinite(body)),'Invalid scalar node.');if(typeof body==='string')insist(new TextEncoder().encode(body).length<=16*1024,'Inline trace string exceeds the codec limit.');return;}
  if(tag==='r'){validateRef(body,LIMITS.node);return;}
  insist(Array.isArray(body),'Invalid trace container.');
  if(tag==='s'){body.forEach(ref=>validateRef(ref,LIMITS.string));return;}
  if(tag==='o'){const keys=new Set();body.forEach(pair=>{insist(Array.isArray(pair)&&pair.length===2,'Invalid object entry.');validateNode(pair[0],depth+1);insist(['v','s','S','r'].includes(pair[0][0]),'Invalid object key node.');if(pair[0][0]==='v'){insist(typeof pair[0][1]==='string','Object key must be a string.');insist(!keys.has(pair[0][1]),'Duplicate object key.');keys.add(pair[0][1]);}validateNode(pair[1],depth+1);});return;}
  insist(['a','A','O','S'].includes(tag),'Unknown trace node tag.');body.forEach(item=>validateNode(item,depth+1));
 }
 function validateManifest(doc,runId){
  insist(doc&&doc.format==='robot-trace-manifest-1.0'&&doc.run_id===runId,'Trace manifest identity mismatch.');insist(Number.isSafeInteger(doc.ordinal)&&doc.ordinal>=0,'Invalid trace ordinal.');insist(doc.metadata&&typeof doc.metadata==='object'&&!Array.isArray(doc.metadata)&&doc.metadata.run_id===runId,'Invalid trace metadata identity.');validateRef(doc.motion_ref,LIMITS.node);insist(Array.isArray(doc.event_headers),'Missing retained event headers.');let prior=-1;
  for(const event of doc.event_headers){insist(event&&Number.isSafeInteger(event.event_id)&&event.event_id>prior&&typeof event.event_type==='string'&&Array.isArray(event.parent_ids),'Invalid or unordered event envelope.');prior=event.event_id;insist(event.parent_ids.every(Number.isSafeInteger),'Invalid event parent IDs.');insist(!Object.hasOwn(event,'payload'),'A trace manifest must not contain eager event payloads.');validateRef(event.payload_ref,LIMITS.node);insist(event.cues&&typeof event.cues.has_packet==='boolean'&&Array.isArray(event.cues.candidate_events),'Invalid event lookup cues.');for(const cue of event.cues.candidate_events)insist(Number.isSafeInteger(cue.index)&&cue.index>=0&&(cue.type==null||typeof cue.type==='string'),'Invalid candidate event cue.');}
 }
 function sameJSON(left,right,depth=0){insist(depth<=LIMITS.depth,'Metadata nesting exceeds the presentation limit.');if(left===right)return true;if(left===null||right===null||typeof left!=='object'||typeof right!=='object'||Array.isArray(left)!==Array.isArray(right))return false;const keys=Object.keys(left),other=Object.keys(right);return keys.length===other.length&&keys.every(key=>Object.hasOwn(right,key)&&sameJSON(left[key],right[key],depth+1));}
 function validateSlot(manifest,descriptor,ordinal){const {package:packageReference,...metadata}=descriptor;insist(manifest.ordinal===ordinal&&sameJSON(manifest.metadata,metadata),'Trace manifest ordinal or metadata differs from the selected slot.');}
 async function dereference(value,reader,signal,budget,depth=0){insist(depth<=LIMITS.depth,'Trace reference depth exceeds the presentation limit.');return value[0]==='r'?dereference(await reader.value(value[1],signal,budget),reader,signal,budget,depth+1):value;}
 async function* children(value,reader,signal,budget,depth=0){
  insist(depth<=LIMITS.depth,'Trace tree exceeds the presentation depth limit.');value=await dereference(value,reader,signal,budget);const [tag,body]=value;
  if(tag==='a'){for(let i=0;i<body.length;i++){aborted(signal);yield [i,body[i]];}return;}
  if(tag==='o'){for(const pair of body){aborted(signal);yield pair;}return;}
  if(tag==='A'||tag==='O'){let offset=0;const names=new Set();for(const fragment of body){const resolved=await dereference(fragment,reader,signal,budget);insist((tag==='A'?['a','A']:['o','O']).includes(resolved[0]),'Container fragment has the wrong type.');for await(const [key,item]of children(resolved,reader,signal,budget,depth+1)){if(tag==='A')yield [offset++,item];else{const name=await materialize(key,reader,signal,{bytes:0,maxBytes:128*1024,nodes:0,maxNodes:10000},depth+1);insist(typeof name==='string'&&!names.has(name),'Duplicate or invalid object fragment key.');names.add(name);yield [key,item];}}}return;}
  throw new PackageError('Expected an array or object container.');
 }
 async function atPath(value,path,reader,signal){const budget={bytes:0,maxBytes:LIMITS.motionBytes,nodes:0,maxNodes:LIMITS.motionNodes};for(const part of path){value=await dereference(value,reader,signal,budget);let found=false;for await(const [key,item]of children(value,reader,signal,budget)){if((typeof key==='number'&&key===part)||(Array.isArray(key)&&key[0]==='v'&&key[1]===part)){value=item;found=true;break;}}insist(found,'Requested field is absent from this exact record.');}return value;}
 async function materialize(value,reader,signal,budget={bytes:0,maxBytes:LIMITS.motionBytes,nodes:0,maxNodes:LIMITS.motionNodes},depth=0){
  aborted(signal);insist(depth<=LIMITS.depth&&++budget.nodes<=budget.maxNodes,'Record exceeds the bounded decoding limit.');value=await dereference(value,reader,signal,budget);const[tag,body]=value;if(tag==='v')return body;
  if(tag==='s'||tag==='S'){let out='',size=0;for(const item of body){const part=tag==='s'?await reader.text(item,signal,budget):await materialize(item,reader,signal,budget,depth+1);insist(typeof part==='string','Invalid string fragment.');size+=part.length;insist(size<=64*1024,'Large strings must be inspected chunk by chunk.');out+=part;}return out;}
  if(tag==='a'||tag==='A'){const out=[];for await(const [,item]of children(value,reader,signal,budget))out.push(await materialize(item,reader,signal,budget,depth+1));return out;}
  if(tag==='o'||tag==='O'){const out=Object.create(null);for await(const [key,item]of children(value,reader,signal,budget)){const name=await materialize(key,reader,signal,budget,depth+1);insist(typeof name==='string'&&!Object.hasOwn(out,name),'Duplicate or invalid object key.');out[name]=await materialize(item,reader,signal,budget,depth+1);}return out;}
  throw new PackageError('Unsupported materialized value.');
 }
 const api=Object.freeze({LIMITS,PackageError,Epoch,Reader,relativeURL,validateRef,validateNode,validateManifest,validateSlot,dereference,children,atPath,materialize,aborted});
 root.InvestigationData=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
