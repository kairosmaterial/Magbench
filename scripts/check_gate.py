#!/usr/bin/env python3
"""Check protected static pages with a local browser, without recording credentials."""
import argparse
import base64
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import tempfile
from threading import Thread
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from browser_session import Browser


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def check_gate(site, password, output=None):
    if not password:raise ValueError('A site password is required in the command environment')
    if output:Path(output).mkdir(parents=True,exist_ok=True)
    result={'widths':[]}
    with tempfile.TemporaryDirectory(prefix='magbench-gate-links-') as temporary:
        (Path(temporary)/'Magbench').symlink_to(Path(site).resolve(),target_is_directory=True)
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temporary))
        worker=Thread(target=server.serve_forever,daemon=True);worker.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with Browser() as browser:
                def wait(expression):
                    for _ in range(200):
                        if browser.js(expression):return
                        time.sleep(.05)
                    raise RuntimeError('Browser check timed out')
                def navigate(name):
                    browser.call('Page.navigate',{'url':base+'/Magbench/'+name})
                    wait('location.pathname==='+json.dumps('/Magbench/'+name)+'&&document.readyState==="complete"')
                def clear():
                    browser.call('Storage.clearDataForOrigin',{'origin':base,'storageTypes':'all'})
                def submit(value):
                    # The expression returns only a boolean, never the field value.
                    browser.js('(()=>{document.querySelector("#password").value='+json.dumps(value)+';document.querySelector("#gate").requestSubmit();return true})()')
                def screenshot(name,width):
                    if not output:return
                    height=browser.call('Page.getLayoutMetrics')['cssContentSize']['height']
                    png=browser.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':0,'width':width,'height':height,'scale':1}})
                    (Path(output)/name).write_bytes(base64.b64decode(png['data']))
                def no_overflow():
                    assert browser.js('document.documentElement.scrollWidth<=innerWidth')
                    assert browser.js('!document.body.innerText.includes("to be provided")')
                for width in (1440,390):
                    browser.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000 if width==1440 else 844,'deviceScaleFactor':1,'mobile':False})
                    clear();navigate('index.html');wait('document.querySelector("#gate")?.hidden===false')
                    assert browser.js('!document.querySelector("#leaderboard")');no_overflow();screenshot(f'sign-in-{width}.png',width)
                    wrong='invalid-site-entry'
                    while wrong==password:wrong+='-invalid'
                    submit(wrong);wait('document.querySelector("#message")?.textContent==="Incorrect password"')
                    assert browser.js('!document.querySelector("#leaderboard")')
                    submit(password);wait('document.querySelectorAll("#leaderboard tbody tr").length>0')
                    expected=browser.js('JSON.parse(document.querySelector("#page-data").textContent).models.length')
                    wait('document.querySelectorAll(".plot-mark").length==='+str(expected));time.sleep(.5)
                    no_overflow();screenshot(f'unlocked-leaderboard-{width}.png',width)
                    assert browser.js('!!localStorage.getItem("magbench-site-key")')
                    navigate('protocol.html');wait('!!document.querySelector("article.document")');assert browser.js('!document.querySelector("#gate")');no_overflow();screenshot(f'protocol-{width}.png',width)
                    navigate('datasets.html');wait('!!document.querySelector("#datasets")');assert browser.js('!document.querySelector("#gate")');no_overflow()
                    clear();navigate('models/prophet-spin-v2l.html');wait('document.querySelector("#gate")?.hidden===false');assert browser.js('!document.querySelector("main")');no_overflow()
                    submit(password);wait('!!document.querySelector("#materials")');no_overflow();screenshot(f'pending-model-{width}.png',width)
                    clear();navigate('datasets.html');wait('document.querySelector("#gate")?.hidden===false');assert browser.js('!document.querySelector("#datasets")');no_overflow()
                    result['widths'].append({'width':width,'wrong_password_rejected':True,'right_password_unlocks':True,'rows':expected,'scatter_marks':expected,'second_page_without_prompt':True,'direct_model_gated':True,'direct_datasets_gated':True,'horizontal_overflow':False})
                assert not any(event.get('method')=='Runtime.exceptionThrown' for event in browser.events)
                external=[event for event in browser.events if event.get('method')=='Network.requestWillBeSent' and not event['params']['request']['url'].startswith((base,'about:','data:'))]
                assert not external
                result.update(script_exceptions=0,external_runtime_requests=0)
        finally:server.shutdown();server.server_close();worker.join()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        result=check_gate(args.site,os.environ.get('MAGBENCH_SITE_PASSWORD'),args.output)
    except Exception:
        raise SystemExit('Protected browser checks failed; credentials and protocol traffic were not logged.') from None
    text=json.dumps(result,indent=2)+'\n'
    if args.output:(args.output/'gate_checks.json').write_text(text)
    print(text,end='')


if __name__=='__main__':main()
