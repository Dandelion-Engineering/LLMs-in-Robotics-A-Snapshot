/* One forward journal pass. UI navigation never scans reconstructed states. */
function buildVersionIndex(journal){
  const initial=journal[0].state;
  const paths={...initial.paths},nodes={...initial.nodes};
  const reverse=new Map(),last=new Map(),versions=new Map();
  const identity=p=>paths[p]===undefined?'null':JSON.stringify(nodes[String(paths[p])]);
  const attach=(p,id)=>{id=String(id);if(!reverse.has(id))reverse.set(id,new Set());reverse.get(id).add(p);};
  const detach=(p,id)=>{const set=reverse.get(String(id));if(set){set.delete(p);if(!set.size)reverse.delete(String(id));}};
  for(const [p,id] of Object.entries(paths)){attach(p,id);last.set(p,identity(p));versions.set(p,[1]);}
  for(const record of journal){
    if(record.type!=='mutation')continue;
    const delta=record.delta;
    const affected=new Set([...delta.paths.remove,...Object.keys(delta.paths.set)]);
    for(const id of [...delta.nodes.remove,...Object.keys(delta.nodes.set)])for(const p of reverse.get(String(id))||[])affected.add(p);
    for(const p of delta.paths.remove){detach(p,paths[p]);delete paths[p];}
    for(const [p,id] of Object.entries(delta.paths.set)){if(paths[p]!==undefined)detach(p,paths[p]);paths[p]=id;attach(p,id);}
    for(const id of delta.nodes.remove)delete nodes[id];
    Object.assign(nodes,delta.nodes.set);
    for(const p of affected){
      const next=identity(p),prior=last.get(p)||'null';
      if(next!==prior){if(!versions.has(p))versions.set(p,[1]);versions.get(p).push(record.sequence);last.set(p,next);}
    }
  }
  return versions;
}
if(typeof module!=='undefined')module.exports={buildVersionIndex};
