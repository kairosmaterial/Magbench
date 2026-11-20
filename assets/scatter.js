'use strict';
window.MagbenchScatter = (container, models, table) => {
  const math = window.MagbenchPlotMath, NS = 'http://www.w3.org/2000/svg';
  const svg = container.querySelector('svg'), xSelect = container.querySelector('[name=x]'), ySelect = container.querySelector('[name=y]');
  const tooltip = container.querySelector('[role=tooltip]'), omitted = container.querySelector('.plot-omitted');
  const hp = entry => entry.card.hyperparams.architecture;
  const fields = [
    {key:'total', label:'Total (out of 1)', score:true, get:e=>e.card.metrics.total},
    ...[['ground_state','Ground state'],['hull','MP hull with spin'],['phonons','Phonons with spin'],['J','Exchange J'],['magnetovolume','dJ/dlnV']].map(([key, name])=>({key,label:`${name} (out of 0.2)`,score:true,get:e=>e.card.metrics[key]})),
    {key:'passes',label:`Ground-state passes (out of ${models[0]?.scores.dimensions.ground_state.materials ?? 'to be provided'})`,get:e=>e.card.metrics.ground_state_passes},
    {key:'cutoff',label:'Cutoff (Å)',get:e=>Array.isArray(hp(e).cutoff_A)?Math.max(...hp(e).cutoff_A):hp(e).cutoff_A},
    {key:'exchange_range',label:'Exchange range (Å)',get:e=>hp(e).exchange_range_A},
    {key:'training_frames',label:'Training frames',get:e=>e.training_frames},
    {key:'layers',label:'Layers',get:e=>hp(e).n_layers},
    {key:'params',label:'Parameters',get:e=>math.finite(hp(e).model_params)?hp(e).model_params/1e6:null}
  ];
  const byKey = key => fields.find(field=>field.key===key);
  const format = (field, value, tick=false) => field.key==='params' ? math.formatParameters(value,tick) : field.score ? value.toFixed(3) : Number(value.toPrecision(6)).toLocaleString('en-US', {maximumFractionDigits:6});
  const element = (tag, attributes={}, text) => {
    const node=document.createElementNS(NS,tag);
    for(const [key,value] of Object.entries(attributes))node.setAttribute(key,String(value));
    if(text!==undefined)node.textContent=text;
    return node;
  };
  for(const select of [xSelect,ySelect])for(const field of fields){const option=document.createElement('option');option.value=field.key;option.textContent=field.label;select.append(option);}
  let xKey='params', yKey='total', visible=models, activeKey=null, points=new Map(), animation=0;
  const nodes=new Map();
  const title=element('title',{id:'comparison-title'},'Model comparison');
  const description=element('desc',{id:'comparison-description'});
  const grid=element('g',{'class':'plot-grid','aria-hidden':'true'}), axes=element('g',{'class':'plot-axes','aria-hidden':'true'});
  const leaders=element('g',{'class':'plot-leaders','aria-hidden':'true'}), marks=element('g',{'class':'plot-marks'}), labels=element('g',{'class':'plot-labels','aria-hidden':'true'}), guides=element('g',{'class':'plot-guides','aria-hidden':'true'});
  svg.append(title,description,grid,axes,leaders,marks,labels,guides);
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  const rectangle = box => ({left:box.x, top:box.y, width:box.width, height:box.height});
  function restoreLabels() {
    for (const node of nodes.values()) if (node.current) {
      const point=node.current;
      node.label.setAttribute('x',point.labelX);node.label.setAttribute('y',point.labelY);
      node.leader.setAttribute('d',point.leader?`M${point.x},${point.y}L${point.anchorX},${point.anchorY}`:'');
    }
  }
  function highlight(key) {
    activeKey=key;
    for(const [id,node] of nodes){node.group.classList.toggle('is-active',id===key);node.group.classList.toggle('is-dimmed',!!key&&id!==key);node.label.classList.toggle('is-dimmed',!!key&&id!==key);}
    for(const row of table.querySelectorAll('tbody tr[data-key]'))row.classList.toggle('linked-highlight',row.dataset.key===key);
    restoreLabels();
    for(const tick of axes.querySelectorAll('.plot-tick'))tick.removeAttribute('visibility');
    guides.replaceChildren();tooltip.hidden=true;
    const point=points.get(key);if(!point)return;
    const {x,y,left,bottom,xField,yField,entry}=point;
    guides.append(element('path',{d:`M${left},${y}H${x}V${bottom}`}));
    for(const [tx,ty,field,value,anchor] of [[x,bottom+18,xField,point.xValue,'middle'],[left-9,y+4,yField,point.yValue,'end']]){
      const text=element('text',{x:tx,y:ty,'text-anchor':anchor},format(field,value));guides.append(text);
      const box=text.getBBox();const background=element('rect',{'class':'plot-guide-plate',x:box.x-4,y:box.y-3,width:box.width+8,height:box.height+6});guides.insertBefore(background,text);
    }
    const ticks=[...axes.querySelectorAll('.plot-tick')], plates=[...guides.querySelectorAll('rect')].map(node=>rectangle(node.getBBox()));
    for(const index of math.hiddenTicks(plates,ticks.map(node=>rectangle(node.getBBox()))))ticks[index].setAttribute('visibility','hidden');
    const name=document.createElement('strong');name.textContent=entry.card.model_name;
    const org=document.createElement('div');org.className='muted';org.textContent=entry.card.notes?.organisation||'to be provided';
    const values=document.createElement('dl');
    for(const field of fields){const value=field.get(entry);if(field.key==='training_frames'&&!math.finite(value))continue;const label=document.createElement('dt'),number=document.createElement('dd');label.textContent=field.key==='passes'?'Passes':field.label.replace(/ \(out of [^)]+\)/,'');number.textContent=math.finite(value)?(field.key==='params'?`${value.toFixed(1)}M`:field.key==='cutoff'&&Array.isArray(hp(entry).cutoff_A)?hp(entry).cutoff_A.join(' / '):format(field,value)):'to be provided';values.append(label,number);}
    tooltip.replaceChildren(name,org,values);tooltip.hidden=false;
    const box=container.getBoundingClientRect(),plot=svg.getBoundingClientRect();
    if(plot.top>=innerHeight||plot.bottom<=0){tooltip.hidden=true;return;}
    const bounds={left:Math.max(8,8-plot.left),right:Math.min(svg.clientWidth-8,innerWidth-8-plot.left),top:Math.max(8,8-plot.top),bottom:Math.min(svg.clientHeight-8,innerHeight-8-plot.top)};
    const guideObstacles=[{left,top:y-1,width:x-left,height:2},{left:x-1,top:y,width:2,height:bottom-y}];
    const markObstacles=[...points.values()].map(p=>({left:p.x-10,top:p.y-10,width:20,height:20}));
    const labelObstacles=[...nodes.values()].map(node=>rectangle(node.label.getBBox()));
    const axisObstacles=[...axes.querySelectorAll('text')].filter(node=>node.getAttribute('visibility')!=='hidden').map(node=>rectangle(node.getBBox())).filter(rect=>rect.left>=0&&rect.top>=0);
    const fixed=[...guideObstacles,...markObstacles,...axisObstacles];
    let placement=null, movedLabels=null;
    for(const allowMove of [false,true]){
      for(const width of [Math.min(260,svg.clientWidth-16),230,210,200,190,180,170,160]){
        tooltip.style.width=`${width}px`;
        const tip=tooltip.getBoundingClientRect();
        const candidate=math.placeTooltip({x,y},{width:tip.width,height:tip.height},bounds,[...fixed,...(allowMove?[]:labelObstacles)]);
        if(!candidate)continue;
        if(allowMove){
          try{movedLabels=math.placeLabels([...points.values()],{left:69,right:svg.clientWidth-19,top:27,bottom:svg.clientHeight-68},[candidate]);}
          catch{continue;}
        }
        placement=candidate;break;
      }
      if(placement)break;
    }
    if(!placement){tooltip.hidden=true;return;}
    if(movedLabels)for(const label of movedLabels){
      const node=nodes.get(label.id),p=points.get(label.id);
      node.label.setAttribute('x',label.left);node.label.setAttribute('y',label.top);
      node.leader.setAttribute('d',label.leader?`M${p.x},${p.y}L${label.anchorX},${label.anchorY}`:'');
    }
    tooltip.dataset.side=placement.side;
    tooltip.style.left=`${plot.left-box.left+placement.left}px`;
    tooltip.style.top=`${plot.top-box.top+placement.top}px`;

  }
  function makeNode(entry) {
    const id=entry.card.model_key;
    const group=element('g',{'class':'plot-mark',tabindex:0,role:'link','data-key':id,'aria-describedby':'comparison-tooltip'});
    group.append(element('circle',{'class':'plot-hit',r:19}),element('circle',{'class':'plot-focus',r:13}),element('circle',{'class':'plot-dot',r:7}));
    const label=element('text',{'class':'plot-label','dominant-baseline':'hanging'},entry.card.model_name);
    const leader=element('path');
    const open=()=>{location.href=`models/${id}.html`;};
    group.addEventListener('click',open);
    group.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();open();}});
    const leave=()=>highlight(document.activeElement?.classList.contains('plot-mark')?document.activeElement.dataset.key:null);
    group.addEventListener('pointerenter',()=>highlight(id));group.addEventListener('pointerleave',leave);
    let pointerFocus=false;
    group.addEventListener('pointerdown',()=>{pointerFocus=true;});
    for(const event of ['pointerup','pointercancel'])group.addEventListener(event,()=>{pointerFocus=false;});
    group.addEventListener('focus',()=>{const frame=svg.getBoundingClientRect();if(!pointerFocus&&(frame.top<8||frame.bottom>innerHeight-8))svg.scrollIntoView({block:'center',behavior:'instant'});highlight(id);requestAnimationFrame(()=>{if(document.activeElement===group)highlight(id);});});group.addEventListener('blur',()=>highlight(null));
    label.addEventListener('pointerenter',()=>highlight(id));label.addEventListener('pointerleave',leave);label.addEventListener('click',open);
    marks.append(group);labels.append(label);leaders.append(leader);
    const node={group,label,leader};nodes.set(id,node);return node;
  }
  function draw() {
    const width=svg.clientWidth;
    if(!svg.isConnected||width<250)return;
    const previousActive=activeKey;
    cancelAnimationFrame(animation);highlight(null);
    const height=width<540?(models.length>3?620:520):460;
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.style.height=`${height}px`;
    const left=66,right=width-16,top=24,bottom=height-65;
    const xField=byKey(xKey),yField=byKey(yKey);
    const included=visible.filter(e=>math.finite(xField.get(e))&&math.finite(yField.get(e)));
    omitted.textContent=visible.length===included.length?'':`not shown: ${visible.filter(e=>!included.includes(e)).map(e=>e.card.model_name).join(', ')}`;
    omitted.hidden=!omitted.textContent;
    description.textContent=`X: ${xField.label}. Y: ${yField.label}. ${included.length} models shown. The leaderboard table contains the complete data view.`;
    xSelect.value=xKey;ySelect.value=yKey;
    for(const button of container.querySelectorAll('[data-preset]'))button.setAttribute('aria-pressed',String(button.dataset.x===xKey&&button.dataset.y===yKey));
    const sx=math.scale(included.map(xField.get),left,right),sy=math.scale(included.map(yField.get),bottom,top);
    grid.replaceChildren();axes.replaceChildren();
    for(const value of sx.ticks){const x=sx.position(value);grid.append(element('line',{x1:x,x2:x,y1:top,y2:bottom}));axes.append(element('text',{'class':'plot-tick','data-axis':'x',x,y:bottom+20,'text-anchor':'middle'},format(xField,value,true)));}
    for(const value of sy.ticks){const y=sy.position(value);grid.append(element('line',{x1:left,x2:right,y1:y,y2:y}));axes.append(element('text',{'class':'plot-tick','data-axis':'y',x:left-9,y:y+4,'text-anchor':'end'},format(yField,value,true)));}
    axes.append(element('path',{d:`M${left},${top}V${bottom}H${right}`}));
    axes.append(element('text',{'class':'plot-axis-title',x:(left+right)/2,y:height-12,'text-anchor':'middle'},xField.label));
    axes.append(element('text',{'class':'plot-axis-title',transform:`translate(14 ${(top+bottom)/2}) rotate(-90)`,'text-anchor':'middle'},yField.label));
    const wanted=new Set(included.map(e=>e.card.model_key));
    for(const [key,node] of nodes)if(!wanted.has(key)){node.group.remove();node.label.remove();node.leader.remove();nodes.delete(key);}
    const targets=included.map((entry,index)=>{
      const key=entry.card.model_key,node=nodes.get(key)||makeNode(entry);
      if(marks.children[index]!==node.group)marks.insertBefore(node.group,marks.children[index]||null);
      const xValue=xField.get(entry),yValue=yField.get(entry);
      node.group.setAttribute('aria-label',`${entry.card.model_name}. ${xField.label}: ${format(xField,xValue)}. ${yField.label}: ${format(yField,yValue)}. Open model page.`);
      return {id:key,entry,x:sx.position(xValue),y:sy.position(yValue),width:node.label.getComputedTextLength(),height:16,xValue,yValue,left,bottom,xField,yField};
    });
    const placements=math.placeLabels(targets,{left:left+3,right:right-3,top:top+3,bottom:bottom-3});
    const origins=new Map([...nodes].map(([key,node])=>[key,node.current]));points=new Map();
    for(const point of targets){const label=placements.find(p=>p.id===point.id);points.set(point.id,{...point,labelX:label.left,labelY:label.top,anchorX:label.anchorX,anchorY:label.anchorY,leader:label.leader});}
    const started=performance.now(),duration=reduced.matches?0:400;
    function frame(now){
      const progress=duration?Math.min(1,(now-started)/duration):1,ease=1-(1-progress)**3;
      for(const [key,point] of points){
        const node=nodes.get(key),from=origins.get(key)||point,mix=prop=>from[prop]+(point[prop]-from[prop])*ease;
        const x=mix('x'),y=mix('y');
        node.current={...point,x,y,labelX:mix('labelX'),labelY:mix('labelY'),anchorX:mix('anchorX'),anchorY:mix('anchorY')};
        node.group.setAttribute('transform',`translate(${x} ${y})`);node.label.setAttribute('x',mix('labelX'));node.label.setAttribute('y',mix('labelY'));
        node.leader.setAttribute('d',point.leader?`M${x},${y}L${mix('anchorX')},${mix('anchorY')}`:'');
      }
      if(progress<1)animation=requestAnimationFrame(frame);
    }
    frame(started);
    if(document.activeElement?.classList.contains('plot-mark'))highlight(document.activeElement.dataset.key);
    else if(previousActive&&points.has(previousActive))highlight(previousActive);
    return targets.length;
  }
  function axesFromHash(){
    const hash=new URLSearchParams(location.hash.slice(1));
    if(byKey(hash.get('x'))&&byKey(hash.get('y'))){xKey=hash.get('x');yKey=hash.get('y');}
  }
  function changeAxes(x,y){
    xKey=x;yKey=y;const hash=`#x=${encodeURIComponent(x)}&y=${encodeURIComponent(y)}`;
    try{history.replaceState(null,'',hash);}catch{location.hash=hash;}
    draw();
  }
  xSelect.addEventListener('change',()=>changeAxes(xSelect.value,ySelect.value));ySelect.addEventListener('change',()=>changeAxes(xSelect.value,ySelect.value));
  for(const button of container.querySelectorAll('[data-preset]'))button.addEventListener('click',()=>changeAxes(button.dataset.x,button.dataset.y));
  window.addEventListener('hashchange',()=>{axesFromHash();draw();});
  table.addEventListener('pointerover',event=>{const row=event.target.closest('tbody tr[data-key]');if(row)highlight(row.dataset.key);});
  table.addEventListener('pointerout',event=>{if(!table.contains(event.relatedTarget))highlight(null);});
  table.addEventListener('focusin',event=>{const row=event.target.closest('tbody tr[data-key]');if(row)highlight(row.dataset.key);});
  table.addEventListener('focusout',event=>{if(!table.contains(event.relatedTarget))highlight(null);});
  window.addEventListener('scroll',()=>{if(activeKey)requestAnimationFrame(()=>{if(activeKey)highlight(activeKey);});},{passive:true});
  new ResizeObserver(()=>draw()).observe(svg);
  reduced.addEventListener('change',draw);axesFromHash();
  if(!location.hash){try{history.replaceState(null,'',`#x=${xKey}&y=${yKey}`);}catch{location.hash=`x=${xKey}&y=${yKey}`;}}
  return {update(entries){visible=models.filter(e=>entries.includes(e));draw();},highlight};
};
