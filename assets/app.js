'use strict';
(() => {
  const materialSearch = document.getElementById('material-search');
  if (materialSearch) materialSearch.addEventListener('input', () => {
    const query = materialSearch.value.toLowerCase().trim(); let count = 0;
    document.querySelectorAll('#materials tbody tr').forEach(row => {
      row.hidden = !row.cells[0].textContent.toLowerCase().includes(query);
      if (!row.hidden) count++;
    });
    document.getElementById('material-count').textContent = `${count} materials`;
  });
  document.querySelectorAll('.table-frame,.document table').forEach(frame=>{
    const scrollState=()=>frame.classList.toggle('is-scrolled',frame.scrollLeft>0);
    frame.addEventListener('scroll',scrollState,{passive:true});scrollState();
  });
  const table = document.getElementById('leaderboard');
  if (!table) return;
  const data = JSON.parse(document.getElementById('page-data').textContent);
  const models = data.models;
  const groups = {total:'Overall',ground_state:'Ground state',hull:'MP hull with spin',phonons:'Phonons with spin',J:'Exchange J',magnetovolume:'dJ/dlnV',model:'Model',identity:'Model',hyperparams:'Hyperparameters'};
  const metric = (id, label, group=id, max=.2) => ({id,label,group,max,numeric:true,score:true,get:e=>e.scores.dimensions[id]?.weighted_score ?? e.scores.total_score});
  const component = (dim,part) => ({id:`${dim}.${part}`,label:part[0].toUpperCase()+part.slice(1),group:dim,max:.1,numeric:true,score:true,get:e=>e.scores.dimensions[dim][`${part}_weighted_score`]});
  const prop = (id,label,get,group='model',numeric=false) => ({id,label,get,group,numeric});
  const identity=prop('name','Rank / model / organisation',e=>e.card.model_name,'identity');
  const total=metric('total','Total','total',1);
  const passes=prop('passes','Passes',e=>e.card.metrics.ground_state_passes,'ground_state',true);
  const dimensions=['ground_state','hull','phonons','J','magnetovolume'];
  const moment=prop('moment','Moments',e=>e.card.evaluation.moment_initialisation.replaceAll('_',' '));
  const route=prop('route','Exchange route',e=>e.card.evaluation.exchange_route.replaceAll('_',' '));
  const openness=prop('openness','Code / weights licence',e=>`${(e.card.license?.code ?? "pending")} / ${(e.card.license?.checkpoint ?? "pending")}`);
  const architecture=e=>e.card.hyperparams.architecture;
  const cutoff={...prop('cutoff','Cutoff (Å)',e=>{const v=architecture(e).cutoff_A;return Array.isArray(v)?Math.max(...v):v;},'hyperparams',true),format:e=>{const v=architecture(e).cutoff_A;return Array.isArray(v)?v.join(' / '):String(v);}};
  const exchangeRange=prop('exchange_range','Exchange range (Å)',e=>architecture(e).exchange_range_A,'hyperparams',true);
  const layers=prop('layers','Layers',e=>architecture(e).n_layers,'hyperparams',true);
  const params={...prop('params','Parameters',e=>architecture(e).model_params,'hyperparams',true),format:e=>typeof architecture(e).model_params==='number'?`${(architecture(e).model_params/1e6).toFixed(1)}M`:'pending'};
  const training=prop('training','Training data',e=>e.training_frames,'model',true);
  const hyperparams=[cutoff,exchangeRange,layers,params];
  const sets={
    scores:[identity,total,metric('ground_state','Score'),passes,...dimensions.slice(1).map(k=>metric(k,'Score')),moment,route,openness,training,...hyperparams],
    components:[identity,total,metric('ground_state','Score'),passes,component('hull','sign'),component('hull','accuracy'),component('phonons','stability'),component('phonons','spectrum'),component('J','sign'),component('J','accuracy'),component('magnetovolume','sign'),component('magnetovolume','accuracy'),moment,route,openness,training,...hyperparams],
    details:[identity,total,metric('ground_state','Score'),passes,...dimensions.slice(1).map(k=>metric(k,'Score')),moment,prop('seeds','Seed amplitudes',e=>e.card.evaluation.seed_amplitudes.replaceAll('_',' ')),route,openness,prop('status','Status',e=>e.card.lifecycle==='active'?'complete':e.card.lifecycle),prop('added','Added',e=>e.card.dates.benchmark_added),training,...hyperparams]
  };
  const scatter=window.MagbenchScatter(document.getElementById('comparison'),models,table);
  let columnSet='scores',sortKey='total',direction=-1;
  const filterOptions={
    moment:[['all','Moments: all'],['moment_head','Moments: head'],['energy_gradient','Moments: energy gradient']],
    exchange:[['all','Exchange: all'],['exchange_readout','Exchange: readout'],['energy_mapping','Exchange: mapping']],
    openness:[['all','Openness: all'],['public','Openness: public artefacts'],['awaiting','Openness: awaiting artefacts'],['MIT','Licence: MIT code']]
  };
  const filterState={moment:0,exchange:0,openness:0};
  const textNode=(tag,text,cls)=>{const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;};
  const columnByKey = id => Object.values(sets).flat().find(c=>c.id===id);
  function matches(entry) {
    const c=entry.card,q=document.getElementById('model-search').value.trim().toLowerCase();
    if(!`${c.model_name} ${c.notes?.organisation||''}`.toLowerCase().includes(q))return false;
    for (const [name, index] of Object.entries(filterState)) {
      const value=filterOptions[name][index][0]; if(value==='all')continue;
      if(name==='moment'&&c.evaluation.moment_initialisation!==value)return false;
      if(name==='exchange'&&c.evaluation.exchange_route!==value)return false;
      if(name==='openness'){
        const isPublic=c.publication_status!=='awaiting_artifacts'&&c.repo?.startsWith('https://')&&c.checkpoint?.url?.startsWith('https://')&&c.predictions?.url?.startsWith('https://');
        if(value==='public'&&!isPublic)return false;
        if(value==='awaiting'&&isPublic)return false;
        if(value==='MIT'&&c.license?.code!=='MIT')return false;
      }
    }
    return true;
  }
  function header(columns) {
    const head=table.tHead;head.replaceChildren();
    const groupRow=head.insertRow();groupRow.className='groups';
    for(let i=0;i<columns.length;){let end=i+1;while(end<columns.length&&columns[end].group===columns[i].group)end++;
      const th=textNode('th',groups[columns[i].group]||'');th.colSpan=end-i;th.scope='colgroup';th.classList.add('group-start');groupRow.append(th);i=end;
    }
    const row=head.insertRow();row.className='columns';
    for(const [index,col] of columns.entries()){
      const th=document.createElement('th');th.scope='col';th.setAttribute('aria-sort',sortKey===col.id?(direction===-1?'descending':'ascending'):'none');
      if(index===0||columns[index-1].group!==col.group)th.classList.add('group-start');
      if(index===columns.length-1||columns[index+1].group!==col.group)th.classList.add('group-end');
      if(index===1)th.classList.add('after-identity');
      if(col.numeric)th.classList.add('num');
      if(col.group==='hyperparams')th.classList.add('hyperparam');
      const button=textNode('button',col.label);button.type='button';button.dataset.column=col.id;
      const arrow=textNode('span',sortKey===col.id?(direction===-1?'↓':'↑'):'↕','sort-arrow');arrow.setAttribute('aria-hidden','true');button.append(arrow);
      button.addEventListener('click',()=>{direction=sortKey===col.id?-direction:(col.numeric?-1:1);sortKey=col.id;render();table.querySelector(`[data-column="${col.id}"]`).focus();});
      th.append(button);row.append(th);
    }
  }
  function render() {
    const columns=sets[columnSet];header(columns);
    const sortColumn=columnByKey(sortKey);const visible=models.filter(matches).sort((a,b)=>{
      const x=sortColumn.get(a),y=sortColumn.get(b);
      if(x==null)return y==null?0:1;if(y==null)return -1;
      const difference=sortColumn.numeric?x-y:String(x).localeCompare(String(y));
      return difference*direction||a.card.model_key.localeCompare(b.card.model_key);
    });
    const body=table.tBodies[0];body.replaceChildren();
    const best={};for(const col of columns.filter(c=>c.numeric))best[col.id]=Math.max(...models.map(col.get).filter(x=>typeof x==='number'));
    for(const entry of visible){
      const c=entry.card,row=body.insertRow();row.tabIndex=0;row.dataset.key=c.model_key;
      const target=`models/${c.model_key}.html`;
      row.setAttribute('aria-label',`${c.model_name}, total ${c.metrics.total.toFixed(3)}. Open model page.`);
      row.addEventListener('click',event=>{if(!event.target.closest('a'))location.href=target;});
      row.addEventListener('keydown',event=>{if(event.target===row&&['Enter',' '].includes(event.key)){event.preventDefault();location.href=target;}});
      for(const [index,col] of columns.entries()){const td=row.insertCell(),value=col.get(entry);td.dataset.value=value??'';
        if(index===0||columns[index-1].group!==col.group)td.classList.add('group-start');
        if(index===columns.length-1||columns[index+1].group!==col.group)td.classList.add('group-end');
        if(index===1)td.classList.add('after-identity');
        if(col===identity){
          td.append(textNode('span',String(models.indexOf(entry)+1).padStart(2,'0'),'rank'));
          const anchor=textNode('a',c.model_name,'model-name');anchor.href=target;td.append(anchor);
          td.append(textNode('span',c.notes?.organisation||'pending','organisation'));
        }else{
          td.textContent=value==null?(col.id==='params'?'pending':'—'):col.score?value.toFixed(3):String(value);
          if(col.numeric)td.classList.add('num');
          if(col.group==='hyperparams')td.classList.add('hyperparam');
          if(col.format)td.textContent=col.format(entry);
          if(col===training){
            td.replaceChildren();
            entry.training_data.forEach((item,index)=>{
              if(index)td.append(document.createTextNode(' + '));
              const link=textNode('a',item.name);link.href=`datasets.html#${item.dataset_key}`;td.append(link);
              if('subset' in item)td.append(document.createTextNode(' (subset)'));
            });
          }
          if(col.score)td.classList.add('score');
          if((col.score||col.id==='passes')&&value===best[col.id])td.classList.add('best');
          if(col.id==='passes')td.textContent=`${value} / ${entry.scores.dimensions.ground_state.materials}`;
        }
      }
    }
    if(!visible.length){const cell=body.insertRow().insertCell();cell.colSpan=columns.length;cell.textContent='No models match these filters.';cell.style.position='static';}
    scatter.update(visible);
    document.getElementById('model-count').textContent=`${visible.length} of ${models.length} models`;
  }
  document.querySelectorAll('[data-set]').forEach(button=>button.addEventListener('click',()=>{
    columnSet=button.dataset.set;
    if(!sets[columnSet].some(c=>c.id===sortKey)){sortKey='total';direction=-1;}
    document.querySelectorAll('[data-set]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();
  }));
  document.querySelectorAll('[data-filter]').forEach(button=>{
    button.setAttribute('aria-pressed','false');
    button.addEventListener('click',()=>{const name=button.dataset.filter;filterState[name]=(filterState[name]+1)%filterOptions[name].length;button.textContent=filterOptions[name][filterState[name]][1];button.setAttribute('aria-pressed',String(filterState[name]!==0));render();});
  });
  document.getElementById('reset-filters').addEventListener('click',()=>{
    document.getElementById('model-search').value='';
    for(const name of Object.keys(filterState)){filterState[name]=0;const b=document.querySelector(`[data-filter="${name}"]`);b.textContent=filterOptions[name][0][1];b.setAttribute('aria-pressed','false');}render();
  });
  document.getElementById('model-search').addEventListener('input',render);render();
})();
