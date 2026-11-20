import copy
import json
import math
from pathlib import Path
import pytest
import yaml
from leaderboard.cards import ROOT,load_card,read,metrics_from,compare,check_adapter,inside,config
from leaderboard.site import payload,build
from leaderboard.validation import validate,path_guard,route_check

KEYS=('prophet-spin-v1','prophet-spin-ex','prophet-spin-v2')


@pytest.mark.parametrize('key',KEYS)
def test_card_and_review_round_trip(key):
    card,folder=load_card(key);check_adapter(card,folder)
    compare(metrics_from(read(folder/'scores.json')),card['metrics'])
    review=validate(key,offline=True)
    assert not review.passed
    assert any(r['status']=='AWAITING ARTEFACTS' for r in review.rows)
    assert next(r['status'] for r in review.rows if r['check']=='Scorer replay')=='FAIL'
    assert not any(r['status']=='EXEMPT' for r in review.rows)


@pytest.mark.parametrize('path',[(),('evaluation',),('checkpoint',),('license',),('predictions',),('predictions','phonons'),('inference',),('dates',),('metrics',)])
def test_unknown_keys_rejected(checkout,path):
    key='prophet-spin-v1';p=checkout/'models'/key/f'{key}.yml';card=yaml.safe_load(p.read_text());target=card
    for part in path:target=target[part]
    target['unexpected_field']=True;p.write_text(yaml.safe_dump(card))
    with pytest.raises(Exception,match='unexpected_field'):load_card(key,checkout,checkout)


def test_free_form_notes_allowed(checkout):
    p=checkout/'models/prophet-spin-v1/prophet-spin-v1.yml';c=yaml.safe_load(p.read_text());c['notes']['extra']={'content':'Review note'};p.write_text(yaml.safe_dump(c))
    load_card('prophet-spin-v1',checkout,checkout)


@pytest.mark.parametrize('corresponding',[[False],[True,True]])
def test_exactly_one_corresponding_author(checkout,corresponding):
    p=checkout/'models/prophet-spin-v1/prophet-spin-v1.yml';c=yaml.safe_load(p.read_text());c['authors']=[dict(name='Example',affiliation='Example',corresponding=v) for v in corresponding];p.write_text(yaml.safe_dump(c))
    with pytest.raises(Exception):load_card('prophet-spin-v1',checkout,checkout)


def test_public_submission_offline_fails_openness(public_model):
    root,key,card,folder=public_model
    review=validate(key,root=root,policy_root=root,offline=True)
    assert not review.passed
    for name in ('Public inference repository','Public checkpoint (range request)','Prediction artefact download'):
        assert next(r['status'] for r in review.rows if r['check']==name)=='FAIL'
    assert not any(r['status']=='AWAITING ARTEFACTS' for r in review.rows)


def test_new_model_cannot_claim_release_exception(public_model):
    root,key,card,folder=public_model;card['publication_status']='awaiting_artifacts';(folder/f'{key}.yml').write_text(yaml.safe_dump(card))
    with pytest.raises(Exception):load_card(key,root,ROOT)


def test_candidate_cannot_change_trusted_exception(checkout):
    path=checkout/'models/prophet-spin-ex/scores.json';s=read(path);s['total_score']+=.001;path.write_text(json.dumps(s))
    settings=config(checkout);settings['awaiting_publication']['prophet-spin-ex']['score_sha256']='0'*64;(checkout/'benchmark.json').write_text(json.dumps(settings))
    with pytest.raises(ValueError,match='owner-approved'):load_card('prophet-spin-ex',checkout,ROOT)


def test_reference_score_record_is_pinned(checkout):
    c,f=load_card('prophet-spin-v1',checkout,checkout);p=f/'scores.json';p.write_text(p.read_text()+' ')
    with pytest.raises(ValueError,match='owner-approved'):load_card('prophet-spin-v1',checkout,ROOT)


def test_pending_cannot_activate_without_public_release():
    review=validate('prophet-spin-v2',offline=True,require_public=True)
    assert not review.passed
    assert next(r['status'] for r in review.rows if r['check']=='Inference script')=='FAIL'


def test_reference_aggregates_exactly():
    s=read(ROOT/'models/prophet-spin-v1/scores.json')
    card,_=load_card('prophet-spin-v1')
    assert metrics_from(s)['ground_state_passes']==card['metrics']['ground_state_passes']
    expected=[card['metrics'][k] for k in s['dimensions']]
    for (key,dimension),value in zip(s['dimensions'].items(),expected):
        eligible=[r['scores'][key] for r in s['materials'] if r['scores'][key] is not None]
        assert sum(eligible)/len(eligible)*dimension['weight']==dimension['weighted_score']==value
    assert sum(expected)==s['total_score']


def test_site_payload_and_pages(tmp_path):
    data=build(output=tmp_path)
    expected=sorted(KEYS,key=lambda key:(-read(ROOT/f'models/{key}/scores.json')['total_score'],key))
    assert [e['card']['model_key'] for e in data['models']]==expected
    assert read(tmp_path/'data.json')==payload()
    for entry in data['models']:
        key=entry['card']['model_key'];assert entry['scores']==read(ROOT/f'models/{key}/scores.json')
        text=(tmp_path/f'models/{key}.html').read_text()
        assert entry['card']['model_name'] in text
        assert text.count('<tr>')>=len(entry['scores']['materials'])
    assert all((tmp_path/name).is_file() for name in ('index.html','protocol.html','submit.html','assets/style.css','assets/app.js','assets/kairos-mark.png'))
    assert 'weights and inference code to be released' not in (tmp_path/'models/prophet-spin-v2.html').read_text()
    assert 'trained on a subset of the v5 dataset' in (tmp_path/'models/prophet-spin-v1.html').read_text()
    for path in tmp_path.rglob('*.html'):
        assert "TODO" not in path.read_text()
        assert '<footer' not in path.read_text()


def test_path_guard():
    assert path_guard(['models/example/inference.py'],'example')==[]
    assert path_guard(['models/example/inference.py','README.md'],'example')==['README.md']
    with pytest.raises(ValueError,match='Other model'):path_guard(['models/another/scores.json'],'example')


@pytest.mark.parametrize('path',['../escape','/absolute','sub/../../escape','sub\\escape'])
def test_paths_stay_in_model_folder(tmp_path,path):
    with pytest.raises(ValueError):inside(tmp_path,path)


def test_symlink_escape_rejected(tmp_path):
    (tmp_path/'link').symlink_to(tmp_path.parent,target_is_directory=True)
    with pytest.raises(ValueError):inside(tmp_path,'link/outside')


def test_adapter_not_executed(public_model):
    root,key,card,folder=public_model
    (folder/'inference.py').write_text('raise RuntimeError("do not execute")\nclass Model: pass\n')
    assert check_adapter(card,folder).name=='inference.py'
    card['inference']['adapter']='Missing'
    with pytest.raises(ValueError,match='not defined'):check_adapter(card,folder)


def test_metric_tolerance_and_boolean_types():
    compare({'x':.5},{'x':.5+5e-10})
    with pytest.raises(ValueError):compare({'x':.5},{'x':.5+2e-9})
    with pytest.raises(ValueError):compare(True,1)
    with pytest.raises(ValueError):compare(float('nan'),float('nan'))


def test_route_must_match():
    card,_=load_card('prophet-spin-v2')
    route_check(card,{'001':{'J_meV':[1],'exchange_method':'exchange-head'}})
    with pytest.raises(ValueError):route_check(card,{'001':{'J_meV':[1],'exchange_method':'energy-mapping'}})
    with pytest.raises(ValueError):route_check(card,{'001':{'J_meV':[1]}})


def test_current_versions_required(checkout):
    p=checkout/'models/prophet-spin-ex/prophet-spin-ex.yml';c=yaml.safe_load(p.read_text());c['evaluation']['data_version']='0.1.0';p.write_text(yaml.safe_dump(c))
    review=validate('prophet-spin-ex',root=checkout,policy_root=ROOT,offline=True)
    assert next(r['status'] for r in review.rows if r['check']=='Version pins')=='FAIL'


def test_site_counts_come_from_score_records(checkout,tmp_path):
    import hashlib
    settings=config(checkout)
    ground_count=settings['cohorts']['ground_state']+7
    for key in KEYS:
        folder=checkout/'models'/key;p=folder/'scores.json';score=read(p)
        score['dimensions']['ground_state']['materials']=ground_count
        p.write_text(json.dumps(score,indent=2)+'\n')
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        settings['awaiting_publication'][key]['score_sha256']=digest
    (checkout/'benchmark.json').write_text(json.dumps(settings))
    build(root=checkout,output=tmp_path/'output')
    text=(tmp_path/'output/index.html').read_text()
    assert f'<strong>{ground_count}</strong>' in text
    model=(tmp_path/'output/models/prophet-spin-v2.html').read_text()
    assert f'/ {ground_count} ground-state passes' in model


@pytest.mark.parametrize('key',KEYS)
def test_ingest_preserves_existing_entries_without_public_replay(tmp_path,key):
    from scripts.ingest_model import ingest
    before=(ROOT/f'models/{key}/{key}.yml').read_bytes()
    with pytest.raises(ValueError,match='Public validation'):ingest(key,cache=tmp_path)
    assert (ROOT/f'models/{key}/{key}.yml').read_bytes()==before


def test_public_validation_and_ingest_round_trip(public_model,monkeypatch,tmp_path):
    from leaderboard import artifacts,validation
    from scripts.ingest_model import ingest
    root,key,card,folder=public_model
    prediction=tmp_path/'predictions.json'
    prediction.write_text(json.dumps({'001':{'J_meV':[1.],'exchange_method':'exchange-head'}}))
    monkeypatch.setattr(artifacts,'probe',lambda *a,**kw:16)
    monkeypatch.setattr(artifacts,'prediction_files',lambda *a,**kw:prediction)
    monkeypatch.setattr(artifacts,'targets',lambda *a,**kw:tmp_path/'targets')
    monkeypatch.setattr(validation,'replay',lambda *a:read(folder/'scores.json'))
    review=validate(key,root=root,policy_root=root,cache=tmp_path,require_public=True)
    assert review.passed,review.markdown()
    assert not any(r['status'] in ('EXEMPT','AWAITING ARTEFACTS') for r in review.rows)
    ingest(key,root=root,cache=tmp_path)
    active,_=load_card(key,root,root)
    assert active['lifecycle']=='active'
    built=read(root/'site/dist/data.json')
    assert next(e['card'] for e in built['models'] if e['card']['model_key']==key)['lifecycle']=='active'


def test_model_directory_symlinks_are_rejected(checkout,tmp_path):
    folder=checkout/'models/prophet-spin-ex';target=tmp_path/'moved';folder.rename(target);folder.symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError,match='symlinks'):load_card('prophet-spin-ex',checkout,ROOT)


def test_new_submission_lifecycle_and_git_path_guard(public_model):
    import subprocess
    root,key,card,folder=public_model
    subprocess.run(['git','init','-q'],cwd=root,check=True)
    subprocess.run(['git','add','.'],cwd=root,check=True)
    subprocess.run(['git','rm','--cached','-rq',f'models/{key}'],cwd=root,check=True)
    identity=subprocess.check_output(['git','log','--reverse','--format=%an%n%ae'],cwd=ROOT,text=True).splitlines()[:2]
    subprocess.run(['git','-c','user.name='+identity[0],'-c','user.email='+identity[1],'commit','-qm','Initial fixture'],cwd=root,check=True)
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    card['lifecycle']='active';(folder/f'{key}.yml').write_text(yaml.safe_dump(card))
    subprocess.run(['git','add',f'models/{key}'],cwd=root,check=True)
    review=validate(key,root=root,policy_root=ROOT,offline=True,base_ref=base)
    assert next(r['status'] for r in review.rows if r['check']=='Submission lifecycle')=='FAIL'
    card['lifecycle']='pending';(folder/f'{key}.yml').write_text(yaml.safe_dump(card))
    review=validate(key,root=root,policy_root=ROOT,offline=True,base_ref=base)
    assert next(r['status'] for r in review.rows if r['check']=='Submission lifecycle')=='PASS'
    assert next(r['status'] for r in review.rows if r['check']=='Model path guard')=='PASS'
    (root/'models/prophet-spin-v1/inference.py').write_text('class Model: pass\n')
    review=validate(key,root=root,policy_root=ROOT,offline=True,base_ref=base)
    assert next(r['status'] for r in review.rows if r['check']=='Model path guard')=='FAIL'
