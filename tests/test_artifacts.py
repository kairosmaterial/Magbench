import hashlib
import io
import json
import zipfile
import pytest
from leaderboard import artifacts
from leaderboard.cards import config


class Response(io.BytesIO):
    status=200
    url='https://example.org/file'
    def __init__(self,body,headers=None):super().__init__(body);self.headers=headers or {'Content-Length':str(len(body))}


def test_checkpoint_probe_reads_only_one_byte(monkeypatch):
    stream=Response(b'weights',{'Content-Range':'bytes 0-0/9000000','Content-Length':'1'});seen=[]
    def request(url,headers=None):seen.append(headers);return stream
    monkeypatch.setattr(artifacts,'request',request)
    assert artifacts.probe('https://example.org/weights',checkpoint=True)==9000000
    assert seen==[{'Range':'bytes=0-0'}]


def test_download_persisted_hash_and_size(monkeypatch,tmp_path):
    content=b'prediction bytes';ref={'url':'https://example.org/file','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}
    monkeypatch.setattr(artifacts,'request',lambda *a,**kw:Response(content))
    p=artifacts.download(ref,tmp_path/'prediction',100)
    assert p.read_bytes()==content
    p.write_bytes(content[:-1])
    with pytest.raises(ValueError,match='size'):artifacts.download(ref,p,100)


@pytest.mark.parametrize('body,sha,size',[(b'bad','a'*64,3),(b'large','a'*64,2),(b'x','a'*64,3)])
def test_bad_download_never_promoted(monkeypatch,tmp_path,body,sha,size):
    monkeypatch.setattr(artifacts,'request',lambda *a,**kw:Response(body))
    with pytest.raises(ValueError):artifacts.download({'url':'https://example.org/file','sha256':sha,'size':size},tmp_path/'final',10)
    assert not (tmp_path/'final').exists()
    assert not list(tmp_path.glob('.download-*'))


@pytest.mark.parametrize('name',['../escape.npz','/absolute.npz','phonons/../../escape.npz','phonons/not-a-prediction.py'])
def test_unsafe_archive_rejected(tmp_path,name):
    p=tmp_path/'archive.zip'
    with zipfile.ZipFile(p,'w') as f:f.writestr(name,b'test')
    with pytest.raises(ValueError):artifacts.extract_phonons(p,tmp_path/'out',config()['limits'])


def test_archive_member_and_expansion_limits(tmp_path):
    p=tmp_path/'archive.zip'
    with zipfile.ZipFile(p,'w') as f:f.writestr('phonons/001.npz',b'12345')
    limits={**config()['limits'],'extracted_bytes':4}
    with pytest.raises(ValueError,match='Expanded'):artifacts.extract_phonons(p,tmp_path/'out',limits)
    limits={**config()['limits'],'archive_members':0}
    with pytest.raises(ValueError,match='Too many'):artifacts.extract_phonons(p,tmp_path/'out',limits)


@pytest.mark.parametrize('url',['http://example.org/a','file:///data','https://name:password@example.org/a'])
def test_public_urls_without_credentials(url):
    with pytest.raises(ValueError):artifacts.public_url(url)


def test_target_hashes_verify_local_bytes(tmp_path):
    path=tmp_path/'targets/scoring.json';path.parent.mkdir();path.write_bytes(b'{}')
    settings={'dataset':{'revision':'a'*40,'targets':[{'path':'targets/scoring.json','size':2,'sha256':hashlib.sha256(b'{}').hexdigest()}]}}
    assert artifacts.targets(settings,data=tmp_path,offline=True)==tmp_path/'targets'
    path.write_bytes(b'[]')
    with pytest.raises(ValueError,match='SHA-256'):artifacts.targets(settings,data=tmp_path,offline=True)


def test_archive_symlinks_and_duplicate_normalised_paths_rejected(tmp_path):
    for variant in ('symlink','duplicate'):
        archive=tmp_path/f'{variant}.zip'
        with zipfile.ZipFile(archive,'w') as handle:
            if variant=='symlink':
                member=zipfile.ZipInfo('phonons/001.npz');member.create_system=3;member.external_attr=0o120777<<16
                handle.writestr(member,'outside')
            else:
                handle.writestr('phonons/001.npz',b'a');handle.writestr('phonons/./001.npz',b'b')
        with pytest.raises(ValueError,match='Duplicate or non-regular'):
            artifacts.extract_phonons(archive,tmp_path/variant,config()['limits'])
