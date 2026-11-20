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
  const table = document.getElementById('leaderboard');
  if (!table) return;
  const data = JSON.parse(document.getElementById('page-data').textContent);
  const models = data.models;
  const groups = {total:'Overall',ground_state:'Ground state',hull:'MP hull',phonons:'Phonons',J:'Exchange J',magnetovolume:'dJ/dlnV',model:'Model'};
  const metric = (id, label, group=id, max=.2) => ({id,label,group,max,numeric:true,score:true,get:e=>e.scores.dimensions[id]?.weighted_score ?? e.scores.total_score});
  const component = (dim,part) => ({id:`${dim}.${part}`,label:part[0].toUpperCase()+part.slice(1),group:dim,max:.1,numeric:true,score:true,get:e=>e.scores.dimensions[dim][`${part}_weighted_score`]});
  const prop = (id,label,get,group='model',numeric=false) => ({id,label,get,group,numeric});
  const identity=prop('name','Rank / model / organisation',e=>e.card.model_name,'identity');
  const total=metric('total','Total','total',1);
  const passes=prop('passes','Passes',e=>e.card.metrics.ground_state_passes,'ground_state',true);
  const dimensions=['ground_state','hull','phonons','J','magnetovolume'];
  const moment=prop('moment','Moments',e=>e.card.evaluation.moment_initialisation.replaceAll('_',' '));
  const route=prop('route','Exchange route',e=>e.card.evaluation.exchange_route.replaceAll('_',' '));
  const openness=prop('openness','Code / weights licence',e=>`${e.card.license.code} / ${e.card.license.checkpoint}`);
  const informed=prop('informed','Test-set-informed',e=>e.card.test_set_informed===true?'Yes':e.card.test_set_informed===false?'No':'Unknown');
  const version=prop('protocol','Protocol / data',e=>`${e.card.evaluation.protocol_version} / ${e.card.evaluation.data_version}`);
  const sets={
    scores:[identity,total,metric('ground_state','Score'),passes,...dimensions.slice(1).map(k=>metric(k,'Score')),moment,route,openness,informed,version],
    components:[identity,total,metric('ground_state','Score'),passes,component('hull','sign'),component('hull','accuracy'),component('phonons','stability'),component('phonons','spectrum'),component('J','sign'),component('J','accuracy'),component('magnetovolume','sign'),component('magnetovolume','accuracy')],
    details:[identity,total,passes,prop('params','Parameters',e=>typeof e.card.model_params==='number'?e.card.model_params:null,'model',true),moment,prop('seeds','Seed amplitudes',e=>e.card.evaluation.seed_amplitudes.replaceAll('_',' ')),route,openness,informed,version,prop('status','Status',e=>e.card.publication_status?'Awaiting artefacts':e.card.lifecycle),prop('added','Added',e=>e.card.dates.benchmark_added)]
  };
  let columnSet='scores',sortKey='total',direction=-1;
  const filterOptions={
    moment:[['all','Moments: all'],['moment_head','Moments: head'],['energy_gradient','Moments: energy gradient']],
    exchange:[['all','Exchange: all'],['exchange_readout','Exchange: readout'],['energy_mapping','Exchange: mapping']],
    openness:[['all','Openness: all'],['public','Openness: public artefacts'],['awaiting','Openness: awaiting artefacts'],['MIT','Licence: MIT code']],
    informed:[['all','Test set: all'],['true','Test set: informed'],['false','Test set: not informed'],['unknown','Test set: unknown']]
  };
  const filterState={moment:0,exchange:0,openness:0,informed:0};
  const textNode=(tag,text,cls)=>{const el=document.createElement(tag);el.textContent=text;if(cls)el.className=cls;return el;};
  const columnByKey = id => Object.values(sets).flat().find(c=>c.id===id);
  function matches(entry) {
    const c=entry.card,q=document.getElementById('model-search').value.trim().toLowerCase();
    if(!`${c.model_name} ${c.notes?.organisation||''}`.toLowerCase().includes(q))return false;
    for (const [name, index] of Object.entries(filterState)) {
      const value=filterOptions[name][index][0]; if(value==='all')continue;
      if(name==='moment'&&c.evaluation.moment_initialisation!==value)return false;
      if(name==='exchange'&&c.evaluation.exchange_route!==value)return false;
      if(name==='informed'&&(typeof c.test_set_informed==='boolean'?String(c.test_set_informed):'unknown')!==value)return false;
      if(name==='openness'){
        const isPublic=c.repo.startsWith('https://')&&c.checkpoint.url.startsWith('https://')&&c.predictions.url.startsWith('https://');
        if(value==='public'&&!isPublic)return false;
        if(value==='awaiting'&&isPublic)return false;
        if(value==='MIT'&&c.license.code!=='MIT')return false;
      }
    }
    return true;
  }
  function header(columns) {
    const head=table.tHead;head.replaceChildren();
    const groupRow=head.insertRow();groupRow.className='groups';
    for(let i=0;i<columns.length;){let end=i+1;while(end<columns.length&&columns[end].group===columns[i].group)end++;
      const th=textNode('th',groups[columns[i].group]||'');th.colSpan=end-i;th.scope='colgroup';groupRow.append(th);i=end;
    }
    const row=head.insertRow();row.className='columns';
    for(const col of columns){
      const th=document.createElement('th');th.scope='col';th.setAttribute('aria-sort',sortKey===col.id?(direction===-1?'descending':'ascending'):'none');
      if(col.numeric)th.classList.add('num');
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
      for(const col of columns){const td=row.insertCell(),value=col.get(entry);td.dataset.value=value??'';
        if(col===identity){
          td.append(textNode('span',String(models.indexOf(entry)+1).padStart(2,'0'),'rank'));
          const anchor=textNode('a',c.model_name,'model-name');anchor.href=target;td.append(anchor);
          if(c.test_set_informed===true){const m=textNode('span','†','marker');m.title='Test-set-informed';td.append(m);}
          if(c.lifecycle==='reference'){const m=textNode('span','◇','marker');m.title='Reference: replay unavailable';td.append(m);}
          if(c.publication_status){const m=textNode('span','○','marker');m.title='Awaiting artefacts';td.append(m);}
          td.append(textNode('span',c.notes?.organisation||'TODO(owner)','organisation'));
          if(c.publication_status)td.append(textNode('span','weights and inference code to be released','row-status'));
          if(c.lifecycle==='reference')td.append(textNode('span','Reference · replay unavailable','row-status'));
        }else{
          td.textContent=value==null?'—':col.score?value.toFixed(3):String(value);
          if(col.numeric)td.classList.add('num');
          if(col.score){td.classList.add('score');td.style.setProperty('--fill',String(Math.max(0,Math.min(1,value/col.max))));}
          if(col.numeric&&value===best[col.id])td.classList.add('best');
          if(col.id==='passes')td.textContent=`${value} / ${entry.scores.dimensions.ground_state.materials}`;
        }
      }
    }
    if(!visible.length){const cell=body.insertRow().insertCell();cell.colSpan=columns.length;cell.textContent='No models match these filters.';cell.style.position='static';}
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
