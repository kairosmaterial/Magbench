"""Small local browser session for static-site checks; protocol traffic is not logged."""
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
import urllib.parse


def find_browser():
    configured=os.environ.get('MAGBENCH_BROWSER')
    if configured:return configured if Path(configured).is_file() else None
    for name in ('chromium','chromium-browser','google-chrome','chrome'):
        if found:=shutil.which(name):return found
    cache=Path.home()/'.cache/ms-playwright'
    for pattern in ('chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell','chromium-*/chrome-linux*/chrome'):
        for path in sorted(cache.glob(pattern),reverse=True):
            if path.is_file():return str(path)
    return None


class CDP:
 def __init__(self,url):
  u=urllib.parse.urlparse(url);self.s=socket.create_connection((u.hostname,u.port),timeout=15);key=base64.b64encode(os.urandom(16)).decode();self.s.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode());h=b''
  while not h.endswith(b'\r\n\r\n'):h+=self.s.recv(1)
  assert b'101' in h;self.count=0;self.events=[]
 def exact(self,n):
  b=b''
  while len(b)<n:
   chunk=self.s.recv(n-len(b))
   if not chunk:raise EOFError()
   b+=chunk
  return b
 def send(self,obj):
  p=json.dumps(obj).encode();mask=os.urandom(4);length=len(p);head=bytes([0x81,0x80|length]) if length<126 else bytes([0x81,0xfe])+struct.pack('!H',length) if length<65536 else bytes([0x81,0xff])+struct.pack('!Q',length);self.s.sendall(head+mask+bytes(x^mask[i%4] for i,x in enumerate(p)))
 def recv(self):
  h=self.exact(2);n=h[1]&127
  if n==126:n=struct.unpack('!H',self.exact(2))[0]
  elif n==127:n=struct.unpack('!Q',self.exact(8))[0]
  mask=self.exact(4) if h[1]&128 else None;p=self.exact(n)
  if mask:p=bytes(x^mask[i%4] for i,x in enumerate(p))
  if h[0]&15==8:raise EOFError()
  if h[0]&15==9:return self.recv()
  return json.loads(p)
 def call(self,method,params=None):
  self.count+=1;request=self.count;self.send(dict(id=request,method=method,params=params or {}))
  while True:
   reply=self.recv()
   if reply.get('id')==request:
    if 'error' in reply:raise RuntimeError('Browser protocol command failed')
    return reply.get('result',{})
   self.events.append(reply)
 def js(self,expression):
  result=self.call('Runtime.evaluate',dict(expression=expression,returnByValue=True))
  if 'exceptionDetails' in result:raise RuntimeError('Browser expression failed')
  return result['result'].get('value')

class Browser:
    def __enter__(self):
        binary=find_browser()
        if not binary:raise RuntimeError('Set MAGBENCH_BROWSER to a local Chromium executable')
        self.profile=tempfile.TemporaryDirectory(prefix='magbench-browser-',dir=os.environ.get('MAGBENCH_BROWSER_TMP'),ignore_cleanup_errors=True)
        self.process=None;self.client=None
        try:
            self.process=subprocess.Popen([binary,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--incognito','--no-first-run','--disable-background-networking','--disable-sync','--disable-extensions','--disable-component-update','--remote-allow-origins=*','--remote-debugging-port=0',f'--user-data-dir={self.profile.name}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            active=Path(self.profile.name)/'DevToolsActivePort'
            for _ in range(300):
                if active.exists():break
                if self.process.poll() is not None:raise RuntimeError('Browser did not start')
                time.sleep(.1)
            port=int(active.read_text().splitlines()[0])
            targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=10))
            self.client=CDP(next(item['webSocketDebuggerUrl'] for item in targets if item['type']=='page'))
            for domain in ('Page','Runtime','Network'):self.client.call(domain+'.enable')
            return self.client
        except Exception:
            self.__exit__(None,None,None)
            raise RuntimeError('Browser startup failed') from None
    def __exit__(self,*args):
        if self.client:self.client.s.close()
        if self.process:
            self.process.terminate()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.profile.cleanup()
