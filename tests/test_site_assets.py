"""Static hosting paths and pixel-only binary assets."""
from functools import partial
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import struct
import subprocess
from threading import Thread
from urllib.parse import urljoin,urlsplit
from urllib.request import urlopen
import zlib
from leaderboard.cards import ROOT
from leaderboard.site import build


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attributes):
        self.links.extend(v for k,v in attributes if k in ('src','href') and v)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def test_every_internal_link_works_under_repository_subpath(tmp_path):
    output=tmp_path/'Magbench';build(output=output)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=tmp_path))
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_port}/Magbench/'
    try:
        for page in output.rglob('*.html'):
            url=urljoin(base,str(page.relative_to(output)))
            with urlopen(url) as response:
                assert response.status==200;parser=Links();parser.feed(response.read().decode())
            for link in parser.links:
                if urlsplit(link).scheme:continue
                assert not link.startswith('/')
                target=urljoin(url,link)
                assert urlsplit(target).path.startswith('/Magbench/')
                with urlopen(target) as response:assert response.status==200;response.read()
        for name in ('.nojekyll','data.json'):
            with urlopen(urljoin(base,name)) as response:assert response.status==200;response.read()
    finally:server.shutdown();server.server_close();worker.join()


def test_tracked_binary_assets_contain_pixel_data_only():
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    binary=[]
    for name in names:
        path=ROOT/name
        if not path.is_file():continue
        data=path.read_bytes()
        try:data.decode('utf-8');continue
        except UnicodeDecodeError:pass
        binary.append(name)
        assert path.suffix=='.png' and data[:8]==b'\x89PNG\r\n\x1a\n',name
        offset=8;chunks=[]
        while offset<len(data):
            size=struct.unpack('>I',data[offset:offset+4])[0]
            kind=data[offset+4:offset+8];pixels=data[offset+8:offset+8+size]
            checksum=struct.unpack('>I',data[offset+8+size:offset+12+size])[0]
            assert kind in {b'IHDR',b'PLTE',b'IDAT',b'IEND',b'tRNS'},(name,kind)
            assert zlib.crc32(kind+pixels)&0xffffffff==checksum,name
            chunks.append(kind);offset+=12+size
        assert offset==len(data) and chunks[0]==b'IHDR' and chunks[-1]==b'IEND' and b'IDAT' in chunks,name
    assert binary
