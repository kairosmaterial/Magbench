#!/usr/bin/env python3
"""Put a built site behind a shared password.

Every HTML page is replaced by a small sign-in page that carries the original
page encrypted with AES-256-GCM. The key is derived from the password with
PBKDF2-HMAC-SHA256 and never leaves the browser. Style sheets, scripts and
images are copied unchanged; JSON files are left out of the protected build.

Usage: MAGBENCH_SITE_PASSWORD=... python protect_site.py BUILT_SITE OUTPUT
"""
import argparse
import base64
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 600_000
SALT = hashlib.sha256(b"magbench-site-access").digest()[:16]

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>MagBench</title><style>
html,body{height:100%;margin:0}body{background:#f5f4f0;color:#27212d;font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;display:flex;align-items:center;justify-content:center}
form{width:min(320px,calc(100vw - 32px))}h1{font-size:28px;font-weight:500;margin:0 0 24px}label{display:block;font-size:13px;color:#78737b;margin-bottom:6px}
input{box-sizing:border-box;width:100%;padding:10px 12px;border:1px solid #d8d3d9;background:#fbfaf8;color:inherit;font:inherit}input:focus{outline:2px solid #5c3b7e;outline-offset:1px}
button{margin-top:12px;width:100%;padding:10px 12px;border:0;background:#27212d;color:#f5f4f0;font:inherit;cursor:pointer}button:focus-visible{outline:2px solid #5c3b7e;outline-offset:2px}
p{min-height:1.5em;margin:10px 0 0;font-size:13px;color:#8a2b2b}
</style></head><body><form id="gate" hidden><h1>MagBench</h1><label for="password">Password</label><input id="password" type="password" autocomplete="current-password" required><button type="submit">Enter</button><p id="message" role="alert"></p></form>
<script id="payload" type="application/octet-stream">__PAYLOAD__</script>
<script>
(async()=>{
const bytes=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
const salt=bytes("__SALT__"),iv=bytes("__IV__"),store="magbench-site-key";
const form=document.getElementById("gate"),field=document.getElementById("password"),message=document.getElementById("message");
const decrypt=async raw=>{const key=await crypto.subtle.importKey("raw",raw,"AES-GCM",false,["decrypt"]);
  return new TextDecoder().decode(await crypto.subtle.decrypt({name:"AES-GCM",iv},key,bytes(document.getElementById("payload").textContent)))};
const derive=async text=>{const material=await crypto.subtle.importKey("raw",new TextEncoder().encode(text),"PBKDF2",false,["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits({name:"PBKDF2",hash:"SHA-256",salt,iterations:__ITERATIONS__},material,256))};
const loaded=()=>document.readyState==="complete"?Promise.resolve():new Promise(done=>addEventListener("load",done,{once:true}));
const show=async html=>{await loaded();document.open();document.write(html);document.close()};
let saved=null;try{saved=localStorage.getItem(store)}catch(error){}
if(saved){try{const html=await decrypt(bytes(saved));await show(html);return}catch(error){try{localStorage.removeItem(store)}catch(inner){}}}
form.hidden=false;field.focus();
form.addEventListener("submit",async event=>{event.preventDefault();message.textContent="";
  try{const raw=await derive(field.value),html=await decrypt(raw);
    try{localStorage.setItem(store,btoa(String.fromCharCode(...raw)))}catch(error){}
    await show(html)}
  catch(error){message.textContent="Incorrect password";field.select()}});
})();
</script></body></html>
"""



def write_site(source, output, password=None):
    """Replace a publication tree only after every page has been prepared."""
    source, output = Path(source).resolve(), Path(output).absolute()
    if not source.is_dir() or output.is_symlink():
        raise ValueError('Source must be a directory and output must not be a symlink')
    resolved = output.resolve()
    if source == resolved or source in resolved.parents or resolved in source.parents:
        raise ValueError('Source and output must be separate directory trees')
    if (output/'.git').exists():
        raise ValueError('Prepare a separate tree before copying into a worktree')
    if password is not None and not password:
        raise ValueError('A nonempty site password is required')
    cipher = AESGCM(hashlib.pbkdf2_hmac('sha256', password.encode(), SALT, ITERATIONS, 32)) if password is not None else None
    counts = {'encrypted':0, 'copied':0, 'left_out':0}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.magbench-publication-',dir=output.parent) as temporary:
        staged = Path(temporary)/'tree';staged.mkdir()
        for path in sorted(source.rglob('*')):
            if path.is_symlink():
                raise ValueError('Publication sources must not contain symlinks')
            if not path.is_file():continue
            relative=path.relative_to(source)
            if relative.parts[0]=='.git':continue
            if cipher is not None and path.suffix.lower()=='.json':
                counts['left_out']+=1;continue
            target=staged/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if cipher is not None and path.suffix.lower()=='.html':
                iv=os.urandom(12)
                payload=cipher.encrypt(iv,path.read_bytes(),None)
                page=(PAGE.replace('__PAYLOAD__',base64.b64encode(payload).decode())
                      .replace('__SALT__',base64.b64encode(SALT).decode())
                      .replace('__IV__',base64.b64encode(iv).decode())
                      .replace('__ITERATIONS__',str(ITERATIONS)))
                target.write_text(page,encoding='utf-8');counts['encrypted']+=1
            else:
                shutil.copyfile(path,target);counts['copied']+=1
        if output.exists():shutil.rmtree(output)
        os.replace(staged,output)
    return counts


def protect(source, output, password):
    if not password:raise ValueError('A nonempty site password is required')
    return write_site(source,output,password)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    password=os.environ.get('MAGBENCH_SITE_PASSWORD')
    if not password:parser.error('Set MAGBENCH_SITE_PASSWORD in the command environment')
    print(protect(args.source,args.output,password))


if __name__=='__main__':main()
