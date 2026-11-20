"""Bounded, verified public artefact and target retrieval."""
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
from urllib.parse import urlsplit, quote
from urllib.request import Request, urlopen
import zipfile
from .cards import inside


def public_url(url):
    parts=urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValueError('A public HTTPS URL without credentials is required')
    return url


def request(url, *, headers=None):
    response=urlopen(Request(public_url(url),headers={'User-Agent':'MagBench-validation',**(headers or {})}),timeout=30)
    public_url(response.url)
    if response.status not in (200,206):
        response.close()
        raise ValueError('Public endpoint did not answer successfully')
    return response


def probe(url, *, checkpoint=False):
    with request(url,headers={'Range':'bytes=0-0'} if checkpoint else {}) as response:
        if checkpoint:
            total=response.headers.get('Content-Range','').split('/')[-1]
            if not total.isdigit(): total=response.headers.get('Content-Length','0')
            if not total.isdigit() or int(total)<1:
                raise ValueError('Checkpoint endpoint must report a non-zero size')
            if not response.read(1): raise ValueError('Checkpoint endpoint is empty')
            return int(total)
        return response.status


def verify(path, sha256, size):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        raise ValueError('Artefact size differs from the declared persisted size')
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    if digest.hexdigest()!=sha256: raise ValueError('Artefact SHA-256 differs')
    return path


def download(ref, destination, limit):
    if not isinstance(ref['size'],int) or not 0<ref['size']<=limit:
        raise ValueError('Declared artefact size exceeds the download limit')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():return verify(destination,ref['sha256'],ref['size'])
    fd, temporary=tempfile.mkstemp(prefix='.download-',dir=destination.parent)
    try:
        count=0
        with os.fdopen(fd,'wb') as output, request(ref['url']) as response:
            header=response.headers.get('Content-Length')
            if header and int(header)>min(limit,ref['size']): raise ValueError('Response exceeds declared size')
            while True:
                block=response.read(min(1024*1024,limit-count+1))
                if not block:break
                count+=len(block)
                if count>min(limit,ref['size']):raise ValueError('Download exceeds the size limit')
                output.write(block)
            output.flush();os.fsync(output.fileno())
        verify(temporary,ref['sha256'],ref['size'])
        os.replace(temporary,destination)
        return destination
    finally:
        if Path(temporary).exists():Path(temporary).unlink()


def extract_phonons(archive, destination, limits):
    """Accept NPZ files only; never follow archive paths or symbolic links."""
    archive=Path(archive);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    if zipfile.is_zipfile(archive):
        handle=zipfile.ZipFile(archive)
        members=[(m.filename,m.file_size,m.is_dir(),(m.external_attr>>16)&0o170000,lambda m=m:handle.open(m)) for m in handle.infolist()]
    else:
        handle=tarfile.open(archive,mode='r:*')
        members=[(m.name,m.size,m.isdir(),0 if m.isfile() or m.isdir() else 0o120000,lambda m=m:handle.extractfile(m)) for m in handle.getmembers()]
    total=0;seen=set()
    try:
        if len(members)>limits['archive_members']:raise ValueError('Too many archive members')
        for name,size,is_dir,kind,opener in members:
            target=inside(destination,name)
            canonical=str(target.relative_to(destination.resolve()))
            if canonical in seen or kind in (0o120000,0o020000,0o060000):raise ValueError('Duplicate or non-regular archive member')
            seen.add(canonical)
            if is_dir:continue
            if target.suffix!='.npz' or size>64*1024*1024:raise ValueError('Archive must contain bounded NPZ files only')
            total+=size
            if total>limits['extracted_bytes']:raise ValueError('Expanded archive exceeds the size limit')
            target.parent.mkdir(parents=True,exist_ok=True)
            written=0
            with opener() as source, target.open('wb') as output:
                while True:
                    block=source.read(min(1024*1024,size-written+1))
                    if not block:break
                    written+=len(block)
                    if written>size:raise ValueError('Archive member exceeds declared size')
                    output.write(block)
            if written!=size:raise ValueError('Truncated archive member')
    finally:handle.close()


def targets(settings, *, data=None, cache=None, offline=False):
    dataset=settings['dataset']
    if not re.fullmatch('[0-9a-f]{40}',dataset['revision']) and not (data and dataset['revision']=='TODO(owner)'):
        raise ValueError('Dataset revision must be an immutable commit SHA; the release pin awaits owner confirmation')
    if not data and not cache:raise ValueError('Supply --data or --cache for pinned targets')
    root=Path(data) if data else Path(cache)/'dataset'/dataset['revision']
    for entry in dataset['targets']:
        path=inside(root,entry['path'])
        if not path.exists():
            if offline or data:raise ValueError('Pinned target file is missing: '+entry['path'])
            url=f"https://huggingface.co/datasets/{dataset['repo_id']}/resolve/{dataset['revision']}/{quote(entry['path'])}"
            download({**entry,'url':url},path,entry['size'])
        verify(path,entry['sha256'],entry['size'])
    return root/'targets'


def verify_local_phonons(card, prediction, limits):
    refs=card['predictions']['phonons']
    if 'files' not in refs:return
    folder=Path(prediction).resolve().parent
    members=refs['files']
    if len(members)>limits['archive_members'] or sum(r['size'] for r in members)>limits['extracted_bytes']:
        raise ValueError('Phonon manifest exceeds the size limit')
    seen=set()
    for ref in members:
        path=inside(folder,ref['path'])
        if path in seen or path.suffix!='.npz' or not ref['path'].startswith('phonons/'):
            raise ValueError('Invalid or duplicate phonon manifest member')
        seen.add(path)
        verify(path,ref['sha256'],ref['size'])
    records=json.loads(Path(prediction).read_text())
    for row in records.values():
        if 'phonon_file' in row and inside(folder,row['phonon_file']) not in seen:
            raise ValueError('Prediction references an unlisted phonon file')


def prediction_files(card, settings, cache):
    limits=settings['limits'];refs=card['predictions'];folder=Path(cache)/'predictions'/refs['sha256']
    prediction=download(refs,folder/'predictions.json',limits['predictions_bytes'])
    phonons=refs['phonons']
    if 'files' in phonons:
        if len(phonons['files'])>limits['archive_members'] or sum(r['size'] for r in phonons['files'])>limits['extracted_bytes']:
            raise ValueError('Phonon manifest exceeds the size limit')
        for ref in phonons['files']:
            relative=ref['path']
            target=inside(folder,relative)
            if not relative.startswith('phonons/') or target.suffix!='.npz':raise ValueError('Invalid phonon path')
            url=phonons['url'].rstrip('/')+'/'+quote(relative.removeprefix('phonons/'))
            download({**ref,'url':url},target,64*1024*1024)
        verify_local_phonons(card,prediction,limits)
    else:
        archive=download(phonons,Path(cache)/'archives'/phonons['sha256'],limits['phonon_archive_bytes'])
        extract_phonons(archive,folder,limits)
    return prediction
