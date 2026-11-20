import copy
import json
from pathlib import Path
import shutil
import sys
import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'benchmark_runner'))
from leaderboard.cards import read


@pytest.fixture
def checkout(tmp_path):
    for name in ('models','tests','site/assets'):
        shutil.copytree(ROOT/name,tmp_path/name,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy(ROOT/'benchmark.json',tmp_path/'benchmark.json')
    return tmp_path


@pytest.fixture
def public_model(checkout):
    key='example-model';folder=checkout/'models'/key
    shutil.copytree(checkout/'models/prophet-spin-ex',folder)
    card=yaml.safe_load((folder/'prophet-spin-ex.yml').read_text());(folder/'prophet-spin-ex.yml').unlink()
    card.update(model_key=key,model_name='Example model',model_params=123,repo='https://example.org/code')
    card.pop('publication_status');card['authors']=[dict(name='Example researcher',affiliation='Example institute',corresponding=True)]
    card['checkpoint']={'url':'https://example.org/weights','sha256':'a'*64,'size':16}
    card['license']={'code':'MIT','checkpoint':'MIT'}
    card['training_sets']=[dict(name='Example set',url='https://example.org/data',size=10,open=True)]
    card['inference']['python_version']='3.11';card['inference']['command']='python inference.py run'
    card['predictions']={'url':'https://example.org/predictions.json','sha256':'b'*64,'size':10,'phonons':{'url':'https://example.org/phonons.zip','sha256':'c'*64,'size':10}}
    (folder/f'{key}.yml').write_text(yaml.safe_dump(card))
    return checkout,key,card,folder
