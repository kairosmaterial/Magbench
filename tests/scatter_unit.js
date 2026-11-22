'use strict';
const assert = require('node:assert/strict');
const {scale, placeLabels, overlaps, finite, placeTooltip, hiddenTicks, formatParameters} = require('../site/assets/plot-math.js');
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

assert.equal(formatParameters(35.836962), '35.8M');
assert.equal(formatParameters(30, true), '30M');
assert.equal(formatParameters(35.8, true), '35.8M');
for (const point of [{x:25,y:25},{x:325,y:25},{x:25,y:415},{x:325,y:415}]) {
  const guide=[{left:20,top:point.y-1,width:point.x-20,height:2},{left:point.x-1,top:point.y,width:2,height:420-point.y}];
  const mark={left:point.x-10,top:point.y-10,width:20,height:20};
  const box=placeTooltip(point,{width:160,height:210},{left:8,right:342,top:8,bottom:432},[...guide,mark]);
  assert(box);
  assert(box.left>=8 && box.top>=8 && box.left+box.width<=342 && box.top+box.height<=432);
  for(const obstacle of [...guide,mark])assert(!overlaps(box,obstacle,0));
}
const ticks=[{left:50,top:400,width:30,height:14},{left:4,top:100,width:35,height:14},{left:140,top:400,width:30,height:14}];
// Values less than one tenth of the tick spacing away on both axes.
const plates=[{left:52,top:399,width:36,height:20},{left:2,top:102,width:43,height:20}];
assert.deepEqual(hiddenTicks(plates,ticks),[0,1]);
assert.deepEqual(hiddenTicks([],ticks),[]);
const obstacle={left:90,top:120,width:130,height:180};
const moved=placeLabels([{id:'a',x:75,y:100,width:140,height:16},{id:'b',x:75,y:230,width:140,height:16}],{left:66,right:334,top:24,bottom:375},[obstacle]);
for(const label of moved)assert(!overlaps(label,obstacle));
for(const vertical of [false,true]) {
  const axis=scale([.05,.1005,.195],0,300), tick=axis.ticks[2], step=axis.ticks[1]-axis.ticks[0];
  const near=tick+step*.05, at=axis.position(tick), guide=axis.position(near);
  assert(Math.abs(near-tick)<step*.1);
  const label=vertical?{left:0,top:at-7,width:30,height:14}:{left:at-15,top:0,width:30,height:14};
  const plate=vertical?{left:0,top:guide-10,width:38,height:20}:{left:guide-19,top:0,width:38,height:20};
  assert.deepEqual(hiddenTicks([plate],[label]),[0]);
}
console.log('Tooltip placement, tick plates and parameter formatting passed');
