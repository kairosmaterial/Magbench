"""Encryption compatibility, publication modes and the browser sign-in flow."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from leaderboard.cards import ROOT
from leaderboard.site import build,public_fields
from scripts.protect_site import protect,write_site,ITERATIONS,SALT
from scripts.browser_session import find_browser
from scripts.check_gate import check_gate


def decrypt(page,key):
    data=re.search(r'id="payload" type="application/octet-stream">([^<]+)</script>',page).group(1)
    iv=re.search(r'iv=bytes\("([^"]+)"\)',page).group(1)
    return AESGCM(key).decrypt(base64.b64decode(iv),base64.b64decode(data),None)


def test_protected_round_trip_and_legacy_key_format(tmp_path):
    plain=tmp_path/'plain';output=tmp_path/'protected';build(output=plain)
    # Match the existing gate so an already saved browser key remains usable.
    assert ITERATIONS==600000 and SALT==hashlib.sha256(b'magbench-site-access').digest()[:16]
    password=secrets.token_urlsafe(24)
    key=hashlib.pbkdf2_hmac('sha256',password.encode(),SALT,ITERATIONS,32)
    counts=protect(plain,output,password);nonces=set()
    assert counts['encrypted']==len(list(plain.rglob('*.html')))
    for original in plain.rglob('*.html'):
        page=(output/original.relative_to(plain)).read_text()
        assert decrypt(page,key)==original.read_bytes()
        assert 'store="magbench-site-key"' in page and 'iterations:600000' in page
        assert password not in page and 'MODEL CARD' not in page and 'Prophet-Spin' not in page
        nonce=re.search(r'iv=bytes\("([^"]+)"\)',page).group(1)
        assert nonce not in nonces;nonces.add(nonce)
        with pytest.raises(InvalidTag):decrypt(page,b'0'*32)
    assert not list(output.rglob('*.json'))
    assert (output/'.nojekyll').exists()
    assert (output/'assets/app.js').read_bytes()==(plain/'assets/app.js').read_bytes()


def test_publication_modes_remove_stale_plaintext_and_respect_paths(tmp_path):
    plain=tmp_path/'plain';plain.mkdir();(plain/'index.html').write_text('<p>Private example.</p>');(plain/'data.json').write_text('{"value":1}')
    out=tmp_path/'out';write_site(plain,out);assert (out/'data.json').is_file()
    protect(plain,out,secrets.token_urlsafe(24));assert not (out/'data.json').exists()
    for target in (plain,plain/'inside'):
        with pytest.raises(ValueError):protect(plain,target,'example')
    (out/'.git').mkdir()
    with pytest.raises(ValueError):protect(plain,out,'example')
    assert (plain/'index.html').read_text()=='<p>Private example.</p>'
    with pytest.raises(ValueError):protect(plain,tmp_path/'empty','')


def test_publication_command_uses_environment_only(tmp_path):
    plain=tmp_path/'plain';plain.mkdir();(plain/'index.html').write_text('<p>Private example.</p>');(plain/'data.json').write_text('{}')
    password=secrets.token_urlsafe(24);env=dict(os.environ,MAGBENCH_SITE_PASSWORD=password)
    cmd=[sys.executable,str(ROOT/'scripts/prepare_pages.py'),str(plain),str(tmp_path/'out')]
    result=subprocess.run(cmd,env=env,capture_output=True,text=True,check=True)
    assert password not in result.stdout+result.stderr and not (tmp_path/'out/data.json').exists()
    env.pop('MAGBENCH_SITE_PASSWORD');subprocess.run(cmd,env=env,capture_output=True,check=True)
    assert (tmp_path/'out/data.json').exists()


def test_public_build_has_no_undeclared_placeholders(tmp_path):
    data=build(output=tmp_path)
    for path in tmp_path.rglob('*'):
        if path.is_file() and path.suffix in ('.html','.json','.js','.css'):
            assert 'to be provided' not in path.read_text().casefold(),path
    pending=(tmp_path/'models/prophet-spin-v2.html').read_text()
    assert '<p>Kairos Materials</p>' in pending
    assert '<dt>Code licence</dt><dd>pending</dd>' in pending
    assert '<dt>Weights licence</dt><dd>pending</dd>' in pending
    assert 'corresponding</p>' not in pending
    preview=public_fields({'name':'to be provided','valid':1,'nested':{'url':None}})
    assert preview=={'valid':1}
    assert all('to be provided' not in json.dumps(entry['card']) for entry in data['models'])


def test_build_rejects_placeholder_in_an_asset(checkout,tmp_path):
    p=checkout/'site/assets/app.js';p.write_text(p.read_text()+'\n// to be provided\n')
    with pytest.raises(ValueError,match='placeholder'):build(root=checkout,output=tmp_path/'out')


def test_browser_sign_in_navigation_and_mobile_width(tmp_path):
    if not find_browser():
        if os.environ.get('MAGBENCH_REQUIRE_BROWSER'):pytest.fail('Browser executable is required for this check job')
        pytest.skip('Set MAGBENCH_BROWSER to run browser protection checks')
    plain=tmp_path/'plain';protected=tmp_path/'protected';build(output=plain)
    password=secrets.token_urlsafe(24);protect(plain,protected,password)
    result=check_gate(protected,password)
    assert [row['width'] for row in result['widths']]==[1440,390]
    assert all(row['wrong_password_rejected'] and row['direct_datasets_gated'] for row in result['widths'])


def test_publication_scan_rejects_credentials_and_placeholder_text(tmp_path):
    from scripts.check_publication import check_publication
    page=tmp_path/'index.html';page.write_text('<p>Ready</p>')
    assert check_publication(tmp_path)['files']==1
    credential=secrets.token_urlsafe(24);page.write_text(credential)
    with pytest.raises(ValueError,match='content is not logged'):check_publication(tmp_path,credential)
    page.write_text('to be provided')
    with pytest.raises(ValueError):check_publication(tmp_path)
