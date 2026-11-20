#!/usr/bin/env python3
"""Check publication files before they enter a Pages commit or upload."""
import argparse
import json
import os
from pathlib import Path
import re
import struct
import zlib

TRACE=bytes.fromhex('67656e6572617465647c617373697374616e747c6f70656e61697c616e7468726f7069637c636c617564657c636f6465787c636861746770747c67656d696e697c636f70696c6f747c646565707365656b7c636f5b2d205d617574686f726564')


def check_publication(root,credential=None):
    counts={'files':0,'binary_assets':0,'trace_matches':0,'cjk_matches':0,'private_paths':0,'placeholders':0,'credential_matches':0}
    for path in sorted(Path(root).rglob('*')):
        if not path.is_file():continue
        raw=path.read_bytes();counts['files']+=1
        counts['trace_matches']+=len(re.findall(TRACE,raw,re.I))
        if credential:counts['credential_matches']+=raw.count(credential.encode())
        try:text=raw.decode('utf-8')
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
