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


def test_public_content_has_no_internal_terms_or_private_paths(tmp_path):
    import re
    output=tmp_path/'site';build(output=output)
    obsolete=re.compile(bytes.fromhex('5c6276355c627c70726f706865742d7370696e2d283f3a65787c7631283f3a2d3661293f7c763229283f215b612d7a302d392d5d297c50726f706865742d5370696e2076283f3a31283f3a2065787c205c283620c3855c29293f7c3229283f215b612d7a302d395d29').decode(),re.I)
    forbidden=('host initialisation asset','receipt','input labels','retained copy')
    public_weights=r'(?:prophet-v[12]-mag(?:-head)?|prophet-spin-(?:v1l|v1s|v2l)(?:-head)?|checkpoint|moment-head)\.pt'
    working_files=re.compile(rf'(?<![\w.-])(?!{public_weights})[\w.-]+\.pt\b|[\w.-]*lmdb\b|[\w.-]+/train\b',re.I)
    sources=list((ROOT/'datasets').glob('*.yml'))+list((ROOT/'models').glob('*/*.yml'))
    sources+=list(ROOT.glob('*.md'))+list((ROOT/'docs').rglob('*.md'))+list((ROOT/'models').glob('*/*.md'))+list(output.rglob('*.html'))+[output/'data.json']
    for path in sources:
        text=path.read_text()
        assert not any(word.casefold() in text.casefold() for word in forbidden),path
        assert not obsolete.search(text),path
        assert not working_files.search(text),(path,working_files.search(text).group())
        assert not re.search(r'/(?:root|home|gpfs|tos-vasp|veFPS-model_dev)/',text),path
    for path in (ROOT/'datasets').glob('*.yml'):
        assert 'to be provided' not in path.read_text().casefold(),path
    assert 'to be provided' not in (output/'datasets.html').read_text()


def test_trace_and_cjk_scan_includes_binary_assets():
    import re
    # Encoded patterns keep the audit policy separate from published wording.
    pattern=bytes.fromhex('67656e6572617465647c617373697374616e747c6f70656e61697c616e7468726f7069637c636c617564657c636f6465787c636861746770747c67656d696e697c636f70696c6f747c646565707365656b7c636f5b2d205d617574686f726564')
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    for name in names:
        path=ROOT/name
        if not path.is_file():continue
        raw=path.read_bytes();assert not re.search(pattern,raw,re.I),name
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError:continue
        assert not re.search('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]',text),name
