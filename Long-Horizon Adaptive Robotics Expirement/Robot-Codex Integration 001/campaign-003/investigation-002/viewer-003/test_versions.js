'use strict';
const assert=require('node:assert/strict');
const {buildVersionIndex}=require('./versions.js');
const change=(sequence,paths,nodes)=>({sequence,type:'mutation',delta:{paths:{remove:[],set:{},...paths},nodes:{remove:[],set:{},...nodes}}});
const rows=[{sequence:1,type:'initial',state:{paths:{'/a':1},nodes:{'1':{sha256:'A',size:1}}}},
 change(2,{set:{'/alias':1}},{}),
 change(3,{}, {set:{'1':{sha256:'B',size:1}}}),
 change(4,{remove:['/a'],set:{'/b':1}},{}),
 change(5,{remove:['/alias']},{}),
 change(6,{}, {set:{'1':{sha256:'B',size:1,mode:33188}}}),
 {sequence:7,type:'checkpoint'},
 change(8,{remove:['/b']},{remove:['1']})];
assert.deepEqual(Object.fromEntries(buildVersionIndex(rows)),{'/a':[1,3,4],'/alias':[1,2,3,5],'/b':[1,4,6,8]});
assert.equal(JSON.stringify(rows[0].state),'{"paths":{"/a":1},"nodes":{"1":{"sha256":"A","size":1}}}');
console.log(JSON.stringify({passed:true,checks:['hard-link content changes','rename and removal','metadata changes','checkpoint omission','input unchanged']}));
