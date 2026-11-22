#!/usr/bin/env python3
"""Check publication files before they enter a Pages commit or upload."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import zlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
try:
    from .protect_site import PAGE, SALT, ITERATIONS
except ImportError:
    from protect_site import PAGE, SALT, ITERATIONS

TRACE=bytes.fromhex('67656e6572617465647c617373697374616e747c6f70656e61697c616e7468726f7069637c636c617564657c636f6465787c636861746770747c67656d696e697c636f70696c6f747c646565707365656b7c636f5b2d205d617574686f726564')


def publication_content(raw, credential):
    """Authenticate a recognised gate, then scan its wrapper and clear content."""
    if b'id="payload" type="application/octet-stream"' not in raw:
        return raw
    if not credential:
        raise ValueError('Protected publication checks require the site password')
    pattern=re.escape(PAGE)
    for token, expression in (('__PAYLOAD__',r'(?P<payload>[A-Za-z0-9+/]+={0,2})'),
                              ('__IV__',r'(?P<iv>[A-Za-z0-9+/]+={0,2})')):
        pattern=pattern.replace(re.escape(token),expression)
    pattern=pattern.replace('__SALT__',re.escape(base64.b64encode(SALT).decode()))
    pattern=pattern.replace('__ITERATIONS__',str(ITERATIONS))
    try:
        match=re.fullmatch(pattern,raw.decode('utf-8'))
        if not match:raise ValueError('Unexpected protected page format')
        iv=base64.b64decode(match['iv'],validate=True)
        payload=base64.b64decode(match['payload'],validate=True)
        if len(iv)!=12 or len(payload)<16:raise ValueError('Invalid protected page framing')
        key=hashlib.pbkdf2_hmac('sha256',credential.encode(),SALT,ITERATIONS,32)
        clear=AESGCM(key).decrypt(iv,payload,None)
    except Exception:
        raise ValueError('Protected page verification failed; content is not logged') from None
    # Opaque ciphertext is authenticated, not interpreted as publication text.
    return PAGE.encode()+b'\n'+clear


def check_publication(root,credential=None):
    counts={'files':0,'binary_assets':0,'trace_matches':0,'cjk_matches':0,'private_paths':0,'placeholders':0,'credential_matches':0}
    for path in sorted(Path(root).rglob('*')):
        if not path.is_file():continue
        raw=path.read_bytes();counts['files']+=1
        if credential:counts['credential_matches']+=raw.count(credential.encode())
        content=publication_content(raw,credential)
        counts['trace_matches']+=len(re.findall(TRACE,content,re.I))
        if credential and content!=raw:counts['credential_matches']+=content.count(credential.encode())
        try:text=content.decode('utf-8')
        except UnicodeDecodeError:
            counts['binary_assets']+=1
            if raw[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Unexpected binary publication asset')
            offset=8;chunks=[]
            while offset<len(raw):
                size=struct.unpack('>I',raw[offset:offset+4])[0];kind=raw[offset+4:offset+8];data=raw[offset+8:offset+8+size]
                crc=struct.unpack('>I',raw[offset+8+size:offset+12+size])[0]
                if kind not in {b'IHDR',b'PLTE',b'IDAT',b'IEND',b'tRNS'} or zlib.crc32(kind+data)&0xffffffff!=crc:
                    raise ValueError('Binary publication assets must contain pixel data only')
                chunks.append(kind);offset+=size+12
            if offset!=len(raw) or chunks[0]!=b'IHDR' or chunks[-1]!=b'IEND':raise ValueError('Invalid publication image')
            continue
        counts['cjk_matches']+=len(re.findall('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]',text))
        counts['private_paths']+=len(re.findall(r'/(?:root|home|gpfs|tos-vasp|veFPS-model_dev)/',text))
        counts['placeholders']+=text.casefold().count('to be provided')
    if any(counts[key] for key in counts if key not in ('files','binary_assets')):
        raise ValueError('Publication scan failed; matched content is not logged')
    return counts


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);args=parser.parse_args()
    print(json.dumps(check_publication(args.root,os.environ.get('MAGBENCH_SITE_PASSWORD')),sort_keys=True))


if __name__=='__main__':main()
