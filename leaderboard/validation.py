"""Submission review without importing or running submitted inference code."""
import copy
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
from .cards import ROOT, load_card, config, read, metrics_from, compare, check_adapter, inside
from . import artifacts


class Review:
    def __init__(self): self.rows=[]
    def record(self,check,status,detail): self.rows.append({'check':check,'status':status,'detail':str(detail)})
    def check(self,name,call):
        try:
            value=call();self.record(name,'PASS',value if isinstance(value,(str,int,float,bool)) else 'Verified');return value
        except Exception as error:
            self.record(name,'FAIL',f'{type(error).__name__}: {error}');return None
    @property
    def passed(self):return not any(r['status']=='FAIL' for r in self.rows)
    def markdown(self):
        expected=('Model card schema','Required files','Model path guard','Submission lifecycle','Version pins','Stored scores and metrics','Public inference repository','Public checkpoint (range request)','Licences','Inference syntax and adapter definition','Inference script','Prediction artefact download','Pinned target integrity','Prediction JSON','Recorded exchange route','Scorer replay','Replay equals scores.json','Replay equals declared metrics')
        present={r['check'] for r in self.rows}
        for check in expected:
            if check not in present:self.record(check,'NOT RUN','A prerequisite is unavailable; see the explicit failure or awaiting-artefacts result above')
        clean=lambda v:str(v).replace('|','\\|').replace('\n',' ')
        return '| Check | Status | Result |\n|---|---|---|\n'+''.join('| '+ ' | '.join(clean(r[k]) for k in ('check','status','detail'))+' |\n' for r in self.rows)


def changed_paths(root,base_ref):
    raw=subprocess.check_output(['git','diff','--name-only','-z','--no-renames',base_ref,'--'],cwd=root)
    return [v.decode() for v in raw.split(b'\0') if v]


def path_guard(paths,key,*,root=None,base_ref=None):
    other=[p for p in paths if p.startswith('models/') and not p.startswith(f'models/{key}/')]
    if other: raise ValueError('Other model folders changed: '+', '.join(other))
    extras=[]
    for path in paths:
        if path.startswith(f'models/{key}/'):continue
        if path.startswith('datasets/'):
            if not re.fullmatch(r'datasets/[a-z0-9]+(?:-[a-z0-9]+)*\.yml',path):
                raise ValueError('Dataset additions must be datasets/<dataset_key>.yml')
            if root is None or base_ref is None:
                raise ValueError('Dataset additions require a trusted base reference')
            existed=subprocess.run(['git','cat-file','-e',f'{base_ref}:{path}'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
            if existed:raise ValueError('Existing dataset records cannot be edited by a model submission: '+path)
            if not (Path(root)/path).is_file():raise ValueError('A new dataset record is missing')
        else:extras.append(path)
    return extras


def route_check(card,predictions):
    expected={'exchange_readout':'exchange-head','energy_mapping':'energy-mapping'}[card['evaluation']['exchange_route']]
    observed=[]
    for key,row in predictions.items():
        if not isinstance(row,dict):raise ValueError('Prediction rows must be objects')
        if 'J_meV' in row:
            observed.append(row.get('exchange_method'))
        if 'dJ_dlnV_meV' in row:
            observed.append(row.get('magnetovolume_method',row.get('exchange_method')))
    if not observed or any(v!=expected for v in observed):raise ValueError('Recorded prediction exchange method differs from the card')
    return f'{expected}; {len(observed)} parameter records'


def replay(target_dir,prediction):
    sys.path.insert(0,str(ROOT/'benchmark_runner'))
    from magbench.scoring import evaluate
    return evaluate(target_dir,read(prediction),Path(prediction).resolve().parent)


def compare_replay(scored, stored):
    """Allow the new gate error diagnostic when checking historical scores."""
    comparable = copy.deepcopy(scored)
    old_rows = {row['id']: row for row in stored['materials']}
    for row in comparable['materials']:
        detail = row['details'].get('ground_state')
        old = old_rows.get(row['id'], {})
        if (not row['ground_state_pass'] and detail is not None
                and set(detail) == {'failed'}
                and 'ground_state' not in old.get('details', {})):
            del row['details']['ground_state']
    compare(comparable, stored, 'scores')


def validate(key,*,root=ROOT,policy_root=ROOT,offline=False,data=None,predictions=None,cache=None,base_ref=None,require_public=False):
    review=Review();loaded=review.check('Model card schema',lambda:load_card(key,root,policy_root))
    if loaded is None:return review
    card,folder=loaded
    if card['lifecycle']=='draft':
        review.record('Submission lifecycle','FAIL','Draft entries are not scored submissions; complete local ingest first')
        return review
    settings=config(policy_root);score_path=folder/'scores.json'
    def files():
        for path in (folder/f'{key}.yml',score_path,inside(folder,card['inference']['script'])):
            if not path.is_file() or path.is_symlink():raise ValueError('Required ordinary file missing: '+path.name)
        return 'Card, scores.json and inference script are present'
    review.check('Required files',files)
    if base_ref:
        extras=review.check('Model path guard',lambda:path_guard(changed_paths(root,base_ref),key,root=root,base_ref=base_ref))
        if extras:review.record('Maintainer review','REVIEW','Changes outside the model folder: '+', '.join(extras))
    else:review.record('Model path guard','NOT RUN','No --base-ref supplied; required in pull-request CI')
    if base_ref:
        def lifecycle():
            existed=subprocess.run(['git','cat-file','-e',f'{base_ref}:models/{key}/{key}.yml'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
            if not existed and card['lifecycle']!='pending':raise ValueError('A new submission must start with lifecycle: pending')
            return 'Existing record update' if existed else 'New submission is pending'
        review.check('Submission lifecycle',lifecycle)
    else:review.record('Submission lifecycle','NOT RUN','New-record detection requires --base-ref; enforced in pull-request CI')
    def versions():
        expected={'protocol_version':settings['protocol_version'],'data_version':settings['dataset']['data_version'],'runner_version':settings['runner_version']}
        compare(expected,{k:card['evaluation'][k] for k in expected},'versions');return 'Current protocol, data and runner versions'
    review.check('Version pins',versions)
    awaiting=card.get('publication_status')=='awaiting_artifacts'
    owner_local=bool(card.get('publication_status')) and bool(predictions) and not require_public
    def stored():
        result=read(score_path);compare(metrics_from(result),card['metrics'],'declared metrics')
        if result.get('protocol_version') != settings['protocol_version']:raise ValueError('Score protocol differs')
        if len({row['id'] for row in result['materials']}) != len(result['materials']):
            raise ValueError('Duplicate score material IDs')
        for dimension,count in settings['cohorts'].items():
            if (result['dimensions'][dimension]['materials'] != count
                    or sum(row['scores'][dimension] is not None for row in result['materials']) != count):
                raise ValueError('Scores must cover the full pinned dimension cohort')
        return 'Declared metrics agree with scores.json within 1e-9; ground-state passes agree'
    review.check('Stored scores and metrics',stored)
    def unavailable(name,reason):
        review.record(name,'FAIL' if require_public else 'AWAITING ARTEFACTS',reason)
    def public_check(name,url,call):
        if awaiting and url=='to be provided':unavailable(name,'awaiting artefacts: a public address has not been supplied')
        elif offline:
            review.record(name,'NOT RUN' if (awaiting and not require_public) or owner_local else 'FAIL','Offline mode cannot establish public availability')
        else:review.check(name,call)
    public_check('Public inference repository',card['repo'],lambda:artifacts.probe(card['repo']))
    public_check('Public checkpoint (range request)',card['checkpoint']['url'],lambda:artifacts.probe(card['checkpoint']['url'],checkpoint=True))
    def licenses():
        if any(v=='to be provided' or not v.strip() for v in card['license'].values()):raise ValueError('Both code and checkpoint licences must be stated')
        return 'Code and checkpoint licences stated'
    if awaiting and any(v=='to be provided' for v in card['license'].values()):unavailable('Licences','awaiting artefacts: licence metadata requires owner confirmation')
    else:review.check('Licences',licenses)
    script=review.check('Inference syntax and adapter definition',lambda:str(check_adapter(card,folder).resolve().relative_to(folder.resolve())))
    if awaiting and not settings['awaiting_publication'][key].get('inference_available',False):
        expected=settings['awaiting_publication'][key]['inference_sha256']
        actual=hashlib.sha256(inside(folder,card['inference']['script']).read_bytes()).hexdigest() if script else ''
        if actual==expected:unavailable('Inference script','awaiting artefacts: the tracked script is an explicit release placeholder')
        else:review.record('Inference script','FAIL','Owner-approved release placeholder differs; remove the exception for a public submission')
    else:review.record('Inference script','PASS' if script else 'FAIL','Adapter definition checked without executing model code')
    prediction=Path(predictions).resolve() if predictions else None
    if prediction:
        def local_prediction():
            if prediction.stat().st_size>settings['limits']['predictions_bytes']:raise ValueError('Prediction JSON exceeds size limit')
            artifacts.verify(prediction,card['predictions']['sha256'],card['predictions']['size'])
            artifacts.verify_local_phonons(card,prediction,settings['limits'])
            return 'Explicit local predictions; not evidence of public availability'
        if review.check('Local prediction integrity',local_prediction) is None:prediction=None
    if offline:
        review.record('Prediction artefact download','NOT RUN' if (awaiting or owner_local) and prediction and not require_public else 'FAIL','Public download is not tested offline; supplied local files are checked separately')
    elif not cache:
        review.record('Prediction artefact download','FAIL','Supply --cache on a filesystem with sufficient space')
    else:
        prediction=review.check('Prediction artefact download',lambda:artifacts.prediction_files(card,settings,cache))
    if not prediction:
        review.record('Scorer replay','FAIL','Verified prediction artefacts are required for every entry')
        return review
    target_dir=review.check('Pinned target integrity',lambda:artifacts.targets(settings,data=data,cache=cache,offline=offline))
    preds=review.check('Prediction JSON',lambda:read(prediction))
    if preds is not None:review.check('Recorded exchange route',lambda:route_check(card,preds))
    if target_dir:
        scored=review.check('Scorer replay',lambda:replay(target_dir,prediction))
        if scored is not None:
            review.check('Replay equals scores.json',lambda:compare_replay(scored,read(score_path)))
            review.check('Replay equals declared metrics',lambda:compare(metrics_from(scored),card['metrics']))
    else:review.record('Scorer replay','FAIL','Pinned targets are required')
    return review
