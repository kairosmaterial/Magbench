'use strict';
const assert = require('node:assert/strict');
const {scale, placeLabels, overlaps, finite} = require('../site/assets/plot-math.js');
let checks = 0;
for (const values of [[.43,.54,.60], [35.7,35.8,66.9], [0,0], [12], [-8,-2], [null,undefined,NaN], [.000001,.000002], [8e8,9e8]]) {
  const axis = scale(values, 10, 250), numbers=values.filter(finite);
  assert(axis.ticks.length >= 4 && axis.ticks.length <= 6);
  assert(axis.minimum < axis.maximum);
  for (const value of numbers) {assert(axis.minimum < value);assert(axis.maximum > value);}
  for (let i=1; i<axis.ticks.length; i++) assert(Math.abs((axis.ticks[i]-axis.ticks[i-1])-(axis.ticks[1]-axis.ticks[0])) < (axis.maximum-axis.minimum)*1e-10);
  assert.equal(axis.position(axis.minimum),10);assert.equal(axis.position(axis.maximum),250);
  const step=axis.ticks[1]-axis.ticks[0], normal=step / 10**Math.floor(Math.log10(step));
  assert([1,2,2.5,5,10].some(v=>Math.abs(v-normal)<1e-9));checks++;
}
const bounds={left:0,right:252,top:0,bottom:346};
for (const points of [
  [{id:'a',x:120,y:150,width:140,height:16},{id:'b',x:120,y:150,width:140,height:16}],
  [[0,0],[252,0],[0,346],[252,346]].map(([x,y],i)=>({id:String(i),x,y,width:140,height:16})),
  [{id:'valid',x:100,y:100,width:140,height:16},{id:'missing',x:null,y:100,width:140,height:16}],
  [0,1,2,3].map(i=>({id:String(i),x:140,y:150,width:140,height:16}))
]) {
  const labels=placeLabels(points,bounds);
  assert.equal(labels.length, points.filter(p=>finite(p.x)&&finite(p.y)).length);
  for (const a of labels) {
    assert(a.left>=bounds.left && a.top>=bounds.top);
    assert(a.left+a.width<=bounds.right && a.top+a.height<=bounds.bottom);
    for (const b of labels)if(a!==b)assert(!overlaps(a,b));
  }
  checks++;
}
assert.throws(()=>placeLabels([{x:1,y:1,width:300,height:16}],bounds),RangeError);
console.log(`${checks + 1} scale and label cases passed`);
