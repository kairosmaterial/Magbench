"""Merge disjoint GPU shards and score; unfinished runs are explicitly provisional."""
import argparse,json,os,shutil,time
from pathlib import Path
from .cli import load,save
from .scoring import evaluate

def collect(root,targets):
 launch=load(root/'launch.json');pred={};workers=[];counts={'ground_state':0,'J':0,'magnetovolume':0,'phonons':0}
 destination=root/'combined';destination.mkdir(exist_ok=True)
 for w in launch['workers']:
  out=Path(w['output'])
  try:
   command=(Path('/proc')/str(w['pid'])/'cmdline').read_bytes().split(b'\0')
   running=str(out).encode() in command and b'magbench.cli' in command
  except FileNotFoundError:running=False
  rows=load(out/'predictions.json') if (out/'predictions.json').exists() else {}
  for k,row in rows.items():
   if k in pred:raise ValueError('Overlapping shard material IDs')
   row=dict(row)
   if 'phonon_file' in row:
    src=out/row['phonon_file'];dest=destination/'phonons'/f'{k}.npz';dest.parent.mkdir(exist_ok=True)
    if not dest.exists() or dest.stat().st_mtime<src.stat().st_mtime:shutil.copy2(src,dest)
    row['phonon_file']=str(dest.relative_to(destination))
   pred[k]=row
  progress=load(out/'progress.json') if (out/'progress.json').exists() else {'detail':'initializing'}
  workers.append(dict(gpu=w['gpu'],pid=w['pid'],running=running,progress=progress,errors=load(out/'errors.json') if (out/'errors.json').exists() else {}))
  for stage in counts:counts[stage]+=len(list((out/'completed').glob(f'*/{stage}.json')))
 phase=launch.get('phase')
 ground_only=phase in ('ground_state','ground_state_blocked')
 save(destination/'predictions.json',pred)
 scores=evaluate(targets,pred,destination,ground_only=ground_only)
 scores['provisional']=phase!='complete' if phase else any(w['running'] for w in workers)
 scores['model']='Prophet-Spin v1'
 scores['moment_head']=True
 scores['exchange_method']=launch['exchange_method']
 if phase:
  scores['phase']=phase
 save(destination/'scores.json',scores)
 ground_failures=sum(sum(k.endswith('/ground_state') for k in w['errors']) for w in workers)
 status=dict(updated_unix=time.time(),running_workers=sum(w['running'] for w in workers),
             completed_stages=counts,provisional=scores['provisional'],workers=workers)
 if phase:status.update(phase=phase,ground_state_failed=ground_failures)
 save(root/'status.json',status)
 return status

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--targets',type=Path,required=True);p.add_argument('--watch',action='store_true');a=p.parse_args()
 while True:
  status=collect(a.run,a.targets);print(json.dumps({k:v for k,v in status.items() if k!='workers'}),flush=True)
  if not a.watch or not status['running_workers']:return
  time.sleep(60)
if __name__=='__main__':main()
