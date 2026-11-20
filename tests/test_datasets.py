"""Dataset identity, references, submission boundaries and visible values."""
import copy
import json
from pathlib import Path
import subprocess
import pytest
import yaml
from leaderboard.cards import ROOT, load_card
from leaderboard.datasets import load_datasets, training_data, training_frames
from leaderboard.site import build, payload
from leaderboard.validation import path_guard


def write_record(root, record):
    path=root/'datasets'/f"{record['dataset_key']}.yml"
    path.write_text(yaml.safe_dump(record,sort_keys=False))
    return path


def test_seed_datasets_and_references():
    records=load_datasets(ROOT)
    assert list(records)==['prophet-pretrain','elementa-spin-v1','elementa-spin-v2']
    for path in (ROOT/'models').glob('*/*.yml'):
        card,_=load_card(path.parent.name)
        assert all(item['dataset_key'] in records for item in training_data(card,records))


@pytest.mark.parametrize('section',[None,'magnetic','method','benchmark_overlap','authors'])
def test_dataset_unknown_keys_rejected(checkout,section):
    records=load_datasets(checkout);record=records['elementa-spin-v2']
    target=record if section is None else record.setdefault(section,[{'name':'Researcher','affiliation':'Institute'}])[0] if section=='authors' else record.setdefault(section,{})
    target['unexpected_field']=True;write_record(checkout,record)
    with pytest.raises(Exception,match='unexpected_field'):load_datasets(checkout)


@pytest.mark.parametrize('field,value',[('n_structures',-1),('n_elements',2.5),('open','yes'),('date_added','20 November'),('url','javascript:alert(1)')])
def test_dataset_invalid_values_rejected(checkout,field,value):
    record=load_datasets(checkout)['elementa-spin-v2'];record[field]=value;write_record(checkout,record)
    with pytest.raises(Exception):load_datasets(checkout)


def test_record_identity_parents_and_element_count(checkout):
    record=load_datasets(checkout)['elementa-spin-v2'];record['parent_datasets']=['missing'];write_record(checkout,record)
    with pytest.raises(ValueError,match='Missing parent'):load_datasets(checkout)
    record['parent_datasets']=['elementa-spin-v2'];write_record(checkout,record)
    with pytest.raises(ValueError,match='cycle'):load_datasets(checkout)
    record['parent_datasets']=[];record['n_elements']=1;write_record(checkout,record)
    with pytest.raises(ValueError,match='element count'):load_datasets(checkout)


def test_missing_training_dataset_rejected(checkout):
    path=checkout/'models/prophet-spin-v1l/prophet-spin-v1l.yml';card=yaml.safe_load(path.read_text())
    card['training_sets'][0]['dataset_key']='missing';path.write_text(yaml.safe_dump(card))
    with pytest.raises(ValueError,match='Missing training dataset'):load_card('prophet-spin-v1l',checkout,checkout)


def test_dataset_symlink_rejected(checkout,tmp_path):
    path=checkout/'datasets/elementa-spin-v2.yml';external=tmp_path/'record.yml';path.rename(external);path.symlink_to(external)
    with pytest.raises(ValueError,match='ordinary'):load_datasets(checkout)


def test_training_totals_do_not_expand_unknown_subsets():
    records={'a':{'name':'A','n_structures':100,'parent_datasets':[]},'b':{'name':'B','n_structures':20,'parent_datasets':[]}}
    card={'training_sets':[{'dataset_key':'a','usage':'training'},{'dataset_key':'b','usage':'pretraining'}]}
    assert training_frames(card,records)==120
    card['training_sets'].append({'dataset_key':'a','usage':'fine-tuning'})
    assert training_frames(card,records)==120
    card['training_sets'][0]['subset']='to be provided'
    assert training_frames(card,records) is None
    card['training_sets'][0].pop('subset');records['b']['parent_datasets']=['a']
    assert training_frames(card,records) is None
    records['b']['parent_datasets']=[];records['b']['n_structures']='to be provided'
    assert training_frames(card,records) is None


def test_model_submission_can_add_but_not_edit_datasets(checkout):
    subprocess.run(['git','init','-q'],cwd=checkout,check=True)
    subprocess.run(['git','add','.'],cwd=checkout,check=True)
    identity=subprocess.check_output(['git','log','--reverse','--format=%an%n%ae'],cwd=ROOT,text=True).splitlines()[:2]
    subprocess.run(['git','-c','user.name='+identity[0],'-c','user.email='+identity[1],'commit','-qm','Initial fixture'],cwd=checkout,check=True)
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
    record=copy.deepcopy(load_datasets(checkout)['elementa-spin-v2']);record['dataset_key']='new-data';write_record(checkout,record)
    assert path_guard(['models/example/inference.py','datasets/new-data.yml'],'example',root=checkout,base_ref=base)==[]
    assert path_guard(['datasets/new-data.yml','README.md'],'example',root=checkout,base_ref=base)==['README.md']
    with pytest.raises(ValueError,match='Existing dataset'):path_guard(['datasets/elementa-spin-v2.yml'],'example',root=checkout,base_ref=base)
    with pytest.raises(ValueError,match='Other model'):path_guard(['models/other/scores.json'],'example',root=checkout,base_ref=base)
    with pytest.raises(ValueError,match='Dataset additions'):path_guard(['datasets/sub/data.yml'],'example',root=checkout,base_ref=base)


def test_dataset_payload_pages_and_parameter_format(tmp_path):
    data=build(output=tmp_path)
    assert data==payload() and json.loads((tmp_path/'data.json').read_text())==data
    page=(tmp_path/'datasets.html').read_text()
    assert 'Benchmark data' in page and 'id="datasets"' in page
    for key,record in data['datasets'].items():
        assert f'id="{key}"' in page and record['name'] in page
    for entry in data['models']:
        card=entry['card'];count=card['hyperparams']['architecture']['model_params']
        assert isinstance(count,int) and entry['training_data']
        assert entry['training_data']==training_data(card,data['datasets'])
        assert entry['training_frames']==training_frames(card,data['datasets'])
        model=(tmp_path/f"models/{card['model_key']}.html").read_text()
        assert f'{count/1e6:.1f}M' in model and f'{count:,}' not in model and str(count) not in model
        for item in entry['training_data']:
            assert f'../datasets.html#{item["dataset_key"]}' in model
            assert f'models/{card["model_key"]}.html' in page
    submit=(tmp_path/'submit.html').read_text()
    assert 'Submitting a dataset' in submit and 'dataset_key' in submit
    assert 'maintainers.md' not in submit and 'ingest_model.py' not in submit and 'Prepared owner draft' not in submit
    for name in ('index.html','protocol.html','submit.html'):
        content=(tmp_path/name).read_text()
        assert 'datasets.html' in content
    assert 'MP hull with spin' in (tmp_path/'protocol.html').read_text()
    assert 'Phonons with spin' in (tmp_path/'index.html').read_text()


@pytest.mark.parametrize('change',[{'usage':'validation'},{'unknown':1}])
def test_training_reference_is_strict(checkout,change):
    path=checkout/'models/prophet-spin-v1l/prophet-spin-v1l.yml';card=yaml.safe_load(path.read_text())
    card['training_sets'][0].update(change);path.write_text(yaml.safe_dump(card))
    with pytest.raises(Exception):load_card('prophet-spin-v1l',checkout,checkout)


def test_optional_dataset_fields_are_absent_and_not_printed(checkout,tmp_path):
    record={'name':'Example dataset','dataset_key':'example','description':'Atomic structures.','open':False,'magnetic':{'site_moments':True,'spin_mode':'collinear'}}
    write_record(checkout,record);assert load_datasets(checkout)['example']==record
    build(root=checkout,output=tmp_path/'output');page=(tmp_path/'output/datasets.html').read_text()
    block=page.split('id="example"')[1].split('</section>')[0]
    assert 'Method</h3>' not in block and 'Benchmark overlap</h3>' not in block and 'Parent datasets</h3>' not in block
    assert 'to be provided' not in page
    assert '<th scope="col">Site moments</th>' in page
    record['open']=True;write_record(checkout,record)
    with pytest.raises(Exception):load_datasets(checkout)
    record.update(url='https://example.org/data',license='MIT');write_record(checkout,record);load_datasets(checkout)
    record['description']='to be provided';write_record(checkout,record)
    with pytest.raises(Exception):load_datasets(checkout)


def test_release_sizes_are_not_actual_training_counts():
    records={'a':{'name':'A','n_structures':100,'size_scope':'Public release'}}
    assert training_frames({'training_sets':[{'dataset_key':'a','usage':'pretraining'}]},records) is None


def test_new_dataset_requires_magnetic_information(checkout):
    record={'name':'Example dataset','dataset_key':'example','description':'Atomic structures.','open':False}
    write_record(checkout,record)
    with pytest.raises(Exception,match='magnetic'):load_datasets(checkout)


def test_training_stages_and_public_component_links(tmp_path):
    data=build(output=tmp_path)
    for entry in data['models']:
        references=entry['card']['training_sets']
        assert len(references)==2 and references[0]=={'dataset_key':'prophet-pretrain','usage':'pretraining'}
        assert references[1]['usage']=='training' and references[1]['dataset_key'] in ('elementa-spin-v1','elementa-spin-v2')
        assert entry['training_frames'] is None
        page=(tmp_path/'models'/f"{entry['card']['model_key']}.html").read_text()
        assert '>Prophet pretrain</a> + <a ' in page
    text=(tmp_path/'datasets.html').read_text()
    assert '[ELEMENTA](' not in text
    for url in ('https://huggingface.co/datasets/kairosmaterial/ELEMENTA','https://huggingface.co/datasets/facebook/OMAT24','https://figshare.com/articles/dataset/Materials_Project_Trjectory_MPtrj_Dataset/23713842'):
        assert f'href="{url}"' in text
    assert '4.7 million frames' in text


def test_description_links_escape_markup_and_reject_script_urls(checkout,tmp_path):
    record=load_datasets(checkout)['elementa-spin-v2']
    record['description']='[Public source](https://example.org/data) <script>bad()</script> [Unsafe](javascript:alert)'
    write_record(checkout,record);build(root=checkout,output=tmp_path/'output')
    text=(tmp_path/'output/datasets.html').read_text()
    assert '<a href="https://example.org/data">Public source</a>' in text
    assert '<script>bad()' not in text and 'href="javascript:' not in text
