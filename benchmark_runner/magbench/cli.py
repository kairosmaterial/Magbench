import argparse,hashlib,json,os,traceback,time
from pathlib import Path
import numpy as np
from .physics import DEFAULTS,atoms_from,search_ground_state,fit_exchange,volume_exchange,phonons,head_exchange,head_volume_exchange,relaxed_atoms,dft_exchange_design,dft_exchange_atoms,relax_phonon_geometry,PHONON_RELAX_FMAX,PHONON_RELAX_MAX_STEPS

def load(p):return json.loads(Path(p).read_text())
def save(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(prog='magbench');sub=p.add_subparsers(dest='command',required=True)
 r=sub.add_parser('run');r.add_argument('--inputs',type=Path,required=True);r.add_argument('--checkpoint',type=Path,required=True);r.add_argument('--output',type=Path,required=True);r.add_argument('--device',default='cuda');r.add_argument('--moment-head',type=Path);r.add_argument('--no-moment-head',action='store_true');r.add_argument('--materials',nargs='*');r.add_argument('--stages',nargs='+',choices=['ground_state','J','magnetovolume','phonons'],default=['ground_state']);r.add_argument('--ground-state-barrier',type=Path);r.add_argument('--config',type=Path);r.add_argument('--exchange-method',choices=['energy-mapping','exchange-head'],default='exchange-head')
 s=sub.add_parser('score');s.add_argument('--targets',type=Path,required=True);s.add_argument('--predictions',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
 select=sub.add_parser('select');select.add_argument('--targets',type=Path,required=True);select.add_argument('--inputs',type=Path,required=True);select.add_argument('--run',type=Path,required=True);select.add_argument('--output',type=Path,required=True)
 a=p.parse_args()
 if a.command=='select':
  from .selection import selection_receipt
  ids=load(a.inputs/'manifest.json')['cohorts']['ground_state']
  save(a.output,selection_receipt(a.targets,ids,[a.run]))
  return
 if a.command=='score':
  from .scoring import evaluate
  result=evaluate(a.targets,load(a.predictions),a.predictions.resolve().parent);save(a.output,result);print(json.dumps({k:v for k,v in result.items() if k!='materials'},indent=2));return
 from .adapters import ProphetSpinV2
 cfg=DEFAULTS.copy()
 if a.config:cfg.update(load(a.config))
 manifest=load(a.inputs/'manifest.json');ids=a.materials or manifest['cohorts']['ground_state'];ids=[f'{int(k):03d}' for k in ids]
 if not set(ids)<=set(manifest['cohorts']['ground_state']):raise ValueError('Unknown material IDs')
 # Both model bytes and all inference inputs fingerprint resume state.
 input_hash=hashlib.sha256()
 for path in sorted(a.inputs.rglob('*')):
  if path.is_file():input_hash.update(str(path.relative_to(a.inputs)).encode());input_hash.update(digest(path).encode())
 head_path=None if a.no_moment_head else (a.moment_head or a.checkpoint.with_name(a.checkpoint.stem+'-head'+a.checkpoint.suffix))
 if head_path is not None and not head_path.exists():
  if a.moment_head:raise FileNotFoundError(head_path)
  head_path=None
 fingerprint=dict(moment_head_sha256=digest(head_path) if head_path else None,checkpoint_sha256=digest(a.checkpoint),input_sha256=input_hash.hexdigest(),settings=cfg,runner_version='0.6.0',exchange_method=a.exchange_method)
 a.output.mkdir(parents=True,exist_ok=True);stamp=a.output/'run.json'
 if stamp.exists() and load(stamp)!=fingerprint:raise ValueError('Refusing to mix results from different model, inputs or settings')
 prediction_file=a.output/'predictions.json';pred=load(prediction_file) if prediction_file.exists() else {};error_file=a.output/'errors.json';errors=load(error_file) if error_file.exists() else {}
 stages = [s for s in ('J','magnetovolume','phonons') if s in a.stages]
 if a.ground_state_barrier is None:
  if stages:
   p.error('Run the full ground-state phase and select experimental matches before requesting properties')
  stages.append('ground_state')
  selected = {}
  sign_reference = load(a.inputs/'screening_sign_reference.json')
 else:
  receipt = load(a.ground_state_barrier)
  if ('ground_state' in a.stages
      or set(receipt['terminal_materials']) != set(manifest['cohorts']['ground_state'])):
   raise ValueError('The full ground-state cohort must be terminal before launching properties')
  selected = receipt['selected_seed_indices']
  dft_moments = receipt['dft_moments_muB']
  if set(dft_moments) != set(selected):
   raise ValueError('Every selected material must have its signed DFT moments')
 if len(set(ids)) != len(ids):
  raise ValueError('Duplicate material IDs')
 save(stamp,fingerprint)
 if a.ground_state_barrier is not None:
  property_stamp = a.output/'property_run.json'
  selection_fingerprint = {'version': 'DFT-moments-25pct-v1', 'selection_sha256': digest(a.ground_state_barrier)}
  if property_stamp.exists() and load(property_stamp) != selection_fingerprint:
   raise ValueError('Existing properties use a different material selection or DFT magnetic state')
  if not property_stamp.exists() and any(
      f.stem != 'ground_state' for f in (a.output/'completed').glob('*/*.json')):
   raise ValueError('Existing properties predate the DFT magnetic protocol')
  save(property_stamp,selection_fingerprint)
 if any(stage in {'J','magnetovolume'} for stage in stages):
  exchange_stamp = a.output/'exchange_run.json'
  exchange_protocol = dict(geometry='DFT_reference', magnetic_state='signed_DFT')
  if exchange_stamp.exists() and load(exchange_stamp) != exchange_protocol:
   raise ValueError('Existing exchange results use a different reference geometry or magnetic state')
  if not exchange_stamp.exists() and any(
      f.stem in {'J','magnetovolume'} for f in (a.output/'completed').glob('*/*.json')):
   raise ValueError('Existing exchange results predate the DFT reference geometry protocol')
  save(exchange_stamp,exchange_protocol)
 if 'phonons' in stages:
  phonon_stamp = a.output/'phonon_run.json'
  phonon_protocol = dict(magnetic_state='selected_model_moments', optimize_cell=True,
                         fmax_eV_A=PHONON_RELAX_FMAX, max_steps=PHONON_RELAX_MAX_STEPS)
  if phonon_stamp.exists() and load(phonon_stamp) != phonon_protocol:
   raise ValueError('Existing phonons use a different refinement protocol')
  if not phonon_stamp.exists() and any((a.output/'completed').glob('*/phonons.json')):
   raise ValueError('Existing phonons predate the model-moment refinement protocol')
  save(phonon_stamp,phonon_protocol)
 model=ProphetSpinV2(a.checkpoint,a.device,head_checkpoint=head_path)

 for stage in stages:
  for key in ids:
   if key not in manifest['cohorts'][stage]:
    continue
   case = a.output/'completed'/key
   cache = case/f'{stage}.json'
   task = f'{key}/{stage}'
   if stage != 'ground_state' and key not in selected:
    errors[task] = dict(error='Skipped because no candidate passed the magnetic order, energy and moment-amplitude criteria')
    save(error_file,errors)
    continue
   if stage != 'ground_state':
    ground = load(case/'ground_state.json')
    candidate = next(c for c in ground['converged_candidates'] if c['seed_index']==selected[key])
    row = pred.setdefault(key,{})
    prior_seed = row.get('property_seed_index')
    if prior_seed is not None and prior_seed != selected[key]:
     raise ValueError(f'{key}: saved properties use a different ground-state selection')
    row.update(candidate,property_seed_index=selected[key])
   if cache.exists():
    pred.setdefault(key,{}).update(load(cache))
    continue
   try:
    model.progress = lambda **detail: save(
     a.output/'progress.json',dict(material=key,stage=stage,updated_unix=time.time(),**detail))
    model.progress(detail='starting')
    initial = load(a.inputs/f'ground_state/{key}.json')
    if stage == 'ground_state':
     result = search_ground_state(model,atoms_from(initial),cfg,initial['magnetic_site_indices'],
                                  sign_reference[key])
    else:
     if stage in ('J','magnetovolume'):
      moments = np.asarray(dft_moments[key],float)
      if moments.shape != (len(initial['species']),) or not np.isfinite(moments).all():
       raise ValueError('Invalid signed DFT moment array for the selected structure')
      row['property_magnetic_state']='signed_DFT'
      use_head = a.exchange_method=='exchange-head' and model.supports_exchange_head()
      if use_head:
       definition = load(a.inputs/f'exchange_head/{key}.json')
       reference = dft_exchange_atoms(initial,definition['unitcell'],moments)
       if stage=='J':
        values = head_exchange(model,definition,cfg,relaxed=reference)
       else:
        deltas = load(a.inputs/f'magnetovolume/{key}.json')['volume_deltas']
        values = head_volume_exchange(model,definition,cfg,deltas,relaxed=reference)
      else:
       folder = 'exchange' if stage=='J' else stage
       design = dft_exchange_design(load(a.inputs/f'{folder}/{key}.json'),initial,moments)
       values = fit_exchange(model,design,cfg) if stage=='J' else volume_exchange(model,design,cfg)
      field = 'J_meV' if stage=='J' else 'dJ_dlnV_meV'
      result = {field:values.tolist(),'exchange_method':'exchange-head' if use_head else 'energy-mapping',
                'exchange_reference_geometry':'DFT_reference'}
     else:
      relaxed = relaxed_atoms(initial,candidate)
      geometry_cache = a.output/'phonon_geometry'/f'{key}.json'
      if geometry_cache.exists():
       refinement = load(geometry_cache)
       relaxed.set_cell(refinement['cell_A'])
       relaxed.set_positions(refinement['positions_A'])
      else:
       relaxed,refinement = relax_phonon_geometry(model,relaxed)
       save(geometry_cache,refinement)
      with np.load(a.inputs/f'phonons/{key}/sampling.npz') as sampling:
       data = phonons(model,load(a.inputs/f'phonons/{key}/structure.json'),sampling,cfg,relaxed=relaxed)
      dest = a.output/f'phonons/{key}.npz'
      dest.parent.mkdir(exist_ok=True)
      np.savez_compressed(dest,**data)
      result = {'phonon_file':f'phonons/{key}.npz','phonon_relaxation':refinement,
                'phonon_magnetic_state':'selected_model_moments'}
    save(cache,result)
    pred.setdefault(key,{}).update(result)
    save(prediction_file,pred)
    if task in errors:
     del errors[task]
     save(error_file,errors)
    print(key,stage,'complete',flush=True)
   except Exception as exc:
    errors[task] = dict(error=str(exc),traceback=traceback.format_exc())
    if hasattr(exc,'screening'):
     errors[task]['screening'] = exc.screening
    save(error_file,errors)
    print(key,stage,'failed:',exc,flush=True)

 save(prediction_file,pred)
if __name__=='__main__':main()
