"""Architecture metadata and preparation of the unlisted owner entry."""
import hashlib
import json
from pathlib import Path
import pytest
import yaml
from leaderboard.cards import ROOT,load_card,read,config
from leaderboard.site import build
from leaderboard.validation import validate
from scripts.ingest_model import ingest

DRAFT='prophet-spin-v1s-6a'


@pytest.fixture
def owner_draft(checkout):
    folder=checkout/'models'/DRAFT;p=folder/f'{DRAFT}.yml';c=yaml.safe_load(p.read_text())
    c['lifecycle']='draft';c.pop('publication_status',None);c.pop('metrics',None)
    c['predictions']={'url':'to be provided','sha256':'to be provided','size':'to be provided',
                      'phonons':{'url':'to be provided','sha256':'to be provided','size':'to be provided'}}
    p.write_text(yaml.safe_dump(c,sort_keys=False,allow_unicode=True));(folder/'scores.json').unlink(missing_ok=True)
    settings=config(checkout);settings['awaiting_publication'].pop(DRAFT,None);settings.get('metadata_pending',{}).pop(DRAFT,None)
    settings.setdefault('draft_entries',{})[DRAFT]={'card_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                                                'inference_sha256':hashlib.sha256((folder/'inference.py').read_bytes()).hexdigest()}
    (checkout/'benchmark.json').write_text(json.dumps(settings))
    return checkout


@pytest.mark.parametrize('path',[('hyperparams',),('hyperparams','architecture')])
def test_hyperparameter_unknown_keys_rejected(checkout,path):
    p=checkout/'models/prophet-spin-v1s/prophet-spin-v1s.yml';c=yaml.safe_load(p.read_text());v=c
    for key in path:v=v[key]
    v['unexpected']=1;p.write_text(yaml.safe_dump(c))
    with pytest.raises(Exception,match='unexpected'):load_card('prophet-spin-v1s',checkout,checkout)


@pytest.mark.parametrize('field,value',[('cutoff_A',[]),('cutoff_A',[-1]),('cutoff_A',[3,3]),('exchange_range_A',0),('n_layers',1.5),('model_params',0)])
def test_invalid_architecture_values_rejected(checkout,field,value):
    p=checkout/'models/prophet-spin-v1s/prophet-spin-v1s.yml';c=yaml.safe_load(p.read_text());c['hyperparams']['architecture'][field]=value;p.write_text(yaml.safe_dump(c))
    with pytest.raises(Exception):load_card('prophet-spin-v1s',checkout,checkout)


def test_hyperparameter_block_required_and_null_exchange_accepted(checkout):
    p=checkout/'models/prophet-spin-v1s/prophet-spin-v1s.yml';c=yaml.safe_load(p.read_text());c['hyperparams']['architecture']['exchange_range_A']=None;p.write_text(yaml.safe_dump(c));load_card('prophet-spin-v1s',checkout,checkout)
    c.pop('hyperparams');p.write_text(yaml.safe_dump(c))
    with pytest.raises(Exception,match='hyperparams'):load_card('prophet-spin-v1s',checkout,checkout)


def test_draft_has_no_page_or_payload_and_is_not_submission(owner_draft,tmp_path):
    checkout=owner_draft
    c,f=load_card(DRAFT,checkout,checkout);assert c['lifecycle']=='draft' and not (f/'scores.json').exists()
    output=tmp_path/'output';(output/'models').mkdir(parents=True);(output/'models'/f'{DRAFT}.html').write_text('stale')
    data=build(root=checkout,output=output)
    assert DRAFT not in [e['card']['model_key'] for e in data['models']]
    assert not (output/'models'/f'{DRAFT}.html').exists()
    assert not validate(DRAFT,root=checkout,policy_root=checkout,offline=True).passed
    assert c['checkpoint']['url'].startswith('https://')


def test_unknown_entry_cannot_claim_owner_draft(public_model):
    root,key,c,f=public_model;c['lifecycle']='draft';(f/f'{key}.yml').write_text(yaml.safe_dump(c))
    with pytest.raises(Exception):load_card(key,root,root)


def prepare_run(root,source):
    source.mkdir();(source/'phonons').mkdir();p=source/'phonons/001.npz';p.write_bytes(b'fixture')
    (source/'predictions.json').write_text(json.dumps({'001':{'J_meV':[1.],'exchange_method':'exchange-head','phonon_file':'phonons/001.npz'}}))
    score=read(root/'models/prophet-spin-v1s/scores.json');(source/'scores.json').write_text(json.dumps(score));return score


def test_completed_draft_ingest_replays_before_listing(owner_draft,tmp_path,monkeypatch):
    checkout=owner_draft.resolve()
    import scripts.ingest_model as module
    from leaderboard import artifacts,validation
    source=(tmp_path/'external-run').resolve();score=prepare_run(checkout,source)
    monkeypatch.setattr(artifacts,'targets',lambda *a,**kw:(tmp_path/'targets').resolve())
    monkeypatch.setattr(module,'replay',lambda *a:score);monkeypatch.setattr(validation,'replay',lambda *a:score)
    ingest(DRAFT,root=checkout,predictions=source,data=tmp_path)
    c,f=load_card(DRAFT,checkout,checkout);assert c['lifecycle']=='pending';assert c['metrics']['total']==score['total_score']
    assert c['predictions']['sha256']==hashlib.sha256((source/'predictions.json').read_bytes()).hexdigest()
    assert not (f/'predictions.json').exists() and not (f/'phonons').exists()
    assert any(e['card']['model_key']==DRAFT for e in read(checkout/'site/dist/data.json')['models'])


def test_failed_draft_replay_changes_no_tracked_record(owner_draft,tmp_path,monkeypatch):
    checkout=owner_draft.resolve()
    import scripts.ingest_model as module
    from leaderboard import artifacts
    source=(tmp_path/'external-run').resolve();score=prepare_run(checkout,source);changed=dict(score,total_score=score['total_score']+.01)
    monkeypatch.setattr(artifacts,'targets',lambda *a,**kw:(tmp_path/'targets').resolve());monkeypatch.setattr(module,'replay',lambda *a:changed)
    before={p:p.read_bytes() for p in (checkout/'benchmark.json',checkout/'models'/DRAFT/f'{DRAFT}.yml')}
    with pytest.raises(ValueError,match='number differs'):ingest(DRAFT,root=checkout,predictions=source,data=tmp_path)
    assert all(p.read_bytes()==v for p,v in before.items())
    assert not (checkout/'models'/DRAFT/'scores.json').exists()


def test_completed_owner_entry_has_public_artifacts_and_restricted_metadata(checkout):
    key='prophet-spin-v1s-6a';card,folder=load_card(key,checkout,checkout)
    assert card['lifecycle']=='active' and card['metrics']['ground_state_passes']==116
    assert card['checkpoint']['url'].startswith('https://') and card['predictions']['url'].startswith('https://')
    card['checkpoint']['url']='to be provided';(folder/f'{key}.yml').write_text(yaml.safe_dump(card))
    with pytest.raises(ValueError,match='public artefacts'):load_card(key,checkout,checkout)


def test_completed_metadata_exception_does_not_apply_to_new_submissions(public_model):
    root,key,card,folder=public_model
    card['lifecycle']='active';card['publication_status']='metadata_incomplete'
    (folder/f'{key}.yml').write_text(yaml.safe_dump(card))
    with pytest.raises(Exception):load_card(key,root,root)


def test_adapter_path_accepts_symlinked_checkout(public_model, tmp_path):
    checkout, key, card, folder = public_model
    alias = tmp_path / 'checkout-link'
    alias.symlink_to(checkout.resolve(), target_is_directory=True)
    result = validate(key, root=alias, policy_root=alias, offline=True)
    checks = {row['check']: row['status'] for row in result.rows}
    assert checks['Inference syntax and adapter definition'] == 'PASS'
