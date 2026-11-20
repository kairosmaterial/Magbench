"""Trusted queue service; inference runs in a separate network-disabled container.

Service credentials belong only in the supervisor environment, never the container.
Run: python -m magbench.worker --config worker.json
"""
import argparse,json,os,subprocess,time,uuid,urllib.request,urllib.parse,threading
from pathlib import Path
from .cli import load,save
from .scoring import evaluate
from .selection import selection_receipt

class Client:
 def __init__(self,url):self.url=url.rstrip('/')+'/api/worker'
 def headers(self):
  h={'Authorization':'Bearer '+os.environ['MAGBENCH_EVALUATOR_TOKEN']}
  if os.environ.get('MAGBENCH_SITE_ACCESS_TOKEN'):h['OAI-Sites-Authorization']='Bearer '+os.environ['MAGBENCH_SITE_ACCESS_TOKEN']
  return h
 def post(self,data):
  h=self.headers();h['Content-Type']='application/json'
  with urllib.request.urlopen(urllib.request.Request(self.url,data=json.dumps(data).encode(),headers=h),timeout=60) as r:return json.load(r)
 def download(self,job,path):
  url=self.url+'?'+urllib.parse.urlencode({'id':job['id'],'lease':job['lease']});n=0
  with urllib.request.urlopen(urllib.request.Request(url,headers=self.headers()),timeout=120) as r,open(path,'wb') as out:
   while data:=r.read(8*1024**2):
    n+=len(data)
    if n>job['bytes']:raise ValueError('Checkpoint exceeds declared size')
    out.write(data)
  if n!=job['bytes']:raise ValueError('Incomplete checkpoint download')

def execute(client,job,cfg):
 # Validate server-generated ID before using it as a path or container name.
 uuid.UUID(job['id']);root=Path(cfg['workdir'])/job['id'];root.mkdir(parents=True,exist_ok=True);checkpoint=root/'checkpoint.pt';output=root/'predictions';output.mkdir(exist_ok=True);output.chmod(0o777)
 stop=threading.Event();lease_lost=threading.Event();process=None
 def heartbeat():
  while not stop.wait(60):
   try:client.post(dict(action='heartbeat',id=job['id'],lease=job['lease'],progress='Calculating five benchmark dimensions'))
   except Exception:lease_lost.set();return
 thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
 try:
  client.download(job,checkpoint)
  args=['docker','run','--rm','--name','magbench-'+job['id'],'--network=none','--read-only','--user=65534:65534','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=512','--memory='+cfg.get('memory','48g'),'--cpus='+str(cfg.get('cpus',8)),'--gpus','device='+str(cfg.get('gpu',0)),'--tmpfs','/tmp:rw,exec,size=8g,mode=1777','--shm-size=1g','-e','HOME=/tmp','-e','TORCH_EXTENSIONS_DIR=/tmp/torch_extensions','-e','XDG_CACHE_HOME=/tmp/.cache']
  for host,container in [(cfg['inputs'],'/inputs'),(str(checkpoint),'/model/checkpoint.pt')]:args+=['--mount',f'type=bind,src={Path(host).resolve()},dst={container},readonly']
  args+=['--mount',f'type=bind,src={output.resolve()},dst=/output']
  entry=[cfg['image'],'python','-m','magbench.cli','run','--inputs','/inputs',
         '--checkpoint','/model/checkpoint.pt','--output','/output',
         '--exchange-method',job.get('exchange_method','exchange-head')]
  start=time.monotonic()

  def run_container(command):
   with open(root/'inference.log','ab') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
    while process.poll() is None:
     if lease_lost.is_set() or time.monotonic()-start>cfg.get('timeout_hours',168)*3600:
      raise RuntimeError('Evaluation lease expired or time budget exhausted')
     time.sleep(5)
    if process.returncode:
     raise RuntimeError(f'Inference container exited {process.returncode}')
   for path in output.rglob('*'):
    if path.is_symlink():
     raise ValueError('Symlink in prediction output')

  run_container(args+entry+['--stages','ground_state'])
  ids=load(Path(cfg['inputs'])/'manifest.json')['cohorts']['ground_state']
  barrier=root/'ground_state_barrier.json'
  save(barrier,selection_receipt(cfg['targets'],ids,[output]))
  mount=['--mount',f'type=bind,src={barrier.resolve()},dst=/selection.json,readonly']
  run_container(args+mount+entry+['--stages','J','magnetovolume','phonons',
                               '--ground-state-barrier','/selection.json'])
  pf=output/'predictions.json'
  if pf.stat().st_size>20*1024**2:raise ValueError('Oversized prediction JSON')
  prediction=load(pf);result=evaluate(Path(cfg['targets']),prediction,output)
  result['exchange_method']=job.get('exchange_method','exchange-head');save(root/'scores.json',result)
  client.post(dict(action='complete',id=job['id'],lease=job['lease'],result=result))
 except Exception as e:
  subprocess.run(['docker','rm','-f','magbench-'+job['id']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  if not lease_lost.is_set():client.post(dict(action='fail',id=job['id'],lease=job['lease'],error=str(e)))
 finally:stop.set();thread.join(timeout=2)

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--once',action='store_true');a=p.parse_args();cfg=load(a.config);client=Client(cfg['site'])
 while True:
  job=client.post({'action':'claim'}).get('job')
  if job:execute(client,job,cfg)
  if a.once:return
  time.sleep(30)
if __name__=='__main__':main()
